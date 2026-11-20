# HANDOFF — Grafik

Stan: 2026-10-26. **MVP v1 gotowe lokalnie** (backend + panel + NFC + landing), testy 55/55, E2E 12/12 na
stosie Docker. **Produkcja od 28.10: https://grafik.sudomie.pl** (LXC 108, alias `grafik-prod`, `deploy/PROXMOX-HP.md`). Kolejka prac: OpenProject, projekt `grafik`.

## Logowanie kontem sudomie (WDROŻONE 2026-11-20, w `main` od 48063b6, #767)
- Grafik jako KLIENT Konta sudomie (https://konto.sudomie.pl) przez paczkę `core_sso` (agency-platform-core 0.3.0, wheel w
  `backend/vendor/`, instalowany w Dockerfile `--no-deps`; authlib + requests w `requirements.lock`).
- Flaga: puste `OIDC_ISSUER` = brak przycisku, `/oidc/*` → `/panel/`. Z flagą: na ekranie logowania „Zaloguj przez Konto sudomie”
  (flaga `sso` w `/api/public-config/`), komunikaty odmowy wracają przez `/api/session/` (`komunikaty`) i pokazuje je Login.
- Hak ról `core/sso.py` (prawa w docstringu): firma z Konta = Workplace o tym samym uuid; Employee zakładany / rola
  aktualizowana przy każdym logowaniu; w firmie `w_koncie=True` odebrany dostęp = Employee nieaktywny; firm spoza Konta nie rusza;
  zwolnionego w Grafiku nie reaktywuje.
- Nowe pole `Workplace.w_koncie` (migracja `grafik/0xxx_workplace_w_koncie`, addytywna).
- Migracja kont: `manage.py powiaz_konto <login> <sub z Konta> --firma <uuid>` — wiąże istniejące konto (bez nowego konta, stare
  hasło zostaje jako awaryjne) i oznacza firmę jako zarządzaną przez Konto.
- Caddy: `/oidc/*` → backend. Vite: proxy `/oidc/` z `changeOrigin: false` (redirect_uri z Hosta SPA).
- Testy: `core/test_sso.py` (9). Pełny zestaw 89, jedyny błąd = znany #653. E2E lokalnie z Kontem: Marcin wchodzi w swoje
  konto (rola zsynchronizowana), osoba bez dostępu do Grafiku dostaje komunikat, konto nie powstaje.
