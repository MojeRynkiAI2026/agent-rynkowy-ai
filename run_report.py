import os, io, json, logging, smtplib
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
import pandas as pd
import yfinance as yf
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
TZ = ZoneInfo("Europe/Warsaw")
TODAY = datetime.now(TZ).strftime("%Y-%m-%d")
QUOTE = os.getenv("QUOTE_CURRENCY", "usd").lower()
ETF_TICKERS = [x.strip() for x in os.getenv("ETF_TICKERS", "VWCE.DE,EUNL.DE,SXR8.DE,IWDA.AS").split(",") if x.strip()]
CRYPTO_IDS = [x.strip() for x in os.getenv("CRYPTO_IDS", "bitcoin,ethereum").split(",") if x.strip()]
OUT = Path("reports")
OUT.mkdir(exist_ok=True)

def pct_change(s, n):
    s = s.dropna()
    if len(s) <= n or not s.iloc[-n-1]:
        return None
    return (float(s.iloc[-1]) / float(s.iloc[-n-1]) - 1) * 100

def fmt(v):
    return "brak danych" if v is None or pd.isna(v) else f"{v:+.2f}%"

def rsi(s, n=14):
    d = s.diff()
    up = d.clip(lower=0).rolling(n).mean()
    down = (-d.clip(upper=0)).rolling(n).mean()
    rs = up / down.replace(0, float("nan"))
    return 100 - 100 / (1 + rs)

def history(ticker, period="2y"):
    df = yf.download(ticker, period=period, interval="1d", auto_adjust=True, progress=False, threads=False)
    if df.empty:
        raise ValueError("brak notowań")
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df["Close"].dropna()

def stats(s):
    last = float(s.iloc[-1])
    sma50 = float(s.rolling(50).mean().iloc[-1]) if len(s) >= 50 else None
    sma200 = float(s.rolling(200).mean().iloc[-1]) if len(s) >= 200 else None
    r = rsi(s).iloc[-1] if len(s) >= 15 else None
    r = float(r) if r is not None and pd.notna(r) else None
    return {"last": last, "d1": pct_change(s,1), "w1": pct_change(s,5),
            "m1": pct_change(s,21), "m3": pct_change(s,63), "y1": pct_change(s,252),
            "sma50": sma50, "sma200": sma200, "rsi14": r,
            "above_sma50": last > sma50 if sma50 else None,
            "above_sma200": last > sma200 if sma200 else None}

def get_crypto_market():
    headers = {}
    key = os.getenv("COINGECKO_API_KEY", "").strip()
    if key:
        headers["x-cg-demo-api-key"] = key
    response = requests.get("https://api.coingecko.com/api/v3/coins/markets",
        params={"vs_currency": QUOTE, "ids": ",".join(CRYPTO_IDS),
                "price_change_percentage": "24h,7d,30d"},
        headers=headers, timeout=25)
    response.raise_for_status()
    return response.json()

def get_flows():
    result = {}
    for asset, url in {
        "BTC": "https://farside.co.uk/bitcoin-etf-flow-all-data/",
        "ETH": "https://farside.co.uk/ethereum-etf-flow-all-data/"
    }.items():
        try:
            resp = requests.get(url, timeout=25, headers={"User-Agent":"Mozilla/5.0"})
            resp.raise_for_status()
            tables = pd.read_html(io.StringIO(resp.text))
            if not tables:
                raise ValueError("nie znaleziono tabeli")
            table = max(tables, key=lambda t: t.shape[0])
            result[asset] = {"url":url, "columns":[str(c) for c in table.columns],
                             "rows":table.tail(6).fillna("").astype(str).values.tolist()}
        except Exception as exc:
            result[asset] = {"url":url, "error":str(exc)}
    return result

def make_chart(crypto_series, etf_series):
    fig, ax = plt.subplots(2, 1, figsize=(11, 8))
    for name, s in crypto_series.items():
        ax[0].plot(s.index, s / s.iloc[0] * 100, label=name)
    ax[0].set_title("Kryptowaluty — indeksowane zmiany cen"); ax[0].legend(); ax[0].grid(True, alpha=.25)
    for name, s in etf_series.items():
        ax[1].plot(s.index, s / s.iloc[0] * 100, label=name)
    ax[1].set_title("ETF-y — indeksowane zmiany cen"); ax[1].legend(); ax[1].grid(True, alpha=.25)
    fig.tight_layout()
    path = OUT / f"wykres_{TODAY}.png"
    fig.savefig(path, dpi=150); plt.close(fig)
    return path

