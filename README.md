# Agent AI — codzienny raport ETF i kryptowalut

Raport po polsku, codziennie o 07:30, z wykresami i wysyłką przez Telegram oraz e-mail. Program nie ma funkcji handlowych i nie wykonuje transakcji.

## Zakres wersji bazowej
- ETF-y akcyjne: domyślnie VWCE.DE, EUNL.DE, SXR8.DE, IWDA.AS (można zmienić w `.env`).
- BTC i ETH: cena, zmiany 24 h / 7 dni / 30 dni, średnie 50 i 200 dni, RSI(14), średnia 200 tygodni, obsunięcie od maksimum z 2 lat.
- Przepływy do spotowych ETF BTC i ETH z publicznych tabel Farside, o ile źródło daje się odczytać.
- Wykres PNG, raport TXT i dane JSON.
- Opcjonalny komentarz przez OpenAI API; bez klucza generowany jest komentarz regułowy.

**Ograniczenie:** MVRV, NUPL, SOPR, Puell Multiple oraz dane LTH/STH nie są w tej wersji pobierane. Wymagają dodatkowego dostawcy danych on-chain, klucza API i sprawdzenia licencji. Brak danych nie jest zastępowany zgadywaniem.

## Instalacja (Windows)
1. Zainstaluj Python 3.11+.
2. Rozpakuj archiwum, otwórz PowerShell w katalogu projektu.
3. Uruchom:
   ```powershell
   py -m venv .venv
   .\\.venv\\Scripts\\Activate.ps1
   pip install -r requirements.txt
   ```
4. Skopiuj `.env.example` do `.env`, uzupełnij ustawienia i uruchom:
   ```powershell
   python run_report.py
   ```

## Telegram
1. W Telegramie otwórz `@BotFather`, użyj `/newbot` i zapisz token.
2. Otwórz rozmowę z botem i naciśnij Start.
3. Odczytaj `chat_id`, wysyłając wiadomość do bota i sprawdzając `https://api.telegram.org/bot<TOKEN>/getUpdates`.
4. Wpisz `TELEGRAM_BOT_TOKEN` oraz `TELEGRAM_CHAT_ID` do `.env`. Nie udostępniaj tokenu.

## E-mail
Wpisz ustawienia SMTP w `.env`. Dla Gmaila użyj hasła aplikacji, nie zwykłego hasła do konta. Dla innych usług użyj oficjalnych parametrów SMTP danego dostawcy.

## Dane i klucze
- CoinGecko Demo API: zalecany bezpłatny klucz, limity i warunki mogą się zmieniać.
- ETF-y: prototyp pobiera notowania przez bibliotekę `yfinance`; to wygodne rozwiązanie osobiste, ale nie gwarantuje jakości ani dostępności danych. Dla większej niezawodności należy podłączyć licencjonowane API.
- Przepływy ETF: publiczne tabele Farside; parsowanie może przestać działać po zmianie strony.
- OpenAI: opcjonalny klucz API, koszt zależy od wybranego modelu i zużycia. Bez klucza raport nadal powstaje.
- Telegram i kod: bez opłat za typowe użytkowanie. Hosting: 0 zł na stale włączonym komputerze; VPS jest dodatkowo płatny. Dane on-chain premium mogą kosztować dodatkowo.

## Automatyczne uruchamianie o 07:30 czasu polskiego
Windows: otwórz Harmonogram zadań, utwórz zadanie codzienne na 07:30, wskaż `python.exe` ze środowiska `.venv`, jako argument podaj pełną ścieżkę do `run_report.py`, a „Rozpocznij w” ustaw na katalog projektu. Komputer musi być włączony. Na serwerze skonfiguruj `cron` lub timer w strefie `Europe/Warsaw`; nie ustawiaj stałej godziny UTC bez uwzględnienia zmiany czasu.

## Zastrzeżenie
Raport ma charakter informacyjny, nie stanowi rekomendacji inwestycyjnej. Wskaźniki techniczne i cykl czteroletni nie przewidują przyszłości z pewnością. Przed użyciem sprawdź poprawność danych i dostarczenie wiadomości.

## Wariant bez instalowania Pythona: GitHub Actions

Projekt zawiera plik `.github/workflows/daily-report.yml`. GitHub uruchamia skrypt w chmurze codziennie o 07:30 w strefie `Europe/Warsaw`; nie trzeba instalować Pythona na własnym komputerze. Raport można też uruchomić ręcznie z zakładki Actions.

### Prywatność i koszty
- Najprostszy bezpłatny wariant używa publicznego repozytorium, więc kod będzie publicznie widoczny. Sekrety dodane w ustawieniach GitHub nie są pokazywane w kodzie.
- **Nigdy nie przesyłaj pliku `.env` do GitHub.** Wgrywaj `.env.example`, a nie `.env`.
- Nie wpisuj tokenu Telegrama ani kluczy API do plików programu lub README.
- Bez klucza OpenAI raport korzysta z komentarza regułowego; nie ma wtedy opłaty za model językowy.
- Standardowe uruchomienia GitHub-hosted runners w publicznych repozytoriach są bezpłatne. Harmonogram może czasami się opóźnić, a w publicznych repozytoriach może zostać wyłączony po 60 dniach bez aktywności.
- Wskaźniki on-chain MVRV/NUPL/SOPR/Puell nie są dostępne w tej wersji bez dodatkowego źródła danych.

### Konfiguracja przez stronę GitHub
1. Zaloguj się na https://github.com.
2. Utwórz repozytorium (`New repository`) i wybierz `Public`, jeśli chcesz korzystać z bezpłatnych standardowych uruchomień. Nie dodawaj pliku `.env`.
3. Wgraj zawartość folderu projektu przez `Add file` → `Upload files`. Wgraj `.github/workflows/daily-report.yml`, `run_report.py`, `requirements.txt`, `README.md` i `.env.example`; **nie wgrywaj `.env`**.
4. Przejdź do `Settings` → `Secrets and variables` → `Actions` → `New repository secret`.
5. Dodaj sekrety `TELEGRAM_BOT_TOKEN` i `TELEGRAM_CHAT_ID`, używając swoich wartości.
6. Opcjonalnie dodaj `COINGECKO_API_KEY`, jeśli masz klucz CoinGecko Demo.
7. Otwórz `Actions`, wybierz `Codzienny raport rynkowy` i kliknij `Run workflow`, aby wykonać test.
8. Sprawdź Telegram. Jeśli raport dotrze, automatyczny harmonogram jest skonfigurowany.

Jeśli token trafi do publicznego repozytorium, natychmiast unieważnij go w BotFather i wygeneruj nowy.
