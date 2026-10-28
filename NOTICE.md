# Pochodzenie kodu

- Szkielet (backend `core/`, konfiguracja, Compose, Caddy, skrypty `deploy/`, panel `ui.tsx`/`router.ts`/`api.ts`,
  strona publiczna i zgody cookies) skopiowany z HotelAgenda (ten sam autor). Część infrastruktury
  (`core/transport.py`, `core/private_cache.py`, `core/domain_errors.py`) pochodzi z Narrative Framework
  (web/, 0.3.0-alpha.2), licencja MIT — tekst w `LICENSE`. Nazwy „Narrative Framework” i „Stolem Narrative Dev”
  nie są częścią licencji i nie są używane przez Grafik.
- Domena grafiku: wymagania z repo `AltKorin/Shift_Manager` (wnioski o zmiany) i ze speca InnDesk
  `docs/superpowers/specs/2026-09-10-staff-schedule-design.md` (niedyspozycyjność, kierownik działu). Kod napisany od nowa.
- Krój Instrument Sans z paczki `@fontsource/instrument-sans` (SIL Open Font License 1.1, licencja w `node_modules`).