- Stare zmiany „Grafik jako dostawca” (porzucone, #756): `git stash list` → stash@{0} na gałęzi sso-oidc.
- **Wdrożenie (po zgodzie Konrada):** (1) konto-prod: `klient_oidc grafik https://grafik.sudomie.pl/oidc/callback/` → plik 600;
  (2) dane klienta + `OIDC_ISSUER=https://konto.sudomie.pl/o` do `.env` grafik-prod; (3) push + `deploy/deploy.sh`;
  (4) grafik-prod: `powiaz_konto biuro@przystanekwielbark.pl 2 --firma d8c0be9a-361c-449c-8dbf-8903330cf6ec`; (5) smoke.

## Przyjęcia z Kalendarza na grafiku tygodnia (WDROŻONE 2026-11-20, #759)
- Wiersz „Przyjęcia” pod nagłówkami dni w `panel/Week.tsx` („13:00 Stypa · 40 os. · wstępne”). Pole `events` w `/api/w/<firma>/week/`:
  `null` = brak sekcji (niepodłączone / Kalendarz milczy), lista = przyjęcia (pusta = brak wiersza).
- Serwis `grafik/events.py` (prawa w docstringu, testy `grafik/test_events.py`, 11): token aplikacji z Konta (client credentials,
  scope `api`, `OIDC_ISSUER/token/`, trzymany do wygaśnięcia − 60 s) → `GET KALENDARZ_URL/api/przyjecia?firma=<uuid Workplace>`.
  Tylko firmy `w_koncie=True`. Błąd/timeout (3 s) = `None` + ostrzeżenie w logu, pamiętane 60 s (backpressure); 404 („nie ta firma”)
  bez ostrzeżenia, pamiętane 5 min; dane 5 min w cache.
- Flaga: puste `KALENDARZ_URL` albo brak `KONTO_API_CLIENT_ID` albo `OIDC_ISSUER` = wiersza nie ma. **Zależy od kroku SSO** (OIDC_ISSUER).
- Sprawdzone lokalnie end-to-end bez mocków: Konto (runserver) + Kalendarz (runserver) + Grafik (runserver + Vite) — zrzut
  Playwright, stypa 21.11 w wierszu, następny tydzień bez wiersza, 0 błędów JS.
- **Wdrożenie (po SSO i po zgodzie Konrada):** (1) konto-prod: `manage.py klient_api grafik > /root/klient-api-grafik.env` (600);
  (2) pipe obu linii `KONTO_API_CLIENT_*` do `/opt/grafik/.env` + `KALENDARZ_URL=https://samiswoi.sudomie.pl`; (3) client_id
  do `API_KLIENCI` w `/opt/kalendarz/.env` (samiswoi-prod) i deploy Kalendarza; (4) deploy Grafiku; (5) Workplace Marcina ma
  `w_koncie=True` po `powiaz_konto --firma` (krok SSO); (6) smoke: grafik Marcina, tydzień 16–22.11 → stypa w sobotę.

## Newsletter sudomie przy rejestracji (WDROŻONE 2026-11-12, gałąź newsletter-sudomie, czeka na merge)
- Pole „Chcę dostawać newsletter sudomie” przy rejestracji, domyślnie niezaznaczone. Kod: `backend/core/newsletter.py`, pole w `frontend/src/site/Site.tsx` (PL/EN), flaga `newsletter` w `/api/public-config/`.
- **Flaga:** bez `NEWSLETTER_KLUCZ` w `.env` pola nie ma i nic nie wychodzi. Z kluczem: po zatwierdzeniu rejestracji
  `POST https://sudomie.pl/chat-api/newsletter` (e-mail + IP użytkownika, nagłówek `X-Newsletter-Klucz`); sudomie.pl wysyła link
  potwierdzający i trzyma dowód zgody. Błąd sieci = wpis w logu, rejestracja przechodzi. Tu nic nie zapisujemy w bazie.
- **Wdrożenie:** (1) najpierw `bash ~/Claude/sudomie.pl/scripts/wdroz-klucze-newslettera.sh`; (2) zwykły deploy tej aplikacji;
  (3) do `.env` produkcji dwie linie z `~/.config/sudomie/newsletter-env-dla-aplikacji.txt` (sekcja tej aplikacji) i restart;
  (4) próba: rejestracja z zaznaczonym polem na własny adres → mail „Potwierdź zapis do newslettera sudomie”.
- Testy: `manage.py test core` 31 OK (7 nowych). Uwaga: `grafik.tests.SandboxDemoTests.test_expired_sandbox_disappears_with_its_accounts` pada także bez tych zmian.

## Dokumenty
- `docs/codex-workflow.md` — procedura pracy Codex i przygotowana ścieżka zadania kiosku offline.
- Dostęp Codex do OpenProject: konto `codex` (ID 7), token `~/.config/openproject/codex.token` (600).
  `python3 scripts/openproject.py whoami` / `todo grafik`; zweryfikowane 28.10.2026.
  Konto bez globalnego admina; członkostwo Grafiku i rola globalna skopiowane z konta `claude`.
- `PLAN.md` — ustalenia z userem (§1), role (§2), reguły grafiku/wniosków/NFC (§3–5), poza zakresem (§7), paleta (§9).
- `GLOSSARY.md` — terminy UI (Firma, Dział, Zmiana, Niedyspozycyjność, Wniosek, Punkt odbić, Kiosk, Odbicie…).
- `docs/weryfikacja.md` — bramki, czego nie sprawdzono, **audyt CRUD**.
- `NOTICE.md` + `LICENSE` (MIT) — szkielet z HotelAgenda / Narrative Framework.

## Uruchomienie
- Docker (jak prod): `.env` już jest lokalnie (porty **8095/8456**, bo 8080 i 8090 zajęte). `docker compose up -d --build`
  → http://127.0.0.1:8095. Demo: `docker compose exec -T api python manage.py seed_demo --reset > .seed-links.txt`
  (linki naklejki i kiosku w pliku; hasło kont demo = `DEMO_PASSWORD` z `.env`: `dyrektor-demo`, `kuchnia-kier`, `anna`, `tomek`, `ola`).
- Bez Dockera: `.venv` w katalogu projektu. Backend: `cd backend && DEBUG=1 CSRF_TRUSTED_ORIGINS=http://127.0.0.1:5180 ../.venv/bin/python manage.py runserver 127.0.0.1:8017`;
  front: `cd frontend && API=http://127.0.0.1:8017 npx vite --host 127.0.0.1 --port 5180`. Bez `CSRF_TRUSTED_ORIGINS` logowanie zwraca 403.
- Testy: `cd backend && DEBUG=1 ../.venv/bin/python manage.py test grafik core`; `cd frontend && npm run check`.
- E2E: `cd frontend && CHROME=~/.cache/ms-playwright/chromium-1223/chrome-linux64/chrome BASE=http://127.0.0.1:8095 npm run e2e` — wymaga świeżego `seed_demo --reset > .seed-links.txt`; zrzuty w `frontend/e2e/shots/`.

## Kod
- Backend `backend/grafik/`: `models.py`, `domain.py` (czysta arytmetyka: długość zmiany, sesje z odbić),
  `access.py` (jedyna granica uprawnień), `team.py` (firma, działy, ludzie, loginy, karty, punkty, eksport/usunięcie),
  `schedule.py` (tydzień, zmiany, niedyspozycyjność, wnioski), `clock.py` (naklejka, kiosk, korekty, raport, CSV, „Dziś”),
  `views.py` (cienkie), `tests.py`. `core/` = konta, LoginEvent, regulamin, rejestracja (z HotelAgenda).
- Front `frontend/src/`: `panel/` (Panel, Today, Week, Requests, Time, Team, Away), `tap/` (Tap = `/nfc/<token>`, Kiosk = `/kiosk/<sekret>`),
  `nfc.ts` (Web NFC: zapis naklejki z panelu, odczyt kart na tablecie), `site/` (landing, rejestracja, regulamin).
- API: `/api/workplaces/`, `/api/w/<firma>/…` (departments, employees[/account|/card], unknown-cards, points[/tag|/kiosk],
  week[/copy], shifts, unavailability, requests[/approve|/reject], today, report[.csv], punches[/void]); publiczne `/api/nfc/<token>/`, `/api/kiosk/<sekret>/`.

## Gotcha
- Cache jest w bazie (`DatabaseCache`) — zapisu do cache nie rób w transakcji, którą może wycofać błąd (tak zginęły „nieznane karty”).
- Odbić nie da się zmienić ani usunąć pojedynczo (`PermissionError`); usunięcie firmy kasuje je kaskadą (SQL, bez `delete()`).
- Link naklejki jest publiczny z natury — przy wycieku „Nowy link” w panelu; kiosk ma osobny sekret (sha256 w bazie).
- Czytniki USB różnie podają UID (hex/dziesiętnie) — karty przypisuj z listy „nieznane karty” z tego samego kiosku.
- Strefa czasowa per firma (`Workplace.timezone`); `TIME_ZONE=UTC` w ustawieniach.
- **`ssh host 'bash -s' <<EOF` + `deploy.sh`**: `docker compose exec -T` w środku czyta stdin, czyli resztę heredoca —
  dalsze polecenia znikają bez błędu (28.10). `deploy.sh` uruchamiaj osobnym `ssh … 'cd /opt/grafik && deploy/deploy.sh'`.
- **Demo bez rejestracji** (`grafik/demo.py`): „Wypróbuj demo” = własna kopia Bistro Demo w sesji, konta bez hasła,
  `Workplace.demo_until`; wygasłe usuwa start kolejnego demo (z kontami). Flaga `DEMO_MAX` (0 = przycisk ukryty, kod domyślnie 0;
  produkcja 200), `DEMO_HOURS`, `THROTTLE_DEMO`. Superuser nie widzi piaskownic. `seed_demo` i piaskownica używają `demo.build`.
- **Zaproszenia**: `Employee.invite_hash` (sha256, jednorazowe, `INVITE_DAYS`), publiczne `/api/invite/<token>/` (CSRF + throttle
  `invite` na POST). Kierownik zarządza tylko pracownikami (rola pracownik) swojego działu — reguła w `team.manageable`.
  `seed_demo` na serwerze (`DEBUG=0`) wymaga `DEMO_PASSWORD` — zapasowe hasło jest w publicznym repo.
- **PL/EN**: polski tekst = klucz. Front: `t("…")` + wpis w `frontend/src/en.ts` (`npm run check` pada bez wpisu, z martwym wpisem
  albo z innymi `{param}`). Backend: komunikat `DomainError("… {x} …", x=…)` / `tr("…")` + wpis w `grafik/data/en.json`
  (test `core.tests.EnglishTests` skanuje kod). Język = ciasteczko `django_language` (przełącznik) → `LocaleMiddleware`.
  Regulamin EN (`regulamin.en.html`) jest tłumaczeniem — wiąże PL, akceptacja zapisuje hash PL; zmiana PL = popraw EN.
  E2E w PL wymusza `locale: "pl-PL"` (headless Chromium ma en-US, a język idzie za przeglądarką).

## Do wdrożenia (czeka na usera)
1. ~~Wdrożenie~~ — zrobione 28.10. Aktualizacja: `deploy/push.sh grafik-prod:/opt/grafik` → `ssh grafik-prod 'cd /opt/grafik && deploy/deploy.sh'` → `deploy/smoke.sh https://grafik.sudomie.pl`. Zostaje rezerwacja DHCP (router).
2. Sekcja `#grafik` w polityce prywatności sudomie.pl (link w stopce i regulaminie już na nią wskazuje).
3. Przegląd regulaminu (`backend/grafik/data/regulamin.html`, § 2 ust. 2 o ewidencji czasu pracy, § 8 powierzenie).
4. Test na prawdziwych naklejkach NTAG213 i czytniku USB.

## Repo
- https://github.com/AltKorin/Grafik (publiczne, MIT), gałąź `main`. Commit/push tylko na prośbę usera.

## Podlinkowanie sudomie — 2026-10-28

Wdrożono stopkę publicznych stron z wygenerowanej listy frontend/src/site/sudomie.ts, PL/EN i link katalogu w bieżącym języku. Poprawiono min-width figury z tabelą demo na telefonie. Build, time.check, i18n.check (388), smoke 10/10, produkcja PL/EN 390/1440 px OK.

Podlinkowanie Grafiku ukończone. Kolejka dalszej pracy pozostaje w OpenProject; temat kiosku offline nie był realizowany. Zadanie źródłowe: [473](https://projekty.sudomie.pl/work_packages/473).
