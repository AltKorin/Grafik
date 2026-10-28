# SUMMARY — Grafik

## Sesja 2026-10-26
### Zrobiono
- Nowy projekt `~/Claude/Grafik` jako darmowe narzędzie na wzór HotelAgenda: szkielet (Django 6.1 + DRF, React 19 + Vite,
  Caddy, Postgres, Docker, rejestracja, regulamin, RODO, deploy) skopiowany i oczyszczony z domeny agendy.
- Domena `grafik`: firma, działy, pracownicy (login opcjonalny, karta NFC), zmiany, niedyspozycyjność, wnioski
  (zamiana/odwołanie/godziny/dodatkowa), punkty odbić (naklejka + kiosk), odbicia jako niezmienialne zdarzenia, raport + CSV.
- Panel: Dziś, Grafik (siatka osoby × dni), Wnioski, Czas pracy, Zespół i NFC; strony `/nfc/<token>` (telefon) i `/kiosk/<sekret>` (tablet).
- Paleta ze Słownika Kolorów (202 + akcent 033), landing z przykładowym grafikiem.
- Testy 55 (backend), `time.check`, E2E 12 kroków (dev i Docker), smoke.
### Zadziałało
- Kopia szkieletu HotelAgenda zamiast budowy od zera — rejestracja, regulamin, LoginEvent, deploy przeszły prawie bez zmian.
- Odbicia jako zdarzenia + liczenie godzin od nowa: korekta i anulowanie bez edycji danych, raport zawsze spójny.
- Serwer decyduje wejście/wyjście + 60 s „powtórki” — jedna naklejka, jeden przycisk, brak podwójnych odbić.
- E2E na prawdziwym stosie (Caddy, CSP, Postgres) znalazło błąd, którego testy jednostkowe nie widziały.
### Nie zadziałało
- Pierwsza wersja zapisywała „nieznane karty” do cache w bazie wewnątrz transakcji wycofywanej przez 404 — panel nigdy ich nie widział (poprawione + test).
- Zatwierdzenie wniosku „odwołanie” wywalało zapis (wniosek trzymał w pamięci usuniętą zmianę) — poprawione.
- Kod Shift_Manager z GitHuba nie nadawał się do przeniesienia (`Shift.save()` wcięte poza klasą — scalanie i historia martwe); wzięte tylko wymagania.
### Następne kroki
- 2026-10-28: repo wypchnięte jako publiczne AltKorin/Grafik (#428 zamknięte).
- Zostało niewdrożone: produkcja na proxmox-hp, polityka prywatności `#grafik`, przegląd regulaminu, test na prawdziwych naklejkach i czytniku — zadania w OpenProject (`grafik`).

## Sesja 2026-10-28
### Zrobiono
- Publiczne repo https://github.com/AltKorin/Grafik (README, poprawiony `.gitignore`).
- Produkcja https://grafik.sudomie.pl: LXC 108 (`deploy/lxc-create.sh` — jedna komenda Konrada na hypervisorze,
  klucz deploy wbudowany), `.env` z sekretami z serwera, `deploy.sh` (testy 55/55 na serwerze), tunel `grafik`
  z terminala, smoke HTTPS 10/10, admin `konrad`, cron backupu + pierwszy backup.
### Zadziałało
- Skrypt LXC z wbudowanym kluczem publicznym — Konrad wkleja jedną linię zamiast trzech kroków.
- `tunnel login` zostawiony na 10 min: cloudflared sam ściągnął `cert.pem` na serwer, bez pobierania w przeglądarce.
### Nie zadziałało
- Pierwszy `tunnel login` ubity `timeout 25` po wyciągnięciu linku — autoryzacja przepadła, przeglądarka nic nie pobrała.
- Wpis crona nie zapisał się przy pierwszym podejściu (na świeżym LXC nie było pakietu `cron`) — doinstalowany, wpis ponowiony.
- Backup bazy powstawał z prawami 644 (dane osobowe czytelne dla każdego konta) — `umask 077` w `backup.sh`; ten sam problem jest w HotelAgenda.
### Następne kroki
- Rezerwacja DHCP dla LXC 108 na routerze; polityka prywatności `#grafik`, przegląd regulaminu, test prawdziwego NFC — OpenProject.
- Po wdrożeniu: „Załóż firmę” dla zalogowanego konta (pusty panel nie jest już ślepą uliczką) — wdrożone, commit a124892.
- Wersja angielska całości (PL/EN): panel, strona, rejestracja, regulamin (tłumaczenie, wiąże PL), kiosk, naklejka,
  komunikaty API, etykiety, CSV. Wzorzec z Narrative Framework (polski tekst = klucz). Bramki: `i18n.check` (front),
  `EnglishTests` (backend, skan AST), E2E krok EN (szuka polskich liter na każdej stronie). Lokalnie zielone; **na produkcję
  nie poszło** — wdrożenie zablokowane przez tryb uprawnień, czeka na zgodę usera.
### Zadziałało (EN)
- Natywny `LocaleMiddleware` + ciasteczko `django_language` z przełącznika: link do CSV, regulamin i błędy walidatorów
  Django same wychodzą po angielsku, bez nagłówków w każdym zapytaniu.
- Skan AST w teście zamiast ręcznej listy — znalazł komunikaty z `"…" if … else "…"`, które pierwsza wersja pomijała.
### Nie zadziałało (EN)
- Pierwszy krok EN w E2E skanował strony panelu, zanim doszły dane (trasa po stronie klienta, `networkidle` mijał od razu) —
  test był zielony na pustych stronach. Teraz czeka na odpowiedź API i treść.
- `copy_week` zwracał pominięte zmiany przez `str(error)` — zawsze po polsku; teraz przez `error_body`.
