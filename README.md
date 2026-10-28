# Grafik

*[English below](#english)*

Darmowy grafik pracy i ewidencja czasu pracy z odbiciami NFC — dla małych firm (restauracja, hotel, sklep).

- **Grafik** — siatka osoby × dni tygodnia, działy z kierownikami, kopiowanie tygodnia, druk.
- **Niedyspozycyjność** — urlop, L4, niedostępność; blokuje wpisanie zmiany.
- **Wnioski** — zamiana, odwołanie, inne godziny, dodatkowa zmiana; akceptacja kierownika od razu zmienia grafik.
- **NFC, dwa tryby**
  - naklejka NFC przy wejściu + telefon pracownika (`/nfc/<token>`),
  - tablet-kiosk z czytnikiem USB lub Web NFC i kartami/brelokami (`/kiosk/<sekret>`).
- **Czas pracy** — plan vs odbicia za miesiąc, „do wyjaśnienia”, korekty z powodem (odbić nie da się edytować), eksport CSV.
- Polski i angielski (przełącznik PL/EN; język przeglądarki na start).
- RODO: eksport danych firmy, usunięcie firmy, historia zmian (simple-history) i dziennik logowań.

## Stos

Django 6.1 + DRF, PostgreSQL 17, React 19 + Vite, Caddy, Docker Compose.

## Uruchomienie

```sh
cp .env.example .env        # uzupełnij DJANGO_SECRET_KEY, HTTP_PORT, DEMO_PASSWORD
docker compose up -d --build
docker compose exec -T api python manage.py seed_demo --reset > .seed-links.txt
```

Panel: `http://127.0.0.1:<HTTP_PORT>/panel`. Linki naklejki i kiosku dla danych demo są w `.seed-links.txt`.

Testy: `cd backend && DEBUG=1 python manage.py test grafik core`, `cd frontend && npm run check`.

Więcej: `PLAN.md` (reguły), `GLOSSARY.md` (słownik), `docs/weryfikacja.md` (bramki i audyt), `deploy/` (wdrożenie).

## Licencja

MIT — zob. `LICENSE` i `NOTICE.md`.

---

## English

Free staff scheduling and working-time tracking with NFC punches — for small businesses (restaurants, hotels, shops).
The interface is available in Polish and English (PL/EN switch; the browser language is the default).

- **Schedule** — people × days of the week, departments with managers, copy last week, print.
- **Unavailability** — leave, sick leave, unavailable; blocks scheduling a shift on those days.
- **Requests** — swap, cancellation, different hours, extra shift; the manager's approval changes the schedule at once.
- **NFC, two ways** — an NFC sticker at the entrance + the employee's own phone (`/nfc/<token>`), or a kiosk tablet with a
  USB / Web NFC reader and cards or key fobs (`/kiosk/<secret>`).
- **Working time** — plan vs. punches per month, items to check, corrections with a reason (punches are never edited), CSV export.
- GDPR: company data export and deletion, change history (simple-history) and a login log.

Stack: Django 6.1 + DRF, PostgreSQL 17, React 19 + Vite, Caddy, Docker Compose. Run it with the commands above
(`cp .env.example .env`, `docker compose up -d --build`, `seed_demo`). Licence: MIT.

Translations: the Polish text is the key; English lives in `frontend/src/en.ts` (UI) and `backend/grafik/data/en.json`
(API messages, labels, CSV). `npm run check` and the backend tests fail when a text has no English entry.
