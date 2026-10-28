// /kiosk/<secret>: tablet at the entrance. A USB NFC reader types the card number + Enter into a hidden
// field; on Android Chrome the tablet's own NFC can read cards instead (Web NFC). One card = one punch.
import "../fonts.css";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { hasWebNfc, scanSerials } from "../nfc.ts";
import type { TapResult } from "../panel/api.ts";
import "../panel/panel.css";
import "./tap.css";
import { locale, t } from "../i18n.ts";
import { LangSwitch } from "../panel/ui.tsx";

type Info = { point: string; workplace: string; timezone: string };
type Shown = { kind: "in" | "out" | "bad"; title: string; text: string };
const SHOW_MS = 4000;

async function call<T>(url: string, body?: unknown): Promise<T> {
  const response = await fetch(url, {
    method: body ? "POST" : "GET",
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
    credentials: "omit", // the secret in the link is the credential, never a session
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error ?? data.detail ?? t("Błąd serwera ({status})", { status: response.status }));
  return data as T;
}

export default function Kiosk({ secret }: { secret: string }) {
  const base = `/api/kiosk/${encodeURIComponent(secret)}/`;
  const [info, setInfo] = useState<Info | null>(null);
  const [error, setError] = useState("");
  const [shown, setShown] = useState<Shown | null>(null);
  const [now, setNow] = useState(() => new Date());
  const [nfcOn, setNfcOn] = useState(false);
  const busy = useRef(false);
  const input = useRef<HTMLInputElement>(null);

  useEffect(() => {
    call<Info>(base).then(setInfo).catch((e: Error) => setError(e.message));
    const tick = window.setInterval(() => setNow(new Date()), 1000);
    // keep the tablet's screen on (where supported); a dark screen nobody taps
    navigator.wakeLock?.request("screen").catch(() => undefined);
    return () => window.clearInterval(tick);
  }, [base]);

  useEffect(() => {
    if (!shown) return;
    const id = window.setTimeout(() => setShown(null), SHOW_MS);
    return () => window.clearTimeout(id);
  }, [shown]);

  const punch = async (card: string) => {
    if (busy.current || !card.trim()) return; // backpressure: one card at a time, extra taps are dropped
    busy.current = true;
    try {
      const r = await call<TapResult>(base, { card });
      setShown({ kind: r.kind, title: `${r.kind_label} ${r.time}`, text: r.repeated ? `${r.name} — ${t("już odbito, nie liczymy drugi raz")}` : r.name });
    } catch (e) {
      const offline = e instanceof TypeError;
      setShown({ kind: "bad", title: offline ? t("Brak internetu") : t("Nie odbito"), text: offline ? t("Odbicie nie zostało zapisane — powiedz kierownikowi.") : (e as Error).message });
    } finally {
      busy.current = false;
    }
  };

  const submit = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const value = input.current?.value ?? "";
    if (input.current) input.current.value = "";
    punch(value);
  };

  const startNfc = async () => {
    const controller = new AbortController();
    try {
      await scanSerials((serial) => punch(serial), () => setShown({ kind: "bad", title: t("Nie odczytano"), text: t("Przyłóż kartę jeszcze raz.") }), controller.signal);
      setNfcOn(true);
    } catch (e) {
      setShown({ kind: "bad", title: t("NFC niedostępne"), text: (e as Error).message });
    }
  };

  const time = new Intl.DateTimeFormat(locale, { hour: "2-digit", minute: "2-digit", timeZone: info?.timezone }).format(now);
  if (error) return <div className="panel"><main className="tap"><p className="tap-mark bad">!</p><h1>{t("Kiosk nieaktywny")}</h1><p>{error}</p></main></div>;
  return (
    <div className="panel" onClick={() => input.current?.focus()}>
      <main className="kiosk">
        <header>
          <span>{info ? `${info.workplace} · ${info.point}` : "…"}</span>
          <span className="clock">{time}</span>
        </header>
        <section className={`stage ${shown?.kind ?? ""}`} aria-live="assertive">
          {shown ? (
            <>
              <h1>{shown.title}</h1>
              <p>{shown.text}</p>
            </>
          ) : (
            <>
              <div className="card-icon" aria-hidden="true" />
              <h1>{t("Przyłóż kartę")}</h1>
              <p>{t("Wejście i wyjście — ta sama karta. Wynik zobaczysz tutaj.")}</p>
            </>
          )}
        </section>
        <footer>
          <form onSubmit={submit}>
            {/* the USB reader types here; kept focused */}
            <input ref={input} className="catcher" autoFocus inputMode="none" autoComplete="off" aria-label={t("Numer karty")} onBlur={() => window.setTimeout(() => input.current?.focus(), 50)} />
          </form>
          <span>{t("Odbicia z telefonu: naklejka NFC obok.")}</span>
          {hasWebNfc() && !nfcOn && <button className="btn" onClick={startNfc}>{t("Czytaj karty NFC tabletu")}</button>}
          {nfcOn && <span>{t("NFC tabletu: włączone")}</span>}
          <LangSwitch />
        </footer>
      </main>
    </div>
  );
}
