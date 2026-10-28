import "../fonts.css";
import { useEffect, useState, type FormEvent } from "react";
import { loadSession, logIn, logOut, useApi, type Workplace } from "./api.ts";
import Requests from "./Requests.tsx";
import Team from "./Team.tsx";
import Time from "./Time.tsx";
import Today from "./Today.tsx";
import WeekPage from "./Week.tsx";
import { go, linkTo, usePath } from "./router.ts";
import { Field, ToastProvider } from "./ui.tsx";
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

export function Login({ onLogin, title = "Grafik", lead = "Zaloguj się, żeby zobaczyć grafik i swój czas pracy." }: {
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
        <Field label="Login lub e-mail">{(id) => <input id={id} name="username" type="text" autoComplete="username" autoCapitalize="none" required />}</Field>
        <Field label="Hasło">{(id) => <input id={id} name="password" type="password" autoComplete="current-password" required />}</Field>
        <button className="btn primary" disabled={busy}>
          {busy ? "Logowanie…" : "Zaloguj się"}
        </button>
        <p className="hint">
          Nie masz konta? Login i hasło nadaje dyrektor firmy. Zakładasz Grafik dla swojej firmy? <a href="/rejestracja">Załóż konto</a> — za darmo.
        </p>
      </form>
    </main>
  );
}

const PAGES = [
  { path: "/panel", label: "Dziś", min: "pracownik" },
  { path: "/panel/grafik", label: "Grafik", min: "pracownik" },
  { path: "/panel/wnioski", label: "Wnioski", min: "pracownik" },
  { path: "/panel/czas", label: "Czas pracy", min: "pracownik" },
  { path: "/panel/zespol", label: "Zespół i NFC", min: "dyrektor" },
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
        <p className="empty">To konto nie należy jeszcze do żadnej firmy. Poproś dyrektora o dodanie.</p>
        <button className="btn" onClick={() => logOut().then(onLogout)}>Wyloguj</button>
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
            <select value={firm.id} onChange={(e) => choose(e.target.value)} aria-label="Firma">
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
              {p.label}
            </a>
          ))}
        </nav>
        <span className="who">{user}</span>
        <button className="link" onClick={() => logOut().then(onLogout)}>
          Wyloguj
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
