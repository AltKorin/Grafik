// "Dziś": my status and next shifts, my unavailability, and — for managers — who is at work now.
import { useState, type FormEvent } from "react";
import { api, useApi, type Away, type ChangeRequest, type Today as TodayData, type Workplace } from "./api.ts";
import { AwayDialog, awayText } from "./Away.tsx";
import { linkTo } from "./router.ts";
import { dayLabel } from "./time.ts";
import { Field, useToast } from "./ui.tsx";
import { t } from "../i18n.ts";

export default function Today({ firm }: { firm: Workplace }) {
  const today = useApi<TodayData>(`/w/${firm.id}/today/`);
  const away = useApi<Away[]>(firm.me ? `/w/${firm.id}/unavailability/?employee=${firm.me}` : null);
  const requests = useApi<ChangeRequest[]>(firm.role === "pracownik" ? null : `/w/${firm.id}/requests/`);
  const [editing, setEditing] = useState<Away | "new" | null>(null);
  const data = today.data;
  const toReview = (requests.data ?? []).filter((r) => r.reviewable).length;

  return (
    <main className="page">
      <div className="page-head">
        <div>
          <h1>{t("Dziś")}</h1>
          <p>{data ? dayLabel(data.date) : "…"} — {t("twoja zmiana, odbicia i kto jest w pracy.")}</p>
        </div>
      </div>
      {today.error && <p className="error">{today.error}</p>}
      {toReview > 0 && (
        <p className="notice">
          {t("Wnioski do rozpatrzenia:")} <strong>{toReview}</strong>. <a {...linkTo("/panel/wnioski")}>{t("Przejdź do wniosków")}</a>
        </p>
      )}
      <div className="cards">
        {data?.me && (
          <section className="card">
            <h2>{t("Ja")}</h2>
            <p className={`status${data.me.inside ? " in" : ""}`}>
              <span className="dot" />
              {data.me.inside ? t("W pracy od {since}", { since: data.me.since ?? "" }) : t("Poza pracą")}
            </p>
            {data.me.last && <p className="hint">{t("Ostatnie odbicie:")} {data.me.last.kind === "in" ? t("wejście") : t("wyjście")} {data.me.last.local}</p>}
            <p className="hint">{t("Odbijasz się telefonem przy naklejce NFC albo kartą w kiosku przy wejściu.")}</p>
            <h2>{t("Najbliższe zmiany")}</h2>
            {data.me.shifts.length === 0 ? (
              <p className="muted">{t("Brak zmian w najbliższych dwóch tygodniach.")}</p>
            ) : (
              <ul className="plain-list">
                {data.me.shifts.map((s) => (
                  <li key={s.id}>
                    <span>{dayLabel(s.date)}{s.date === data.date && <strong> — {t("dziś")}</strong>}</span>
                    <span className="num">{s.start}–{s.end}{s.notes && <span className="muted"> · {s.notes}</span>}</span>
                  </li>
                ))}
              </ul>
            )}
          </section>
        )}
        {firm.me && (
          <section className="card">
            <h2>{t("Urlop, L4, niedostępność")}</h2>
            {(away.data ?? []).length === 0 ? (
              <p className="muted">{t("Nic nie zgłoszono.")}</p>
            ) : (
              <ul className="plain-list">
                {away.data!.map((a) => (
                  <li key={a.id}>
                    <span>{awayText(a)}</span>
                    <button className="btn quiet" onClick={() => setEditing(a)}>{t("Zmień")}</button>
                  </li>
                ))}
              </ul>
            )}
            <button className="btn" onClick={() => setEditing("new")}>{t("Zgłoś niedyspozycyjność")}</button>
          </section>
        )}
        {data?.presence && <Presence presence={data.presence} />}
        <PasswordCard />
      </div>
      {editing && (
        <AwayDialog
          firmId={firm.id}
          away={editing === "new" ? null : editing}
          defaultDay={data?.date}
          onClose={() => setEditing(null)}
          onSaved={() => {
            away.reload();
            today.reload();
          }}
        />
      )}
    </main>
  );
}

function Presence({ presence }: { presence: NonNullable<TodayData["presence"]> }) {
  const inside = presence.filter((p) => p.inside);
  const planned = presence.filter((p) => !p.inside && p.today.length);
  return (
    <section className="card">
      <h2>{t("W pracy teraz:")} {inside.length}</h2>
      {inside.length === 0 ? (
        <p className="muted">{t("Nikt nie jest odbity.")}</p>
      ) : (
        <ul className="plain-list">
          {inside.map((p) => (
            <li key={p.employee}>
              <span>{p.name}</span>
              <span className="num muted">{t("od")} {p.since}{p.today.length ? ` · ${t("plan")} ${p.today.join(", ")}` : ` · ${t("bez zmiany w grafiku")}`}</span>
            </li>
          ))}
        </ul>
      )}
      {planned.length > 0 && (
        <>
          <h2>{t("Dziś w grafiku, nie w pracy")}</h2>
          <ul className="plain-list">
            {planned.map((p) => (
              <li key={p.employee}>
                <span>{p.name}</span>
                <span className="num muted">{p.today.join(", ")}</span>
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}

function PasswordCard() {
  const toast = useToast();
  const [error, setError] = useState("");
  const submit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const form = e.currentTarget;
    const f = new FormData(form);
    if (f.get("new") !== f.get("repeat")) return setError(t("Nowe hasło i powtórzenie się różnią"));
    try {
      await api.post("/me/password/", { current: f.get("current"), new: f.get("new") });
      setError("");
      form.reset();
      toast(t("Hasło zmienione. Inne urządzenia trzeba zalogować ponownie."));
    } catch (err) {
      setError((err as Error).message);
    }
  };
  return (
    <section className="card">
      <h2>{t("Moje hasło")}</h2>
      <form onSubmit={submit} style={{ display: "grid", gap: 12 }}>
        {error && <p className="error">{error}</p>}
        <Field label={t("Obecne hasło")}>{(id) => <input id={id} name="current" type="password" autoComplete="current-password" required />}</Field>
        <Field label={t("Nowe hasło")} hint={t("Co najmniej 12 znaków.")}>{(id) => <input id={id} name="new" type="password" autoComplete="new-password" minLength={12} required />}</Field>
        <Field label={t("Powtórz nowe hasło")}>{(id) => <input id={id} name="repeat" type="password" autoComplete="new-password" minLength={12} required />}</Field>
        <button className="btn">{t("Zmień hasło")}</button>
      </form>
    </section>
  );
}
