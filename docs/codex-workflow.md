# Codex — sposób pracy w Grafiku

Zasady: `/home/konrad/Claude/CLAUDE.md`. Kolejka i statusy wyłącznie w
[OpenProject](https://projekty.sudomie.pl/projects/grafik/work_packages).
Ten dokument opisuje procedurę, nie zastępuje kolejki.

## Dostęp

Konto techniczne `codex`, osobny token `~/.config/openproject/codex.token` (600),
bez sekretów w repo. Klient projektu korzysta ze wspólnego `~/Claude/OpenProject/op.py`,
ale przed żądaniami API ustawia token Codex. Wspólny moduł przy imporcie nadal wymaga
istnienia `claude.token`; to zależność istniejącego klienta.

```sh
python3 scripts/openproject.py whoami
python3 scripts/openproject.py todo grafik
python3 scripts/openproject.py show 427
```

## Przebieg sesji

1. Przeczytaj nadrzędny `CLAUDE.md`, `HANDOFF.md`, `SUMMARY.md`; sprawdź `git status`
   i kolejkę przez klienta Codex. Zachowaj cudze niezacommitowane zmiany.
2. Kontynuuj „W Toku”; sprawdź blokady „Zawieszony”; następnie wybierz najniższy numer
   „Nowy”. Przy faktycznym rozpoczęciu ustaw `move <id> w-toku` (limit 1–2 zadań).
3. Zrealizuj kryteria zadania, sprawdź uprawnienia, błędy i przypadki graniczne.
   Funkcje klienta muszą działać w jego panelu. Nową funkcję udostępniaj przez flagę.
4. Uzupełnij wynik i dowody w OpenProject oraz dokumentację sesji. Zamykaj tylko
   zweryfikowane zadania. Nowe niezakończone sprawy rejestruj w OpenProject;
   po dodaniu uruchom wspólny `plan_timeline.py`, bez `--replan`.
5. Sprawy wymagające Konrada oznacz „Zawieszony” i przypisz Konradowi (ID 5).
   Uwaga: wspólne `move <id> czeka` zmienia tylko status — przypisanie trzeba
   sprawdzić i ustawić osobno przez API. `add ... --czeka` robi obie rzeczy.

Commit i push tylko na prośbę użytkownika, zgodnie z `HANDOFF.md`.
Numery zadań w odpowiedziach zawsze jako linki.

## Przygotowana ścieżka dla zadania 427

[Kiosk: kolejka offline odbić](https://projekty.sudomie.pl/work_packages/427)
było pierwszym zadaniem „Nowy” przy przeglądzie 2026-10-28. Przed rozpoczęciem
ponownie odczytaj kolejkę i opis; przygotowanie planu nie oznacza rozpoczęcia implementacji.

1. Prześledź `frontend/src/tap/`, `frontend/src/nfc.ts`, `backend/grafik/clock.py`,
   `domain.py`, `access.py` oraz modele odbić. Ustal zachowanie przy utracie sieci,
   restarcie kiosku, cofnięciu zegara i zmianie sekretu punktu.
2. Zaprojektuj kontrakt synchronizacji: identyfikator zdarzenia do deduplikacji,
   czas urządzenia oraz czas odbioru na serwerze, kolejność, ograniczony rozmiar
   kolejki i jawna obsługa odrzuconych odbić. Zdefiniuj dopuszczalne opóźnienie
   i odchylenie zegara jako konfigurację; nie ufaj bezwarunkowo czasowi klienta.
3. Dodaj trwałą kolejkę po stronie kiosku oraz idempotentny endpoint. Wybór
   localStorage lub IndexedDB uzasadnij wymaganiami trwałości i współbieżności.
   Panel pokazuje liczbę oczekujących odbić i błędy synchronizacji, a sukces
   dopiero po trwałym zapisie lokalnym lub potwierdzeniu serwera, odpowiednio opisany.
4. Zweryfikuj offline → restart → online, ponowne wysłanie, częściową odpowiedź,
   błędny sekret, obcą firmę, pełną kolejkę, zmianę dnia/DST oraz zmanipulowany czas.
   Uruchom testy backendu, `npm run check` i adekwatny scenariusz E2E; uzupełnij PL/EN.
5. Zapisz dowody w `docs/weryfikacja.md` i zadaniu. DoD: brak utraty i duplikacji
   zaakceptowanych odbić, czytelny stan synchronizacji, zachowane uprawnienia
   i historia, kontrolowane włączanie funkcji oraz aktualne HANDOFF/SUMMARY.

## Sprawy oczekujące na Konrada — stan przeglądu

- [Polityka prywatności](https://projekty.sudomie.pl/work_packages/424).
- [Przegląd regulaminu](https://projekty.sudomie.pl/work_packages/425).
- [Test fizycznego NFC](https://projekty.sudomie.pl/work_packages/426).
- [Rezerwacja DHCP](https://projekty.sudomie.pl/work_packages/461).

Bieżące rozstrzygnięcia i priorytety sprawdzaj w OpenProject.
