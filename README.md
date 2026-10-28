# Grafik

Darmowy grafik pracy i ewidencja czasu pracy z odbiciami NFC — dla małych firm (restauracja, hotel, sklep).

- **Grafik** — siatka osoby × dni tygodnia, działy z kierownikami, kopiowanie tygodnia, druk.
- **Niedyspozycyjność** — urlop, L4, niedostępność; blokuje wpisanie zmiany.
- **Wnioski** — zamiana, odwołanie, inne godziny, dodatkowa zmiana; akceptacja kierownika od razu zmienia grafik.
- **NFC, dwa tryby**
  - naklejka NFC przy wejściu + telefon pracownika (`/nfc/<token>`),
  - tablet-kiosk z czytnikiem USB lub Web NFC i kartami/brelokami (`/kiosk/<sekret>`).
- **Czas pracy** — plan vs odbicia za miesiąc, „do wyjaśnienia”, korekty z powodem (odbić nie da się edytować), eksport CSV.
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
