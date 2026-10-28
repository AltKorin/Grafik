# Weryfikacja — Grafik (2026-10-26)

## Czym sprawdzone

| Bramka | Wynik | Jak uruchomić |
| --- | --- | --- |
| Testy backendu (SQLite) | 73/73 (w tym kompletność EN) | `cd backend && DEBUG=1 ../.venv/bin/python manage.py test grafik core` |
| Testy backendu (PostgreSQL, kontener) | 73/73 | `docker compose exec -T api python manage.py test grafik core` |
| Czyste reguły czasu we froncie + kompletność EN (`i18n.check`, 387 tekstów) | OK | `cd frontend && npm run check` |
| Build frontu (tsc + vite) | OK | `npm run build` |
| E2E w Chromium (12 kroków) — Vite dev | 12/12 | `CHROME=… BASE=http://127.0.0.1:5180 npm run e2e` |
| E2E na stosie Docker (Caddy + CSP + Postgres), w tym zaproszenie, demo bez rejestracji i przejście EN | 15/15 | `CHROME=… BASE=http://127.0.0.1:8095 npm run e2e` |
| Smoke z zewnątrz | OK (8/8, bez HTTPS) | `deploy/smoke.sh http://127.0.0.1:8095` |
| `check --deploy` | 0 błędów (5 ostrzeżeń = brak HTTPS lokalnie) | w kontenerze |

E2E zmienia dane demo → potem `docker compose exec -T api python manage.py seed_demo --reset > .seed-links.txt`.

## Czego NIE sprawdzono

- **Prawdziwe NFC**: naklejka NTAG z zapisanym linkiem na iPhonie i Androidzie, czytnik USB (format UID!),
  Web NFC na tablecie z Androidem. E2E symuluje czytnik USB klawiaturą i otwiera link naklejki wprost.
- Produkcja (domena, tunel, HTTPS, ciasteczka Secure) — nie wdrożone.
- Wygląd na prawdziwym telefonie/tablecie (tylko emulowane rozmiary w Chromium).

## Błędy znalezione w tej sesji

- E2E: nieznana karta z kiosku nigdy nie trafiała do panelu — zapis do cache (w bazie) był w transakcji,
  którą wycofywał błąd 404. Testy jednostkowe nie złapały, bo używają cache w pamięci. Poprawka w
  `clock.kiosk_punch` + test regresyjny z `DatabaseCache`.
- Zatwierdzenie wniosku „odwołanie” wywalało `save()` na usuniętej zmianie — poprawione w `schedule.apply`.

## Audyt CRUD w panelu klienta (CLAUDE.md)

| Rzecz | Lista | Dodaj | Zmień | Usuń | Gdzie |
| --- | --- | --- | --- | --- | --- |
| Firma | przełącznik firm | rejestracja; „Załóż kolejną firmę” (Firma) i formularz na pustym panelu konta bez firmy | nazwa, strefa | z potwierdzeniem nazwą + eksport przed | Zespół i NFC → Firma |
| Dział | ✓ (liczba osób) | ✓ | nazwa, kolor | ✓ — blokada z nazwiskami, gdy są w nim osoby | Zespół i NFC |
| Pracownik | ✓ | ✓ (z loginem lub bez) | imię, dział, rola, aktywny | ✓ — z odbiciami → archiwum (ewidencja zostaje), bez → usunięcie | Zespół i NFC |
| Login pracownika | w liście | ✓ (hasło pokazane raz) | nowe hasło | odbierz logowanie | okno pracownika (dyrektor; kierownik — swój dział) |
| Zaproszenie (link) | w liście („zaproszenie do …”) | ✓ przy dodaniu albo w oknie osoby (link + QR + udostępnij, raz) | nowy link (stary przestaje działać) | anuluj zaproszenie | Zespół (dyrektor i kierownik) |
| Karta NFC | w liście (…4 znaki) | ✓ z „nieznanych kart” kiosku lub ręcznie | odbierz + przypisz | odbierz kartę | okno pracownika |
| Punkt odbić | ✓ (QR, link, liczba odbić) | ✓ | nazwa, nowy link naklejki | ✓ z potwierdzeniem (odbicia zostają) | Zespół i NFC |
| Kiosk punktu | stan | włącz (link raz) | nowy link | wyłącz | Zespół i NFC |
| Zmiana | siatka tygodnia | „+” w komórce, kopiuj tydzień | ✓ wszystkie pola | ✓ z potwierdzeniem | Grafik |
| Niedyspozycyjność | Dziś (swoja), siatka (zespół) | ✓ sam / kierownik za osobę | ✓ wszystkie pola | ✓ (historia zostaje) | Dziś, Grafik |
| Wniosek | ✓ moje / do rozpatrzenia / rozpatrzone | ✓ | ✓ dopóki czeka | wycofaj | Wnioski |
| Odbicie | ✓ w oknie osoby (Czas pracy) | dopisz korektę z powodem | — (niezmienialne: anuluj + dopisz) | anuluj z powodem (zostaje przekreślone) | Czas pracy |

Dziura „druga firma dla istniejącego konta” zamknięta 28.10 (`POST /api/workplaces/`, limit `MAX_FIRMS_PER_ACCOUNT`, testy `NewFirmTests`).
