// Zespół i NFC (director): departments, people (login, card), clock points (sticker + kiosk), the firm.
// CLAUDE.md: everything here has list / add / edit / delete in this panel.
import QRCode from "qrcode";
import { useEffect, useState, type FormEvent } from "react";
import { hasWebNfc, writeUrl } from "../nfc.ts";
import { api, useApi, type ClockPoint, type Department, type Employee, type UnknownCard, type Workplace } from "./api.ts";
import { Dialog, Field, useToast } from "./ui.tsx";

// Słownik Kolorów, połączenia 201, 204, 208, 209 (s. 128–132) — proposed department colours.
const SWATCHES = ["#2f8a68", "#1e5f9b", "#c95a1e", "#a3195b", "#6b6a1f", "#2a8a91", "#8094d6", "#e0762c", "#9dbbd6", "#5b7a8c"];
const ROLES: [Employee["role"], string][] = [["pracownik", "Pracownik"], ["kierownik", "Kierownik działu"], ["dyrektor", "Dyrektor"]];

export default function Team({ firm, onFirmChange }: { firm: Workplace; onFirmChange: () => void }) {
  const departments = useApi<Department[]>(`/w/${firm.id}/departments/`);
  const people = useApi<Employee[]>(`/w/${firm.id}/employees/`);
  const points = useApi<ClockPoint[]>(`/w/${firm.id}/points/`);
  const reloadAll = () => {
    departments.reload();
    people.reload();
  };
  return (
    <main className="page">
      <div className="page-head">
        <div>
          <h1>Zespół i NFC</h1>
          <p>Działy, pracownicy z loginami i kartami, punkty odbić przy wejściu, ustawienia firmy.</p>
        </div>
      </div>
      <People firm={firm} people={people.data ?? []} departments={departments.data ?? []} onChange={reloadAll} />
      <Departments firm={firm} departments={departments.data ?? []} onChange={reloadAll} />
      <Points firm={firm} points={points.data ?? []} onChange={points.reload} />
      <Firm firm={firm} onChange={onFirmChange} />
    </main>
  );
}

// --- people ----------------------------------------------------------------------------------

function People({ firm, people, departments, onChange }: { firm: Workplace; people: Employee[]; departments: Department[]; onChange: () => void }) {
  const [editing, setEditing] = useState<Employee | "new" | null>(null);
  const [secret, setSecret] = useState<{ name: string; login: string; password: string } | null>(null);
  const names = Object.fromEntries(departments.map((d) => [d.id, d.name]));
  const current = editing && editing !== "new" ? people.find((p) => p.id === editing.id) ?? null : null;
  return (
    <section className="card settings-card">
      <h2>Pracownicy</h2>
      {secret && (
        <div className="notice secret">
          <p>
            Dane logowania dla <strong>{secret.name}</strong> — przekaż je teraz, później nie będzie ich widać:
          </p>
          <p className="num">
            login: <strong>{secret.login}</strong> · hasło: <strong>{secret.password}</strong>
          </p>
          <button className="btn" onClick={() => setSecret(null)}>Przekazane, ukryj</button>
        </div>
      )}
      <ul className="settings-list">
        {people.map((p) => (
          <li key={p.id} style={p.active ? undefined : { opacity: 0.6 }}>
            <span className="settings-name">{p.name}</span>
            <span className="muted">
              {ROLES.find(([r]) => r === p.role)?.[1]}
              {p.department && ` · ${names[p.department] ?? ""}`}
              {p.login ? ` · login ${p.login}` : " · bez logowania"}
              {p.card ? ` · karta ${p.card}` : ""}
              {!p.active && " · zarchiwizowany"}
            </span>
            <span className="settings-actions">
              <button className="btn quiet" onClick={() => setEditing(p)}>Zmień</button>
            </span>
          </li>
        ))}
      </ul>
      <button className="btn primary" style={{ justifySelf: "start" }} onClick={() => setEditing("new")}>Dodaj pracownika</button>
      {editing && (
        <PersonDialog
          firm={firm}
          person={editing === "new" ? null : current}
          departments={departments}
          onClose={() => setEditing(null)}
          onSaved={(result) => {
            onChange();
            if (result?.password && result.login) setSecret({ name: result.name, login: result.login, password: result.password });
          }}
        />
      )}
    </section>
  );
}

