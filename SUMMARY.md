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
- Zostało niewdrożone: produkcja na proxmox-hp, polityka prywatności `#grafik`, przegląd regulaminu, test na prawdziwych naklejkach i czytniku — zadania w OpenProject (`grafik`).
