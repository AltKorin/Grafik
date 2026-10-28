# PLAN — Grafik

Darmowe narzędzie (freeware, jak Agenda hotelowa) dla małych firm: grafik pracy zespołu + rejestracja
czasu pracy przez NFC. Stan: MVP v1, 2026-10-26.

## 1. Ustalenia (user, 2026-10-26)

- Źródła: repo GitHub `AltKorin/Shift_Manager` (katalog `Grafik/` — Django, wnioski o zamianę) oraz spec
  InnDesk `docs/superpowers/specs/2026-09-10-staff-schedule-design.md` (dowolne godziny, niedyspozycyjność,
  kierownik działu). Kod Shift_Manager **nie** jest kopiowany — przepisany na wzór HotelAgenda
  (jego `Shift.save()` był wcięty na poziomie modułu, więc scalanie i historia nigdy się nie wykonywały).
- Stos: **kopia szkieletu HotelAgenda** — Django 6.1 + DRF, React 19 + Vite, Caddy, Postgres, Docker,
  rejestracja, regulamin, RODO, deploy na ProxMox + Cloudflare Tunnel.
- NFC: **oba tryby** — naklejka NFC + telefon pracownika (zalogowany) oraz kiosk (tablet + czytnik USB
  albo Web NFC na Androidzie) z kartami/brelokami.
- Zakres v1: siatka osoby × dni, niedyspozycyjność, wnioski o zamianę, raport godzin (CSV), działy i kierownicy.

## 2. Role

| Rola | Może |
| --- | --- |
| dyrektor | wszystko: zespół, działy, punkty NFC, firma, grafik i korekty wszystkich |
| kierownik | grafik, wnioski i korekty odbić osób ze **swojego** działu; zakładka „Zespół”: dodaje pracowników (tylko rola pracownik, tylko swój dział), wysyła im zaproszenia, nadaje loginy i karty (od 28.10) |
| pracownik | widzi grafik swojego działu, zgłasza swoją niedyspozycyjność, składa wnioski, widzi swój czas |
| admin (superuser) | jak dyrektor w każdej firmie — tylko serwis |

Inna firma → 404 (bez wycieku istnienia); brak uprawnienia w swojej firmie → 403 ze zdaniem, kto może.
Kierownik nie widzi osób z innych działów (404, nie 403).

## 3. Grafik

- Zmiana = dowolne godziny od–do; koniec ≤ początek = kończy się następnego dnia.
- **Blokady przy zapisie** (też przy kopiowaniu tygodnia i akceptacji wniosku):
  1. zgłoszona niedyspozycyjność tej osoby w ten dzień → 409 z treścią „poproś o wycofanie zgłoszenia”,
  2. nakładanie się z inną zmianą tej osoby (także przez północ) → 409.
- Niedyspozycyjność (urlop / L4 / niedostępność) bez akceptacji, widoczna od razu. Zgłoszenie na dni
  z już zaplanowaną zmianą przechodzi, ale zwraca listę konfliktów (kierownik widzi chip z czerwonym obramowaniem).
  `simple-history` trzyma dowód zgłoszenia także po jego usunięciu (wymóg z InnDesk spec, pkt 6).
- „Skopiuj poprzedni tydzień” — tylko osoby, którymi wołający zarządza; konflikty pomijane i nazwane.

## 4. Wnioski

Rodzaje: zamiana (moja zmiana ↔ zmiana osoby z działu), odwołanie, inne godziny, dodatkowa zmiana.
Akceptacja kierownika wykonuje zmianę w grafiku **w tej samej transakcji** z tymi samymi blokadami;
konflikt → 409 i nic się nie zmienia (wniosek dalej „czeka”). Drugie zatwierdzenie → 409 (idempotencja).
Pracownik może zmienić i wycofać wniosek, dopóki czeka.

## 5. Czas pracy i NFC

- **Odbicie (`Punch`) = niezmienialne zdarzenie** (`save()`/`delete()` blokowane, jak `LoginEvent`).
  Korekta kierownika = nowy wpis (`manual`, z powodem) albo `void` wskazujący pomyłkę (z powodem).
  Godziny zawsze liczone od nowa ze zdarzeń (`domain.sessions`) — nic nie jest „poprawiane w miejscu”.
- Wejście czy wyjście decyduje serwer: ostatnie ważne odbicie to wejście młodsze niż `MAX_SHIFT_HOURS` (16)
  → wyjście; inaczej wejście. Wejście bez wyjścia po 16 h → „brak wyjścia” do wyjaśnienia.
