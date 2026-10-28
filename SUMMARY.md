# SUMMARY — Grafik

## Sesja 2026-10-28 — przygotowanie Codex do OpenProject
### Zrobiono
- Przeczytano nadrzędny `CLAUDE.md`, zasady komunikacji i dokumentację Grafiku oraz OpenProject.
- Utworzono aktywne konto `codex` (ID 7), bez globalnego administratora, z dostępem do Grafiku
  i rolą globalną wzorowaną na istniejącym koncie agenta. Osobny token zapisano poza repo (600).
- Dodano `scripts/openproject.py` oraz `docs/codex-workflow.md`: procedura sesji, blokady,
  plan realizacji [kiosku offline](https://projekty.sudomie.pl/work_packages/427) i kryteria odbioru.
### Zadziałało
- API `/users/me` potwierdziło `codex`, ID 7; odczyt kolejki zwrócił pięć otwartych zadań.
- Tworzenie konta i członkostw w transakcji zapobiegło częściowej konfiguracji po błędzie.
### Nie zadziałało
- Sandbox blokował DNS klienta i uruchomienie SSH; dostęp wykonano po eskalacji uprawnień.
- Model User w tej wersji OpenProject nie ma `mail_notification=`. Usunięto nieobsługiwane
  ustawienie i ponowiono transakcję; konto powstało poprawnie.
### Następne kroki
- Gotowa procedura pozwala zaczynać kolejne sesje od kolejki OpenProject. Przy przeglądzie
  pierwszym „Nowy” był kiosk offline; cztery pozostałe sprawy czekały na Konrada.
  Implementacji kiosku w tej sesji nie rozpoczynano.
- Adapter nadal wymaga wspólnego `~/Claude/OpenProject/op.py` i jego lokalnego pliku
  `claude.token` przy imporcie, ale każde żądanie wysyła z tokenem Codex.

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
  `EnglishTests` (backend, skan AST), E2E krok EN (szuka polskich liter na każdej stronie). Wdrożone po zgodzie usera
  (testy na serwerze 62/62, smoke OK, EN sprawdzone na żywo), commit acabce9.
### Zadziałało (EN)
- Natywny `LocaleMiddleware` + ciasteczko `django_language` z przełącznika: link do CSV, regulamin i błędy walidatorów
  Django same wychodzą po angielsku, bez nagłówków w każdym zapytaniu.
- Skan AST w teście zamiast ręcznej listy — znalazł komunikaty z `"…" if … else "…"`, które pierwsza wersja pomijała.
### Nie zadziałało (EN)
- Pierwszy krok EN w E2E skanował strony panelu, zanim doszły dane (trasa po stronie klienta, `networkidle` mijał od razu) —
  test był zielony na pustych stronach. Teraz czeka na odpowiedź API i treść.
- `copy_week` zwracał pominięte zmiany przez `str(error)` — zawsze po polsku; teraz przez `error_body`.
- Zaproszenia: kierownik ma zakładkę „Zespół” (pracownicy swojego działu: dodaj, zmień, usuń/archiwizuj, login, karta,
  zaproszenie). Zaproszenie = jednorazowy link `/zaproszenie/<token>` (sha256 w bazie, 7 dni), kopiuj / udostępnij / QR;
  pracownik sam ustawia login i hasło i jest od razu zalogowany. `seed_demo` na serwerze wymaga `DEMO_PASSWORD`.
  Testy 68/68 (SQLite + Postgres), `i18n.check` 376 tekstów, E2E 14/14. Lokalnie gotowe; wdrożenie i demo na produkcji
  zablokowane przez tryb uprawnień — czeka na zgodę usera (OpenProject).
### Zadziałało (zaproszenia)
- Jedna reguła `team.manageable` dla wszystkich akcji na osobie — kierownik dostał uprawnienia bez rozsiewania warunków.
- Bramka EN od razu wyłapała nowe teksty bez tłumaczenia i martwe wpisy po usuniętym polu „Login (opcjonalnie)”.
### Nie zadziałało (zaproszenia)
- „Błąd DRF po angielsku” okazał się artefaktem testu (ciasteczko `en` wysłane ręcznie) — w PL DRF już mówi po polsku.
- E2E: `check()` na przycisku wyboru w `Segmented` czekał w nieskończoność (radio ukryte, klika się etykietę).
- Zaproszenia + Bistro Demo wdrożone na produkcję (commit ec1f5fd; dane demo w /root/grafik-demo.txt).
- Demo bez rejestracji: przycisk „Wypróbuj demo” na stronie głównej — każdy odwiedzający dostaje własną kopię firmy
  przykładowej na 24 h, „Zobacz jako: dyrektor / kierownik / pracownik”, kiosk w nowej karcie, odbicie telefonem.
  Limit kopii (`DEMO_MAX`, 503 ponad limit), throttle na IP, konta bez haseł, z demo nie da się założyć prawdziwej firmy,
  superuser nie widzi piaskownic. Testy 73/73, E2E 15/15.
### Nie zadziałało (demo)
- `ssh host 'bash -s' <<EOF` z `deploy.sh` w środku: `docker compose exec -T` zjadł resztę skryptu — seed się nie wykonał, bez błędu.
- Bramka EN skanowała stałą listę plików — nowy `grafik/demo.py` by się prześlizgnął; dopisany do listy (lista jest w teście).

## Sesja 2026-10-28 — podlinkowanie sudomie
### Zrobiono
- Wdrożono stopkę publicznych stron z wygenerowanej listy frontend/src/site/sudomie.ts, PL/EN i link katalogu w bieżącym języku. Poprawiono min-width figury z tabelą demo na telefonie.
### Zadziałało
- Build, time.check, i18n.check (388), smoke 10/10, produkcja PL/EN 390/1440 px OK.
### Nie zadziałało / ograniczenia
- Stary obraz działającego web nie był dostępny do tagowania; zachowano jego /srv i Caddyfile, następnie wdrożono nowy frontend.
### Następne kroki
- Podlinkowanie Grafiku ukończone. Kolejka dalszej pracy pozostaje w OpenProject; temat kiosku offline nie był realizowany. Zadanie źródłowe: [473](https://projekty.sudomie.pl/work_packages/473).
