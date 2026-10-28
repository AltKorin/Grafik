// /zaproszenie/<token>: the link a manager sent. The employee picks a login and password, then lands in the panel.
import "../fonts.css";
import { useEffect, useState, type FormEvent } from "react";
import { t } from "../i18n.ts";
import { api, loadSession } from "../panel/api.ts";
import { Field, LangSwitch } from "../panel/ui.tsx";
import "../panel/panel.css";

type Info = { workplace: string; name: string; login: string };

export default function Invite({ token }: { token: string }) {
  const path = `/invite/${encodeURIComponent(token)}/`;
  const [info, setInfo] = useState<Info | null>(null);
  const [error, setError] = useState("");
  const [dead, setDead] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    loadSession() // the CSRF token for the POST
      .then(() => api.get<Info>(path))
      .then(setInfo)
      .catch((err: Error) => setDead(err.message));
  }, [path]);

  const submit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    if (f.get("password") !== f.get("repeat")) return setError(t("Hasło i powtórzenie się różnią"));
    setBusy(true);
    setError("");
    try {
      await api.post(path, { login: f.get("login"), password: f.get("password") });
      window.location.assign("/panel"); // signed in already; the used link must not stay in the address bar
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  };

  return (
    <div className="panel">
      <main className="login">
        {dead ? (
          <div className="login-card">
            <h1>{t("Zaproszenie nie działa")}</h1>
            <p>{dead}</p>
            <a className="btn" href="/panel">{t("Mam już konto — zaloguj się")}</a>
          </div>
        ) : info && (
          <form onSubmit={submit}>
            <h1>{t("Witaj, {name}", { name: info.name })}</h1>
            <p>{t("{firm} zaprasza Cię do Grafiku. Ustaw login i hasło — będziesz widzieć swój grafik i odbijać się telefonem.", { firm: info.workplace })}</p>
            {error && <p className="error">{error}</p>}
            <Field label={t("Login")} hint={t("Litery bez polskich znaków, cyfry, kropka, myślnik.")}>
              {(id) => <input id={id} name="login" type="text" required maxLength={40} autoCapitalize="none" autoComplete="username" defaultValue={info.login} />}
            </Field>
            <Field label={t("Hasło")} hint={t("Co najmniej 12 znaków.")}>
              {(id) => <input id={id} name="password" type="password" required minLength={12} autoComplete="new-password" />}
            </Field>
            <Field label={t("Powtórz hasło")}>{(id) => <input id={id} name="repeat" type="password" required minLength={12} autoComplete="new-password" />}</Field>
            <button className="btn primary" disabled={busy}>{busy ? t("Zakładam konto…") : t("Załóż konto")}</button>
            <LangSwitch />
          </form>
        )}
      </main>
    </div>
  );
}
