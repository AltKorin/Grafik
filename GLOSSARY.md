# Słownik — Grafik

Język UI i rozmów z klientem. Kod po angielsku (w nawiasie). UI po polsku i po angielsku (kolumna EN — te same słowa w `frontend/src/en.ts` i `backend/grafik/data/en.json`).

| Termin | EN (UI) | Znaczenie |
| --- | --- | --- |
| **Firma** (`Workplace`) | Company | Klient: restauracja, hotel, sklep. Jedno konto Grafiku = jedna firma (osoba może należeć do kilku). |
| **Dział** (`Department`) | Department | Zespół w firmie: kuchnia, sala, recepcja. Ma kolor w grafiku. |
| **Pracownik** (`Employee`) | Employee | Osoba w grafiku. Login opcjonalny (osoba tylko z kartą go nie ma). |
| **Dyrektor / kierownik działu / pracownik** | Director / department manager / employee | Role — zob. PLAN.md §2. |
| **Zmiana** (`Shift`) | Shift | Godziny pracy osoby w dniu, od–do; może kończyć się następnego dnia. |
| **Grafik** | Schedule | Siatka osoby × dni tygodnia. |
| **Niedyspozycyjność** (`Unavailability`) | Unavailability | Urlop, L4 albo niedostępność — zgłaszana bez akceptacji, blokuje zmiany. |
| **Wniosek** (`ChangeRequest`) | Request | Prośba o zamianę, odwołanie, inne godziny lub dodatkową zmianę; przyjmuje kierownik. |
| **Punkt odbić** (`ClockPoint`) | Clock point | Wejście do pracy: naklejka NFC i/lub kiosk. |
| **Naklejka NFC** | NFC sticker | Tag z linkiem punktu; pracownik przykłada swój zalogowany telefon. |
| **Zaproszenie** (`invite_hash`) | Invitation | Jednorazowy link, który kierownik wysyła pracownikowi; pracownik sam ustawia login i hasło. |
| **Kiosk** | Kiosk | Tablet przy wejściu: karta/brelok przy czytniku. Link z sekretem, pokazywany raz. |
| **Odbicie** (`Punch`) | Punch (clock-in / clock-out) | Zdarzenie wejście / wyjście. Niezmienialne. |
| **Korekta** | Correction | Odbicie dopisane przez kierownika (z powodem) albo anulowanie pomyłki (z powodem). |
| **Do wyjaśnienia** | To check | Brak wyjścia lub wyjście bez wejścia w zestawieniu. |
| **Czas pracy** | Working time | Zestawienie miesiąca: plan z grafiku vs przepracowane z odbić. |