def regime(d):
    if "error" in d: return "brak danych"
    votes = sum(d.get(k) is True for k in ("above_sma50","above_sma200","above_sma200w"))
    votes -= sum(d.get(k) is False for k in ("above_sma50","above_sma200","above_sma200w"))
    r = d.get("rsi14")
    if votes >= 2 and (r is None or r < 75): return "przewaga sygnałów wzrostowych"
    if votes <= -2: return "podwyższone ryzyko trendu spadkowego"
    return "sygnały mieszane — wymagana ostrożność"

def ai_comment(payload):
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if not key: return None
    try:
        from openai import OpenAI
        client = OpenAI(api_key=key)
        response = client.responses.create(
            model=os.getenv("OPENAI_MODEL", "gpt-6"),
            instructions=("Pisz po polsku jak analityk rynku. Używaj wyłącznie przekazanych danych; nie zgaduj. "
            "Oddziel fakty od interpretacji. Oceń konflikt między cyklem czteroletnim BTC, trendem i przepływami ETF. "
            "Podaj scenariusz bazowy, wzrostowy i spadkowy oraz warunki potwierdzenia/unieważnienia. "
            "Wskaźniki on-chain nieobecne w danych oznacz jako niedostępne. Nie obiecuj wyników ani nie wydawaj pewnych sygnałów kupna/sprzedaży."),
            input=json.dumps(payload, ensure_ascii=False, default=str))
        return response.output_text
    except Exception as exc:
        logging.warning("Komentarz AI niedostępny: %s", exc)
        return None

