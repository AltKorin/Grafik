// The public sandbox („Wypróbuj demo”, backend grafik.demo): a button for the site and a bar for the panel.
import { useEffect, useState } from "react";
import { locale, t } from "../i18n.ts";
import { api, loadSession, useApi } from "./api.ts";

type Role = "dyrektor" | "kierownik" | "pracownik";
type Demo = { workplace: string; until: string; role: Role | null; tag: string; kiosk: string; cards: { name: string; card: string }[] };
const ROLES: [Role, string][] = [["dyrektor", t("Dyrektor")], ["kierownik", t("Kierownik")], ["pracownik", t("Pracownik")]];

/** Shown only when the server has the demo on (DEMO_MAX > 0). */
export function DemoButton({ className = "btn big" }: { className?: string }) {
  const [on, setOn] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    fetch("/api/public-config/").then((r) => r.json()).then((c: { demo?: boolean }) => setOn(Boolean(c.demo))).catch(() => undefined);
  }, []);
  if (!on) return null;
  const start = async () => {
    setBusy(true);
    setError("");
    try {
      await loadSession(); // CSRF token for the POST
      await api.post("/demo/");
      window.location.assign("/panel");
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  };
  return (
    <>
      <button className={className} onClick={start} disabled={busy}>{busy ? t("Przygotowuję demo…") : t("Wypróbuj demo — bez rejestracji")}</button>
      {error && <span className="error">{error}</span>}
    </>
  );
}

export function DemoBar() {
  const state = useApi<{ demo: Demo | null }>("/demo/");
  const demo = state.data?.demo;
  if (!demo) return null;
  const as = (role: Role) => api.post("/demo/as/", { role }).then(() => window.location.assign("/panel"));
  const until = new Date(demo.until).toLocaleString(locale, { weekday: "short", hour: "2-digit", minute: "2-digit" });
  const card = demo.cards[0];
  return (
    <div className="demo-bar no-print">
      <p>
        <strong>{t("Demo")}</strong> — {t("Twoja własna kopia firmy przykładowej. Klikaj śmiało, zniknie {until}.", { until })}
      </p>
      <div className="demo-actions">
        <span role="group" aria-label={t("Zobacz jako")}>
          {t("Zobacz jako:")}{" "}
          {ROLES.map(([role, label]) => (
            <button key={role} className="btn quiet" aria-pressed={demo.role === role} onClick={() => demo.role !== role && as(role)}>{label}</button>
          ))}
        </span>
        <a className="btn quiet" href={demo.kiosk} target="_blank" rel="noopener">{t("Kiosk (tablet)")} ↗</a>
        {demo.role === "pracownik" && <a className="btn quiet" href={demo.tag} target="_blank" rel="noopener">{t("Odbij się telefonem (jak przy naklejce)")} ↗</a>}
        <a className="btn primary" href="/rejestracja">{t("Załóż własne konto")}</a>
      </div>
      {card && <p className="hint">{t("W kiosku wpisz numer karty i naciśnij Enter, np. {card} ({name}) — tak robi czytnik USB.", { card: card.card, name: card.name })}</p>}
    </div>
  );
}
