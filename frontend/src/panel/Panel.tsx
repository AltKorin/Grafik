import "../fonts.css";
import { useEffect, useState, type FormEvent } from "react";
import { PRIVACY } from "../site/Site.tsx";
import { api, loadSession, logIn, logOut, useApi, type Workplace } from "./api.ts";
import Requests from "./Requests.tsx";
import Team from "./Team.tsx";
import Time from "./Time.tsx";
import Today from "./Today.tsx";
import WeekPage from "./Week.tsx";
import { go, linkTo, usePath } from "./router.ts";
import { Field, LangSwitch, ToastProvider } from "./ui.tsx";
import { t } from "../i18n.ts";
import "./panel.css";

const FIRM_KEY = "panel:firm";

export default function Panel() {
  const [user, setUser] = useState<string | null | undefined>(undefined);
  useEffect(() => {
    loadSession().then(setUser).catch(() => setUser(null));
  }, []);
  return (
    <div className="panel">
      <ToastProvider>
        {user === undefined ? null : user ? <Signed user={user} onLogout={() => setUser(null)} /> : <Login onLogin={setUser} />}
      </ToastProvider>
    </div>
  );
}

export function Login({ onLogin, title = t("Grafik"), lead = t("Zaloguj się, żeby zobaczyć grafik i swój czas pracy.") }: {
  onLogin: (user: string) => void;
  title?: string;
  lead?: string;
}) {
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const submit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    setBusy(true);
    setError("");
    try {
      const user = await logIn(String(form.get("username")), String(form.get("password")));
      if (user) onLogin(user);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <main className="login">
      <form onSubmit={submit}>
        <h1>{title}</h1>
        <p>{lead}</p>
        {error && <p className="error">{error}</p>}
        <Field label={t("Login lub e-mail")}>{(id) => <input id={id} name="username" type="text" autoComplete="username" autoCapitalize="none" required />}</Field>
        <Field label={t("Hasło")}>{(id) => <input id={id} name="password" type="password" autoComplete="current-password" required />}</Field>
        <button className="btn primary" disabled={busy}>
          {busy ? t("Logowanie…") : t("Zaloguj się")}
        </button>
        <p className="hint">
          {t("Nie masz konta? Login i hasło nadaje dyrektor firmy. Zakładasz Grafik dla swojej firmy?")} <a href="/rejestracja">{t("Załóż konto")}</a> — {t("za darmo.")}
        </p>
        <LangSwitch />
      </form>
    </main>
  );
}

/** Founds a firm for the logged-in account (it becomes the director) and opens it. */
export function NewFirm() {
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const submit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    setBusy(true);
    setError("");
    try {
      const firm = await api.post<Workplace>("/workplaces/", { firm: f.get("firm"), name: f.get("name"), accept: f.get("accept") === "on" });
      try {
        localStorage.setItem(FIRM_KEY, firm.id);
      } catch {
        /* per-browser convenience only */
      }
      window.location.assign("/panel/zespol");
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  };
  return (
    <form onSubmit={submit} style={{ display: "grid", gap: 14 }}>
      {error && <p className="error">{error}</p>}
      <Field label={t("Nazwa firmy")}>{(id) => <input id={id} name="firm" type="text" required maxLength={200} />}</Field>
      <Field label={t("Twoje imię i nazwisko")} hint={t("Tak zobaczą Cię pracownicy w grafiku.")}>
        {(id) => <input id={id} name="name" type="text" required maxLength={120} autoComplete="name" />}
      </Field>
      <label className="check">
        <input name="accept" type="checkbox" required />
        <span>
          {t("Akceptuję")} <a href="/regulamin" target="_blank">{t("regulamin")}</a> {t("i zapoznałem/am się z")}{" "}
          <a href={PRIVACY} target="_blank" rel="noopener">{t("polityką prywatności")}</a>.
        </span>
      </label>
      <button className="btn primary" disabled={busy}>{busy ? t("Zakładam…") : t("Załóż firmę")}</button>
    </form>
  );
}

const PAGES = [
  { path: "/panel", label: t("Dziś"), min: "pracownik" },
  { path: "/panel/grafik", label: t("Grafik"), min: "pracownik" },
  { path: "/panel/wnioski", label: t("Wnioski"), min: "pracownik" },
  { path: "/panel/czas", label: t("Czas pracy"), min: "pracownik" },
  { path: "/panel/zespol", label: t("Zespół i NFC"), min: "kierownik" }, // a manager sees only his people there
] as const;
const RANK = { pracownik: 0, kierownik: 1, dyrektor: 2, admin: 3 };

function Signed({ user, onLogout }: { user: string; onLogout: () => void }) {
  const path = usePath();
  const firms = useApi<Workplace[]>("/workplaces/");
  const [firmId, setFirmId] = useState(() => {
    try {
      return localStorage.getItem(FIRM_KEY) ?? "";
    } catch {
      return "";
    }
  });
  const list = firms.data ?? [];
  const firm = list.find((f) => f.id === firmId) ?? list[0];

  if (firms.error) return <p className="page error">{firms.error}</p>;
  if (!firms.data) return null;
  if (!firm)
    return (
      <main className="page">
        <p className="empty">{t("To konto nie należy jeszcze do żadnej firmy. Pracujesz w firmie, która używa Grafiku? Poproś dyrektora o dodanie. Prowadzisz firmę? Załóż ją tutaj.")}</p>
        <section className="card settings-card">
          <h2>{t("Nowa firma")}</h2>
          <NewFirm />
        </section>
        <div className="inline-form">
          <button className="btn" onClick={() => logOut().then(onLogout)}>{t("Wyloguj")}</button>
          <LangSwitch />
        </div>
      </main>
    );

  const choose = (id: string) => {
    try {
      localStorage.setItem(FIRM_KEY, id);
    } catch {
      /* per-browser convenience only */
    }
    setFirmId(id);
    go("/panel");
  };
  const pages = PAGES.filter((p) => RANK[firm.role] >= RANK[p.min]);
  const current = [...pages].reverse().find((p) => path === p.path || path.startsWith(`${p.path}/`)) ?? pages[0];

  return (
    <>
      <header className="topbar">
        <span className="firm">
          {list.length > 1 ? (
            <select value={firm.id} onChange={(e) => choose(e.target.value)} aria-label={t("Firma")}>
              {list.map((f) => (
                <option key={f.id} value={f.id}>
                  {f.name}
                </option>
              ))}
            </select>
          ) : (
            firm.name
          )}
        </span>
        <nav>
          {pages.map((p) => (
            <a key={p.path} {...linkTo(p.path)} aria-current={p === current ? "page" : undefined}>
              {p.path === "/panel/zespol" && firm.role === "kierownik" ? t("Zespół") : p.label}
            </a>
          ))}
        </nav>
        <LangSwitch />
        <span className="who">{user}</span>
        <button className="link" onClick={() => logOut().then(onLogout)}>
          {t("Wyloguj")}
        </button>
      </header>
      {current.path === "/panel/grafik" ? (
        <WeekPage firm={firm} />
      ) : current.path === "/panel/wnioski" ? (
        <Requests firm={firm} />
      ) : current.path === "/panel/czas" ? (
        <Time firm={firm} />
      ) : current.path === "/panel/zespol" ? (
        <Team firm={firm} onFirmChange={firms.reload} />
      ) : (
        <Today firm={firm} />
      )}
    </>
  );
}