function PersonDialog({ firm, person, departments, onClose, onSaved }: {
  firm: Workplace;
  person: Employee | null;
  departments: Department[];
  onClose: () => void;
  onSaved: (result?: Employee) => void;
}) {
  const toast = useToast();
  const [error, setError] = useState("");
  const [confirming, setConfirming] = useState(false);
  const unknown = useApi<UnknownCard[]>(person ? `/w/${firm.id}/unknown-cards/` : null);
  const base = `/w/${firm.id}/employees/${person?.id}/`;
  const act = async (fn: () => Promise<Employee | { archived?: boolean }>, message: string, close = false) => {
    try {
      const result = await fn();
      setError("");
      toast(message);
      onSaved("id" in result ? (result as Employee) : undefined);
      if (close) onClose();
    } catch (err) {
      setError((err as Error).message);
    }
  };

  const submit = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const body = { name: f.get("name"), department: f.get("department") || null, role: f.get("role"), login: f.get("login") || undefined, active: person ? f.get("active") === "on" : undefined };
    act(
      () => (person ? api.patch<Employee>(base, body) : api.post<Employee>(`/w/${firm.id}/employees/`, body)),
      person ? "Zapisano." : "Dodano pracownika.",
      true,
    );
  };
  const assign = (uid: string) => act(() => api.post<Employee>(`${base}card/`, { uid }), "Karta przypisana — działa od razu w kiosku.");

  return (
    <Dialog open onClose={onClose} title={person ? person.name : "Nowy pracownik"}>
      <form onSubmit={submit} style={{ display: "grid", gap: 14 }}>
        {error && <p className="error">{error}</p>}
        <Field label="Imię i nazwisko">{(id) => <input id={id} name="name" type="text" required maxLength={120} defaultValue={person?.name ?? ""} />}</Field>
        <div className="grid-2">
          <Field label="Dział">
            {(id) => (
              <select id={id} name="department" defaultValue={person?.department ?? ""}>
                <option value="">— bez działu —</option>
                {departments.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
              </select>
            )}
          </Field>
          <Field label="Rola">
            {(id) => (
              <select id={id} name="role" defaultValue={person?.role ?? "pracownik"}>
                {ROLES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </select>
            )}
          </Field>
        </div>
        {!person && (
          <Field label="Login (opcjonalnie)" hint="Potrzebny do odbić telefonem i do panelu. Osoba z samą kartą w kiosku go nie potrzebuje. Hasło wygenerujemy.">
            {(id) => <input id={id} name="login" type="text" maxLength={40} autoCapitalize="none" placeholder="np. anna.nowak" />}
          </Field>
        )}
        {person && (
          <label className="check">
            <input name="active" type="checkbox" defaultChecked={person.active} /> Aktywny (zarchiwizowany nie loguje się i nie odbija)
          </label>
        )}
        <div className="dialog-actions">
          <button type="button" className="btn quiet" onClick={onClose}>Anuluj</button>
          <button className="btn primary">{person ? "Zapisz" : "Dodaj"}</button>
        </div>
      </form>
      {person && (
        <>
          <h3 className="section-title">Logowanie</h3>
          {person.login ? (
            <div className="inline-form">
              <span>Login: <strong>{person.login}</strong></span>
              <button className="btn" onClick={() => act(() => api.post<Employee>(`${base}account/`, {}), "Nowe hasło wygenerowane.")}>Nowe hasło</button>
              {!person.me && <button className="btn quiet" onClick={() => act(() => api.delete<Employee>(`${base}account/`, {}), "Logowanie odebrane.")}>Odbierz logowanie</button>}
            </div>
          ) : (
            <form className="inline-form" onSubmit={(e) => { e.preventDefault(); act(() => api.post<Employee>(`${base}account/`, { login: new FormData(e.currentTarget).get("login") }), "Login utworzony."); }}>
              <Field label="Nowy login">{(id) => <input id={id} name="login" type="text" required maxLength={40} autoCapitalize="none" />}</Field>
              <button className="btn">Utwórz login</button>
            </form>
          )}
          <h3 className="section-title">Karta / brelok NFC</h3>
          {person.card ? (
            <div className="inline-form">
              <span>Przypisana karta <strong>{person.card}</strong></span>
              <button className="btn quiet" onClick={() => act(() => api.delete<Employee>(`${base}card/`, {}), "Karta odebrana.")}>Odbierz kartę</button>
            </div>
          ) : (
            <>
              {(unknown.data ?? []).length > 0 ? (
                <ul className="plain-list">
                  {unknown.data!.map((c) => (
                    <li key={c.uid}>
                      <span>Nieznana karta <strong>…{c.uid.slice(-4)}</strong> <span className="muted">— {c.point}, {new Date(c.at).toLocaleTimeString("pl-PL", { hour: "2-digit", minute: "2-digit" })}</span></span>
                      <button className="btn" onClick={() => assign(c.uid)}>Przypisz</button>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="hint">Przyłóż nową kartę do czytnika w kiosku — pojawi się tutaj do przypisania (odśwież okno). Albo wpisz numer karty ręcznie.</p>
              )}
              <form className="inline-form" onSubmit={(e) => { e.preventDefault(); assign(String(new FormData(e.currentTarget).get("uid"))); }}>
                <Field label="Numer karty">{(id) => <input id={id} name="uid" type="text" required maxLength={64} autoCapitalize="characters" />}</Field>
                <button className="btn">Przypisz</button>
              </form>
            </>
          )}
          {!person.me && (
            <div className="dialog-actions">
              {confirming ? (
                <button className="btn danger" onClick={() => act(() => api.delete<{ archived: boolean }>(base, {}), "Usunięto. Kto ma odbicia, zostaje w archiwum — ewidencja czasu nie znika.", true)}>
                  Tak, usuń (osoba z odbiciami trafi do archiwum)
                </button>
              ) : (
                <button className="btn danger" onClick={() => setConfirming(true)}>Usuń pracownika</button>
              )}
            </div>
          )}
        </>
      )}
    </Dialog>
  );
}

// --- departments -----------------------------------------------------------------------------

function Departments({ firm, departments, onChange }: { firm: Workplace; departments: Department[]; onChange: () => void }) {
  const toast = useToast();
  const [error, setError] = useState("");
  const [editing, setEditing] = useState<string | null>(null);
  const run = async (fn: () => Promise<unknown>, message: string) => {
    try {
      await fn();
      setError("");
      setEditing(null);
      toast(message);
      onChange();
    } catch (err) {
      setError((err as Error).message);
    }
  };
  const form = (d: Department | null) => (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const body = { name: f.get("name"), color: f.get("color") };
    run(() => (d ? api.patch(`/w/${firm.id}/departments/${d.id}/`, body) : api.post(`/w/${firm.id}/departments/`, body)), d ? "Dział zapisany." : "Dział dodany.");
    if (!d) e.currentTarget.reset();
  };
  const fields = (d: Department | null) => (
    <>
      <Field label="Nazwa działu">{(id) => <input id={id} name="name" type="text" required maxLength={80} defaultValue={d?.name ?? ""} />}</Field>
      <Field label="Kolor">
        {(id) => (
          <>
            <input id={id} name="color" type="color" defaultValue={d?.color ?? SWATCHES[departments.length % SWATCHES.length]} list={`swatches-${d?.id ?? "new"}`} style={{ width: 56, height: 40, padding: 2 }} />
            <datalist id={`swatches-${d?.id ?? "new"}`}>{SWATCHES.map((c) => <option key={c} value={c} />)}</datalist>
          </>
        )}
      </Field>
    </>
  );
  return (
    <section className="card settings-card">
      <h2>Działy</h2>
      {error && <p className="error">{error}</p>}
      <ul className="settings-list">
        {departments.map((d) =>
          editing === d.id ? (
            <li key={d.id}>
              <form className="inline-form" onSubmit={form(d)} style={{ width: "100%" }}>
                {fields(d)}
                <button className="btn primary">Zapisz</button>
                <button type="button" className="btn quiet" onClick={() => setEditing(null)}>Anuluj</button>
              </form>
            </li>
          ) : (
            <li key={d.id}>
              <span className="settings-name"><span className="swatch" style={{ background: d.color }} />{d.name}</span>
              <span className="muted">{d.people} os.</span>
              <span className="settings-actions">
                <button className="btn quiet" onClick={() => setEditing(d.id)}>Zmień</button>
                <button className="btn quiet" onClick={() => run(() => api.delete(`/w/${firm.id}/departments/${d.id}/`, {}), "Dział usunięty.")}>Usuń</button>
              </span>
            </li>
          ),
        )}
      </ul>
      <form className="inline-form" onSubmit={form(null)}>
        {fields(null)}
        <button className="btn">Dodaj dział</button>
      </form>
    </section>
  );
}

// --- clock points ----------------------------------------------------------------------------

function Qr({ url }: { url: string }) {
  const [svg, setSvg] = useState("");
  useEffect(() => {
    QRCode.toString(url, { type: "svg", margin: 0, color: { dark: "#2b2d33", light: "#0000" } }).then(setSvg);
  }, [url]);
  return <div className="qr-box" dangerouslySetInnerHTML={{ __html: svg }} />;
}

function Points({ firm, points, onChange }: { firm: Workplace; points: ClockPoint[]; onChange: () => void }) {
  const toast = useToast();
  const [error, setError] = useState("");
  const [kioskLink, setKioskLink] = useState<{ id: string; url: string } | null>(null);
  const [renaming, setRenaming] = useState<string | null>(null);
  const [confirm, setConfirm] = useState<string | null>(null);
  const run = async <T,>(fn: () => Promise<T>, message: string): Promise<T | undefined> => {
    try {
      const result = await fn();
      setError("");
      toast(message);
      onChange();
      return result;
    } catch (err) {
      setError((err as Error).message);
    }
  };
  const base = (p: ClockPoint) => `/w/${firm.id}/points/${p.id}/`;
  const write = async (url: string) => {
    toast("Przyłóż telefon do naklejki…");
    try {
      await writeUrl(url);
      toast("Zapisano link na naklejce. Sprawdź: przyłóż telefon jeszcze raz.");
    } catch (err) {
      setError(`Nie udało się zapisać naklejki: ${(err as Error).message}`);
    }
  };

  return (
    <section className="card settings-card">
      <h2>Punkty odbić (NFC)</h2>
      <p className="hint">
        Punkt to wejście do pracy. <strong>Naklejka NFC</strong> (NTAG213/215, kilka złotych) z linkiem punktu: pracownik przykłada swój telefon, jest zalogowany — odbicie.
        <strong> Kiosk</strong>: tablet przy wejściu z czytnikiem kart USB (działa jak klawiatura) albo Android z Chrome — pracownik przykłada kartę lub brelok.
      </p>
      {error && <p className="error">{error}</p>}
      {points.map((p) => {
        const tagUrl = `${window.location.origin}${p.tag_path}`;
        return (
          <div key={p.id} className="link-card">
            <Qr url={tagUrl} />
            <div style={{ display: "grid", gap: 10 }}>
              {renaming === p.id ? (
                <form className="inline-form" onSubmit={(e) => { e.preventDefault(); run(() => api.patch(base(p), { name: new FormData(e.currentTarget).get("name") }), "Zapisano nazwę.").then(() => setRenaming(null)); }}>
                  <Field label="Nazwa punktu">{(id) => <input id={id} name="name" type="text" required maxLength={120} defaultValue={p.name} />}</Field>
                  <button className="btn primary">Zapisz</button>
                </form>
              ) : (
                <h2>{p.name} <span className="muted" style={{ fontWeight: 400, fontSize: 14 }}>· odbić: {p.punches}</span></h2>
              )}
              <div className="url"><code>{tagUrl}</code></div>
              <div className="inline-form">
                {hasWebNfc() && <button className="btn primary" onClick={() => write(tagUrl)}>Zapisz na naklejce NFC</button>}
                <button className="btn" onClick={() => navigator.clipboard?.writeText(tagUrl).then(() => toast("Link skopiowany."))}>Kopiuj link naklejki</button>
                <button className="btn quiet" onClick={() => run(() => api.post(`${base(p)}tag/`), "Nowy link. Stara naklejka przestała działać — zapisz nową.")}>Nowy link (stara naklejka przestaje działać)</button>
              </div>
              {!hasWebNfc() && <p className="hint">Link zapiszesz na naklejce aplikacją NFC Tools (Android/iPhone) jako rekord „URL”. Na Androidzie w Chrome ten przycisk zrobi to sam.</p>}
              <div className="inline-form">
                <span>Kiosk: <strong>{p.kiosk ? "włączony" : "brak"}</strong></span>
                <button className="btn" onClick={() => run(() => api.post<ClockPoint>(`${base(p)}kiosk/`), p.kiosk ? "Nowy link kiosku — stary przestał działać." : "Kiosk włączony.").then((r) => r?.kiosk_path && setKioskLink({ id: p.id, url: `${window.location.origin}${r.kiosk_path}` }))}>
                  {p.kiosk ? "Nowy link kiosku" : "Włącz kiosk"}
                </button>
                {p.kiosk && <button className="btn quiet" onClick={() => run(() => api.delete(`${base(p)}kiosk/`, {}), "Kiosk wyłączony.")}>Wyłącz kiosk</button>}
              </div>
              {kioskLink?.id === p.id && (
                <div className="notice secret">
                  <p>Otwórz ten link na tablecie przy wejściu (zeskanuj kod aparatem tabletu). Pokazujemy go tylko teraz — kto go ma, może odbijać karty.</p>
                  <div className="link-card" style={{ padding: 0, border: 0, background: "none" }}>
                    <Qr url={kioskLink.url} />
                    <div className="url"><code>{kioskLink.url}</code></div>
                  </div>
                  <button className="btn" onClick={() => setKioskLink(null)}>Gotowe, ukryj</button>
                </div>
              )}
              <div className="inline-form">
                <button className="btn quiet" onClick={() => setRenaming(p.id)}>Zmień nazwę</button>
                {confirm === p.id ? (
                  <button className="btn danger" onClick={() => run(() => api.delete(base(p), {}), "Punkt usunięty. Odbicia zostały w ewidencji.")}>Tak, usuń punkt (naklejka i kiosk przestaną działać)</button>
                ) : (
                  <button className="btn quiet" onClick={() => setConfirm(p.id)}>Usuń punkt</button>
                )}
              </div>
            </div>
          </div>
        );
      })}
      <form className="inline-form" onSubmit={(e) => { e.preventDefault(); const form = e.currentTarget; run(() => api.post(`/w/${firm.id}/points/`, { name: new FormData(form).get("name") }), "Punkt dodany.").then(() => form.reset()); }}>
        <Field label="Nowy punkt odbić">{(id) => <input id={id} name="name" type="text" required maxLength={120} placeholder="np. Wejście dla personelu" />}</Field>
        <button className="btn">Dodaj punkt</button>
      </form>
    </section>
  );
}

// --- the firm --------------------------------------------------------------------------------

function Firm({ firm, onChange }: { firm: Workplace; onChange: () => void }) {
  const toast = useToast();
  const [error, setError] = useState("");
  const [deleting, setDeleting] = useState(false);
  const save = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    try {
      await api.patch(`/w/${firm.id}/`, { name: f.get("name"), timezone: f.get("timezone") });
      toast("Zapisano.");
      onChange();
    } catch (err) {
      setError((err as Error).message);
    }
  };
  const remove = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    try {
      const r = await api.delete<{ account_removed: boolean }>(`/w/${firm.id}/`, { confirm: new FormData(e.currentTarget).get("confirm") });
      window.location.assign(r.account_removed ? "/?usunieto" : "/panel");
    } catch (err) {
      setError((err as Error).message);
    }
  };
  return (
    <section className="card settings-card">
      <h2>Firma</h2>
      {error && <p className="error">{error}</p>}
      <form className="inline-form" onSubmit={save}>
        <Field label="Nazwa firmy">{(id) => <input id={id} name="name" type="text" required maxLength={200} defaultValue={firm.name} />}</Field>
        <Field label="Strefa czasowa">{(id) => <input id={id} name="timezone" type="text" required maxLength={64} defaultValue={firm.timezone} />}</Field>
        <button className="btn">Zapisz</button>
      </form>
      <div className="inline-form">
        <a className="btn" href={`/api/w/${firm.id}/export/`} download={`grafik-${firm.name}.json`}>Pobierz wszystkie dane (JSON)</a>
        <button className="btn danger" onClick={() => setDeleting(true)}>Usuń firmę i wszystkie dane</button>
      </div>
      <Dialog open={deleting} onClose={() => setDeleting(false)} title="Usunąć firmę?">
        <form onSubmit={remove} style={{ display: "grid", gap: 14 }}>
          <p>
            Znikną od razu: grafik, wnioski, niedyspozycyjność, <strong>wszystkie odbicia</strong>, punkty NFC i konta pracowników bez innych firm. Ewidencję czasu pracy pracodawca musi przechowywać — najpierw pobierz CSV z „Czasu pracy” i dane w JSON.
          </p>
          <Field label={`Wpisz nazwę firmy: ${firm.name}`}>{(id) => <input id={id} name="confirm" type="text" required autoComplete="off" />}</Field>
          <div className="dialog-actions">
            <button type="button" className="btn quiet" onClick={() => setDeleting(false)}>Anuluj</button>
            <button className="btn danger">Usuń na zawsze</button>
          </div>
        </form>
      </Dialog>
    </section>
  );
}