- Drugie przyłożenie w ciągu `PUNCH_DEBOUNCE_SECONDS` (60) zwraca pierwsze odbicie (`repeated`), nie robi nowego.
- **Naklejka**: URL `/nfc/<tag_token>`; telefon musi być zalogowany kontem pracownika tej firmy
  (sesja 90 dni, `SESSION_DAYS`). Po odbiciu adres karty zmienia się na `/panel` — przywrócona karta
  przeglądarki nie odbija drugi raz. Link naklejki jest publiczny z natury (każdy może go odczytać) —
  **świadome ograniczenie**: nie autoryzuje kiosku, a przy podejrzeniu wycieku dyrektor generuje nowy
  link jednym przyciskiem. Mocniejsze (NTAG 424 SUN / ograniczenie do IP firmy) — gdy klient poprosi.
- **Kiosk**: URL `/kiosk/<sekret>` (w bazie tylko sha256, pokazany raz). Czytnik USB pisze numer karty +
  Enter w ukryte pole; na Androidzie z Chrome tablet sam czyta karty (Web NFC). Bez sesji i CSRF
  (sekret w linku jest poświadczeniem), limit `THROTTLE_KIOSK`. Jedna karta naraz (kolejne w trakcie są odrzucane).
- Numer karty normalizowany (bez `:`/spacji, wielkie litery) — ten sam zapis z czytnika USB i Web NFC.
  **Uwaga**: część czytników USB podaje UID dziesiętnie — karta przypisana przez „nieznane karty
  z kiosku” zawsze ma format tego kiosku, dlatego to jest zalecana ścieżka przypisywania.
- Nieznana karta w kiosku trafia na 1 h do listy „nieznane karty” w oknie pracownika → „Przypisz”.
- Raport miesięczny: plan (zmiany) vs przepracowane (pary wejście–wyjście, dzień = dzień wejścia),
  „do wyjaśnienia” = brak wyjścia / wyjście bez wejścia. CSV (`;`, BOM — Excel PL) i wydruk.

## 6. Bezpieczeństwo i RODO

Jak HotelAgenda: `LoginEvent`, `TermsAcceptance`, `simple-history` na wszystkich modelach biznesowych,
`retencja_danych` w cronie, eksport JSON i usunięcie firmy (czyści też `historical_*` i odbicia,
anonimizuje konta bez innych firm). Regulamin: `backend/grafik/data/regulamin.html` (§ 8 = umowa
powierzenia danych pracowników). Polityka prywatności: sekcja `#grafik` na sudomie.pl — **do dopisania**.

## 7. Poza zakresem v1 (świadomie)

- Kolejka offline w kiosku (dziś: komunikat „brak internetu — powiedz kierownikowi”, korekta ręczna).
- Pomoc w innym dziale jako osobne pole zmiany (`Shift.department`) — dziś uwaga w zmianie.
- Kierownik zakładający pracowników swojego działu — dziś tylko dyrektor.
- Powiadomienia (e-mail/push) o nowym grafiku i wnioskach.
- Typy zmian / szablony godzin — zamiast tego szybkie godziny z bieżącego tygodnia.
- Stawki, wynagrodzenia, nadgodziny wg Kodeksu pracy.

## 8. Kolejność prac (zrobione 2026-10-26)

1. Szkielet z HotelAgenda → `grafik` app (modele, dostęp, serwisy, widoki) + 55 testów.
2. Panel (Dziś, Grafik, Wnioski, Czas pracy, Zespół i NFC), strony `/nfc/…` i `/kiosk/…`, landing.
3. E2E `npm run e2e` (12 kroków) lokalnie i na stosie Docker.
4. **Dalej**: produkcja (LXC + `grafik.sudomie.pl`), polityka prywatności, test na prawdziwych naklejkach i czytniku.

## 9. Kolory — Słownik Kolorów

Sprawdzone 2026-10-26: s. 38–43 (połączenia 025–036) i s. 128–132 (201–210).
- **Baza: połączenie 202** (s. 128) — Cobalt Green, Slate Color, Turquoise Green: spokojny, „dyżurny”,
  czytelny przy długiej pracy z tabelą. Slate `#2b2d33` = tekst i główne akcje; Turquoise (rozjaśniony
  `#eef4f1`, `#d3ece1`) = tło pracy; Cobalt (przyciemniony do `#2f8a68` dla kontrastu) = „w pracy”, zaznaczenia, wejście w kiosku.
- **Akcent: połączenie 033** (s. 42) — Raw Sienna `#b4501a` tylko dla „do wyjaśnienia” (wnioski czekające, braki odbić, konflikty).
- **Kolory działów** (propozycje w panelu): z połączeń 201, 204, 208, 209 (Cinnamon Rufous, Antwarp Blue,
  Rosolane Purple, Olive, Green Blue, Salvia Blue, Yellow Orange, Light Glaucous Blue).
- Kolory statusów technicznych (błąd = czerwony) — poza książką, czytelność.
- Krój: Instrument Sans (jedna rodzina, tabelaryczne cyfry) — jak tekst panelu HotelAgenda.
