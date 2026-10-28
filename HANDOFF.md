# HANDOFF — Grafik

Stan: 2026-10-26. **MVP v1 gotowe lokalnie** (backend + panel + NFC + landing), testy 55/55, E2E 12/12 na
stosie Docker. **Nie wdrożone.** Kolejka prac: OpenProject, projekt `grafik`.

## Dokumenty
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

## Do wdrożenia (czeka na usera)
1. LXC na proxmox-hp + domena `grafik.sudomie.pl` + tunel Cloudflare (wzór: HotelAgenda `deploy/PROXMOX-HP.md`; `deploy/push.sh`, `deploy/deploy.sh`, `deploy/env.production.example`).
2. Sekcja `#grafik` w polityce prywatności sudomie.pl (link w stopce i regulaminie już na nią wskazuje).
3. Przegląd regulaminu (`backend/grafik/data/regulamin.html`, § 2 ust. 2 o ewidencji czasu pracy, § 8 powierzenie).
4. Test na prawdziwych naklejkach NTAG213 i czytniku USB.

## Repo
- https://github.com/AltKorin/Grafik (publiczne, MIT), gałąź `main`. Commit/push tylko na prośbę usera.


