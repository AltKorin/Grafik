// Public pages: landing with a working demo, registration, regulamin. Only here GA may run (consent.ts).
import "../fonts.css";
import { useEffect, useId, useState, type FormEvent, type ReactNode } from "react";
import { api, loadSession } from "../panel/api.ts";
import { choose, readChoice, startAnalytics } from "./consent.ts";
import Landing from "./Landing.tsx";
import "../panel/panel.css"; // .btn, .error, .check — shared with the panel
import "./site.css";
import { t } from "../i18n.ts";
import { LangSwitch } from "../panel/ui.tsx";

export const PRIVACY = "https://sudomie.pl/polityka-prywatnosci.html#grafik";

export default function Site({ path }: { path: string }) {
  const page = /^\/rejestracja\/?$/.test(path) ? "register" : /^\/regulamin\/?$/.test(path) ? "terms" : "landing";
  useEffect(() => {
    document.title = { landing: t("Grafik — darmowy grafik pracy i czas pracy przez NFC"), register: t("Załóż konto — Grafik"), terms: t("Regulamin — Grafik") }[page];
  }, [page]);
  return (
    <div className="site">
      <header className="site-top">
        <a className="site-brand" href="/">Grafik</a>
        <nav>
          <LangSwitch />
          <a href="/panel">{t("Zaloguj się")}</a>
          {page !== "register" && <a className="btn primary" href="/rejestracja">{t("Załóż konto")}</a>}
        </nav>
      </header>
      {page === "register" ? <Register /> : page === "terms" ? <Terms /> : <Landing />}
      <Footer />
      <ConsentBar />
    </div>
  );
}

function Footer() {
  return (
    <footer className="site-foot">
      <p>
        {t("Grafik jest darmowy. Prowadzi go Komorowski & Windorpski sp. z o.o., ul. Kawaleryjska 3, 83-400 Kościerzyna-Wybudowanie, KRS 0001265889, NIP 5911731573.")}
      </p>
      <p className="site-links">
        <a href="/regulamin">{t("Regulamin")}</a>
        <a href={PRIVACY}>{t("Polityka prywatności")}</a>
        <button className="link" onClick={() => window.dispatchEvent(new Event("cc:open"))}>{t("Ustawienia cookies")}</button>
        <a href="mailto:kontakt@sudomie.pl">kontakt@sudomie.pl</a>
        <a href="tel:+48668341191">+48 668 341 191</a>
      </p>
    </footer>
  );
}

function ConsentBar() {
  const [id, setId] = useState("");
  const [open, setOpen] = useState(false);
  useEffect(() => {
    startAnalytics().then((value) => {
      setId(value);
      setOpen(Boolean(value) && readChoice() === null);
    });
    const reopen = () => setOpen(true);
    window.addEventListener("cc:open", reopen);
    return () => window.removeEventListener("cc:open", reopen);
  }, []);
  if (!open) return null;
  const pick = (choice: "accepted" | "declined") => {
    choose(choice);
    setOpen(false);
  };
  return (
    <div className="cc-bar" role="region" aria-label={t("Zgoda na statystyki")}>
      <p>
        {id
          ? <>{t("Używamy Google Analytics, żeby wiedzieć, jak korzystasz z tej strony. Bez zgody nie zapisujemy cookies statystycznych.")} <a href={PRIVACY}>{t("Polityka prywatności")}</a></>
          : t("Ta strona nie używa cookies statystycznych.")}
      </p>
      {id ? (
        <span>
          <button className="btn primary" onClick={() => pick("accepted")}>{t("Zgadzam się")}</button>
          <button className="btn" onClick={() => pick("declined")}>{t("Odrzucam")}</button>
        </span>
      ) : (
        <button className="btn" onClick={() => setOpen(false)}>{t("Zamknij")}</button>
      )}
    </div>
  );
}

function Register() {
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    loadSession().catch(() => undefined); // sets the CSRF cookie and token
  }, []);
  const submit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    if (f.get("password") !== f.get("repeat")) return setError(t("Hasło i powtórzenie się różnią"));
    setBusy(true);
    setError("");
    try {
      await api.post("/register/", {
        email: f.get("email"),
        firm: f.get("firm"),
        name: f.get("name"),
        password: f.get("password"),
        accept: f.get("accept") === "on",
        website: f.get("website") ?? "",
      });
      window.gtag?.("event", "sign_up", { method: "email" });
      window.location.assign("/panel");
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  };
  return (
    <main className="site-narrow">
      <h1>{t("Załóż Grafik dla swojej firmy")}</h1>
      <p className="lead">{t("Za darmo, bez karty. Po założeniu dodasz zespół i ułożysz pierwszy tydzień.")}</p>
      <form className="site-form" onSubmit={submit}>
        {error && <p className="error" role="alert">{error}</p>}
        <Labeled label={t("Nazwa firmy")}>
          {(id) => <input id={id} name="firm" type="text" required maxLength={200} autoComplete="organization" />}
        </Labeled>
        <Labeled label={t("Twoje imię i nazwisko")} hint={t("Tak zobaczą Cię pracownicy w grafiku.")}>
          {(id) => <input id={id} name="name" type="text" required maxLength={120} autoComplete="name" />}
        </Labeled>
        <Labeled label={t("Twój e-mail")} hint={t("Będzie Twoim loginem.")}>
          {(id) => <input id={id} name="email" type="email" required maxLength={150} autoComplete="email" />}
        </Labeled>
        <Labeled label={t("Hasło")} hint={t("Co najmniej 12 znaków.")}>
          {(id) => <input id={id} name="password" type="password" required minLength={12} autoComplete="new-password" />}
        </Labeled>
        <Labeled label={t("Powtórz hasło")}>
          {(id) => <input id={id} name="repeat" type="password" required minLength={12} autoComplete="new-password" />}
        </Labeled>
        <div className="hp" aria-hidden="true">
          <label>
            Strona www
            <input name="website" type="text" tabIndex={-1} autoComplete="off" />
          </label>
        </div>
        <label className="check">
          <input name="accept" type="checkbox" required />
          <span>
            {t("Akceptuję")} <a href="/regulamin" target="_blank">{t("regulamin")}</a> {t("i zapoznałem/am się z")}{" "}
            <a href={PRIVACY} target="_blank" rel="noopener">{t("polityką prywatności")}</a>.
          </span>
        </label>
        <button className="btn primary big" disabled={busy}>{busy ? t("Zakładam konto…") : t("Załóż konto")}</button>
        <p className="hint">
          {t("Zostaniesz dyrektorem firmy w Grafiku: dodasz działy, pracowników z loginami i kartami NFC oraz punkty odbić. Masz już konto?")} <a href="/panel">{t("Zaloguj się")}</a>.
        </p>
      </form>
    </main>
  );
}

function Terms() {
  const [html, setHtml] = useState("");
  useEffect(() => {
    fetch("/api/terms/")
      .then((r) => r.json())
      .then((data: { html: string }) => setHtml(data.html))
      .catch(() => setHtml(`<p>${t("Nie udało się wczytać regulaminu. Odśwież stronę.")}</p>`));
  }, []);
  // Our own file from the backend (grafik/data/regulamin.html) — the same bytes whose hash we store.
  return (
    <main className="site-narrow terms">
      <h1>{t("Regulamin Grafiku")}</h1>
      <div dangerouslySetInnerHTML={{ __html: html }} />
    </main>
  );
}

function Labeled({ label, hint, children }: { label: string; hint?: string; children: (id: string) => ReactNode }) {
  const id = useId();
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      {children(id)}
      {hint && <small>{hint}</small>}
    </div>
  );
}