def build():
    crypto_market = get_crypto_market()
    etfs, etf_series = [], {}
    for ticker in ETF_TICKERS:
        try:
            s = history(ticker, "2y"); d = stats(s); d["ticker"] = ticker
            etfs.append(d); etf_series[ticker] = s
        except Exception as exc:
            etfs.append({"ticker":ticker, "error":str(exc)})
    technicals, crypto_series = {}, {}
    for ticker in ("BTC-USD","ETH-USD"):
        try:
            s = history(ticker, "5y"); d = stats(s)
            weekly = s.resample("W").last().dropna()
            d["sma200w"] = float(weekly.rolling(200).mean().iloc[-1]) if len(weekly) >= 200 else None
            d["above_sma200w"] = d["last"] > d["sma200w"] if d["sma200w"] else None
            d["drawdown_from_2y_high_pct"] = (d["last"] / float(s.tail(730).max()) - 1) * 100
            technicals[ticker] = d; crypto_series[ticker] = s
        except Exception as exc:
            technicals[ticker] = {"error":str(exc)}
    flows = get_flows()
    payload = {"date":TODAY, "currency":QUOTE, "crypto_market":crypto_market, "etfs":etfs,
               "btc_eth_technicals":technicals, "spot_etf_flows":flows,
               "onchain_note":"MVRV, NUPL, SOPR, Puell Multiple i LTH/STH wymagają odrębnego źródła API i nie są dostępne w tej wersji."}
    commentary = ai_comment(payload)
    if not commentary:
        parts = ["Komentarz regułowy (bez modelu językowego):"]
        for ticker, d in technicals.items():
            if "error" not in d:
                parts.append(f"- {ticker}: {regime(d)}; 1 mies. {fmt(d.get('m1'))}; "
                             f"obsunięcie od maksimum z 2 lat {fmt(d.get('drawdown_from_2y_high_pct'))}.")
        parts.append("Cykl czteroletni BTC jest kontekstem historycznym, nie zegarem rynku. "
                     "Potwierdzaj ocenę trendem, przepływami ETF i danymi on-chain, gdy są dostępne.")
        parts.append("Scenariusz wzrostowy wymaga poprawy trendu i utrzymania popytu; spadkowy — utrwalenia słabości trendu i odpływów. "
                     "To ramy obserwacji, nie prognoza.")
        commentary = "\n".join(parts)
    payload["commentary"] = commentary
    (OUT / f"dane_{TODAY}.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    chart = make_chart(crypto_series, etf_series)
    lines = [f"RAPORT RYNKOWY AI — {TODAY}", f"Wygenerowano: {datetime.now(TZ).strftime('%H:%M %Z')}",
             f"Waluta kryptowalut: {QUOTE.upper()}", "", "1. KRYPTOWALUTY"]
    for c in crypto_market:
        lines.append(f"- {c.get('name')} ({str(c.get('symbol','')).upper()}): {c.get('current_price')} {QUOTE.upper()}; "
                     f"24 h {fmt(c.get('price_change_percentage_24h'))}; 7 dni {fmt(c.get('price_change_percentage_7d_in_currency'))}; "
                     f"30 dni {fmt(c.get('price_change_percentage_30d_in_currency'))}; kapitalizacja {c.get('market_cap')}.")
    lines += ["", "2. ETF-Y AKCYJNE"]
    for e in etfs:
        if "error" in e: lines.append(f"- {e['ticker']}: błąd danych — {e['error']}")
        else:
            rv = f"{e['rsi14']:.1f}" if e.get("rsi14") is not None else "brak danych"
            lines.append(f"- {e['ticker']}: kurs {e['last']:.2f}; 1 dzień {fmt(e.get('d1'))}; tydzień {fmt(e.get('w1'))}; "
                         f"miesiąc {fmt(e.get('m1'))}; 3 mies. {fmt(e.get('m3'))}; rok {fmt(e.get('y1'))}; RSI(14) {rv}.")
    lines += ["", "3. BTC I ETH — TREND / RYZYKO"]
    for ticker, d in technicals.items():
        if "error" in d: lines.append(f"- {ticker}: brak danych — {d['error']}")
        else:
            lines.append(f"- {ticker}: {regime(d)}; kurs {d['last']:.2f}; tydzień {fmt(d.get('w1'))}; miesiąc {fmt(d.get('m1'))}; "
                         f"3 mies. {fmt(d.get('m3'))}; rok {fmt(d.get('y1'))}; RSI(14) {d.get('rsi14')}; "
                         f"średnia 200 tyg. {d.get('sma200w')}; od maksimum 2-letniego {fmt(d.get('drawdown_from_2y_high_pct'))}.")
    lines += ["", "4. PRZEPŁYWY DO SPOTOWYCH ETF BTC/ETH"]
    for asset, d in flows.items():
        lines.append(f"- {asset}: {d['url']}")
        if "error" in d: lines.append(f"  Niedostępne: {d['error']} (brak danych nie oznacza przepływu 0).")
        else:
            for row in d["rows"][-5:]: lines.append("  " + " | ".join(row))
    lines += ["", "5. KOMENTARZ I SCENARIUSZE", commentary, "", "6. OGRANICZENIA",
              "- Wskaźniki on-chain MVRV, NUPL, SOPR, Puell i LTH/STH nie są w tej wersji pobierane.",
              "- Przepływy ETF z publicznych tabel mogą być niedostępne po zmianie strony.",
              "- Notowania ETF pobierane są przez yfinance i mogą być opóźnione lub niedostępne.",
              "- Raport informacyjny, nie rekomendacja inwestycyjna. Agent nie wykonuje transakcji.",
              "Źródła: CoinGecko API, Yahoo Finance/yfinance, Farside Investors."]
    report = "\n".join(lines)
    txt = OUT / f"raport_{TODAY}.txt"; txt.write_text(report, encoding="utf-8")
    return report, chart, txt

def send_telegram(report, chart):
    token = os.getenv("TELEGRAM_BOT_TOKEN","").strip()
    chat = os.getenv("TELEGRAM_CHAT_ID","").strip()
    if not token or not chat:
        logging.info("Telegram pominięty — brak ustawień"); return
    rest = report
    while rest:
        cut = min(3800, len(rest))
        if cut < len(rest):
            nl = rest.rfind("\n", 0, cut)
            if nl > 1000: cut = nl
        r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                          json={"chat_id":chat,"text":rest[:cut]}, timeout=25)
        r.raise_for_status(); rest = rest[cut:]
    with open(chart,"rb") as f:
        r = requests.post(f"https://api.telegram.org/bot{token}/sendPhoto",
                          data={"chat_id":chat,"caption":f"Wykresy — {TODAY}"},
                          files={"photo":f}, timeout=30)
        r.raise_for_status()

def send_email(report, chart, txt):
    host = os.getenv("SMTP_HOST","").strip(); user = os.getenv("SMTP_USER","").strip()
    password = os.getenv("SMTP_PASSWORD","").strip(); to = os.getenv("EMAIL_TO","").strip()
    sender = os.getenv("EMAIL_FROM",user).strip()
    if not all((host,user,password,to,sender)):
        logging.info("E-mail pominięty — brak ustawień SMTP"); return
    msg = EmailMessage(); msg["Subject"] = f"Raport rynkowy AI — {TODAY}"
    msg["From"] = sender; msg["To"] = to; msg.set_content(report)
    msg.add_attachment(chart.read_bytes(), maintype="image", subtype="png", filename=chart.name)
    msg.add_attachment(txt.read_bytes(), maintype="text", subtype="plain", filename=txt.name)
    with smtplib.SMTP(host, int(os.getenv("SMTP_PORT","587")), timeout=30) as server:
        server.starttls(); server.login(user,password); server.send_message(msg)

if __name__ == "__main__":
    report, chart, txt = build()
    send_telegram(report, chart)
    send_email(report, chart, txt)
    print(report)
