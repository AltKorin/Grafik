// Wnioski: a person asks (swap, cancel, other hours, extra shift); the department manager approves —
// approval changes the schedule at once.
import { useState, type FormEvent, type ReactNode } from "react";
import { api, useApi, type ChangeRequest, type RequestKind, type Shift, type Today, type Week, type Workplace } from "./api.ts";
import { dayLabel } from "./time.ts";
import { Dialog, Field, Segmented, useToast } from "./ui.tsx";

const KINDS: [RequestKind, string][] = [["swap", "Zamiana"], ["cancel", "Odwołanie"], ["modify", "Inne godziny"], ["add", "Dodatkowa zmiana"]];

function describe(r: ChangeRequest) {
  const s = r.shift ? `${dayLabel(r.shift.date)} ${r.shift.start}–${r.shift.end}` : "zmiana usunięta";
  const target = r.new_date ? `${dayLabel(r.new_date)} ${r.new_start}–${r.new_end}` : "";
  if (r.kind === "swap") return `${s} ↔ ${r.swap_shift ? `${r.swap_shift.name}, ${dayLabel(r.swap_shift.date)} ${r.swap_shift.start}–${r.swap_shift.end}` : "zmiana usunięta"}`;
  if (r.kind === "cancel") return s;
  if (r.kind === "modify") return `${s} → ${target}`;
  return target;
}

export default function Requests({ firm }: { firm: Workplace }) {
  const list = useApi<ChangeRequest[]>(`/w/${firm.id}/requests/`);
  const [editing, setEditing] = useState<ChangeRequest | "new" | null>(null);
  const [reviewing, setReviewing] = useState<{ r: ChangeRequest; approve: boolean } | null>(null);
  const toast = useToast();
  const all = list.data ?? [];
  const review = all.filter((r) => r.reviewable);
  const mine = all.filter((r) => r.mine);
  const others = all.filter((r) => !r.mine && !r.reviewable);

  const withdraw = async (r: ChangeRequest) => {
    try {
      await api.delete(`/w/${firm.id}/requests/${r.id}/`, {});
      toast("Wniosek wycofany.");
      list.reload();
    } catch (err) {
      toast((err as Error).message);
    }
  };

  return (
    <main className="page">
      <div className="page-head">
        <div>
          <h1>Wnioski</h1>
          <p>Zamiana, odwołanie albo inne godziny. Kierownik działu przyjmuje wniosek — grafik zmienia się od razu.</p>
        </div>
        {firm.me && <button className="btn primary" onClick={() => setEditing("new")}>Nowy wniosek</button>}
      </div>
      {list.error && <p className="error">{list.error}</p>}
      {review.length > 0 && (
        <Section title={`Do rozpatrzenia (${review.length})`}>
          {review.map((r) => (
            <Row key={r.id} r={r}>
              <button className="btn primary" onClick={() => setReviewing({ r, approve: true })}>Przyjmij</button>
              <button className="btn" onClick={() => setReviewing({ r, approve: false })}>Odrzuć</button>
            </Row>
          ))}
        </Section>
      )}
      {firm.me && (
        <Section title="Moje wnioski">
          {mine.length === 0 ? (
            <p className="hint">Nie masz wniosków.</p>
          ) : (
            mine.map((r) => (
              <Row key={r.id} r={r}>
                {r.status === "pending" && (
                  <>
                    <button className="btn quiet" onClick={() => setEditing(r)}>Zmień</button>
                    <button className="btn quiet" onClick={() => withdraw(r)}>Wycofaj</button>
                  </>
                )}
              </Row>
            ))
          )}
        </Section>
      )}
      {others.length > 0 && <Section title="Rozpatrzone w zespole">{others.map((r) => <Row key={r.id} r={r} />)}</Section>}
      {editing && <RequestDialog firm={firm} request={editing === "new" ? null : editing} onClose={() => setEditing(null)} onSaved={list.reload} />}
      {reviewing && <ReviewDialog firm={firm} {...reviewing} onClose={() => setReviewing(null)} onSaved={list.reload} />}
    </main>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="board-section">
      <h2>{title}</h2>
      <ul className="group-list">{children}</ul>
    </section>
  );
}

function Row({ r, children }: { r: ChangeRequest; children?: ReactNode }) {
  const badge = r.status === "pending" ? "unpublished" : r.status === "approved" ? "ok" : "";
  return (
    <li>
      <div className="group-row">
        <span className="name">{r.mine ? r.kind_label : `${r.name}: ${r.kind_label.toLowerCase()}`}</span>
        <span className="meta">
          {describe(r)}
          {r.reason && <> · „{r.reason}”</>}
          {r.reviewed_by && <> · {r.reviewed_by}{r.review_note && `: „${r.review_note}”`}</>}
        </span>
        <span className="badges">
          <span className={`badge ${badge}`}>{r.status_label}</span>
          {children}
        </span>
      </div>
    </li>
  );
}

function RequestDialog({ firm, request, onClose, onSaved }: { firm: Workplace; request: ChangeRequest | null; onClose: () => void; onSaved: () => void }) {
  const toast = useToast();
  const today = useApi<Today>(`/w/${firm.id}/today/`);
  const [kind, setKind] = useState<RequestKind>(request?.kind ?? "swap");
  const [shiftId, setShiftId] = useState(request?.shift?.id ?? "");
  const [error, setError] = useState("");
  const myShifts = today.data?.me?.shifts ?? [];
  const chosen = myShifts.find((s) => s.id === shiftId);
  // colleagues' shifts in the week of the chosen one (the same department, as the grid shows)
  const week = useApi<Week>(kind === "swap" && chosen ? `/w/${firm.id}/week/?week=${chosen.date}` : null);
  const theirs = (week.data?.shifts ?? []).filter((s) => s.employee !== firm.me && s.date >= (today.data?.date ?? ""));
  const names = Object.fromEntries((week.data?.people ?? []).map((p) => [p.id, p.name]));
  const needsShift = kind !== "add";
  const needsTimes = kind === "modify" || kind === "add";

  const submit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const body = {
      kind,
      shift: needsShift ? shiftId : null,
      swap_shift: kind === "swap" ? f.get("swap_shift") : null,
      new_date: needsTimes ? f.get("new_date") : null,
      new_start: needsTimes ? f.get("new_start") : null,
      new_end: needsTimes ? f.get("new_end") : null,
      reason: f.get("reason"),
    };
    try {
      if (request) await api.patch(`/w/${firm.id}/requests/${request.id}/`, body);
      else await api.post(`/w/${firm.id}/requests/`, body);
      toast("Wniosek wysłany do kierownika.");
      onSaved();
      onClose();
    } catch (err) {
      setError((err as Error).message);
    }
  };

  const label = (s: Shift) => `${dayLabel(s.date)} ${s.start}–${s.end}`;
  return (
    <Dialog open onClose={onClose} title={request ? "Zmień wniosek" : "Nowy wniosek"}>
      <form onSubmit={submit} style={{ display: "grid", gap: 14 }}>
        {error && <p className="error">{error}</p>}
        <Segmented label="Czego dotyczy" value={kind} options={KINDS} onChange={setKind} />
        {needsShift && (
          <Field label="Moja zmiana">
            {(id) => (
              <select id={id} required value={shiftId} onChange={(e) => setShiftId(e.target.value)}>
                <option value="">— wybierz —</option>
                {myShifts.map((s) => <option key={s.id} value={s.id}>{label(s)}</option>)}
              </select>
            )}
          </Field>
        )}
        {needsShift && myShifts.length === 0 && today.data && <p className="hint">Nie masz zmian w najbliższych dwóch tygodniach.</p>}
        {kind === "swap" && chosen && (
          <Field label="Zamiana z" hint="Zmiany osób z twojego działu w tym tygodniu.">
            {(id) => (
              <select id={id} name="swap_shift" required defaultValue={request?.swap_shift?.id ?? ""}>
                <option value="">— wybierz —</option>
                {theirs.map((s) => <option key={s.id} value={s.id}>{names[s.employee]}: {label(s)}</option>)}
              </select>
            )}
          </Field>
        )}
        {needsTimes && (
          <>
            <Field label="Dzień">{(id) => <input id={id} name="new_date" type="date" required defaultValue={request?.new_date ?? chosen?.date ?? ""} />}</Field>
            <div className="grid-2">
              <Field label="Od">{(id) => <input id={id} name="new_start" type="time" required defaultValue={request?.new_start ?? chosen?.start ?? "08:00"} />}</Field>
              <Field label="Do">{(id) => <input id={id} name="new_end" type="time" required defaultValue={request?.new_end ?? chosen?.end ?? "16:00"} />}</Field>
            </div>
          </>
        )}
        <Field label="Powód" hint="Kierownik zobaczy go przy decyzji.">
          {(id) => <input id={id} name="reason" type="text" maxLength={500} defaultValue={request?.reason ?? ""} />}
        </Field>
        <div className="dialog-actions">
          <button type="button" className="btn quiet" onClick={onClose}>Anuluj</button>
          <button className="btn primary">{request ? "Zapisz" : "Wyślij wniosek"}</button>
        </div>
      </form>
    </Dialog>
  );
}

function ReviewDialog({ firm, r, approve, onClose, onSaved }: { firm: Workplace; r: ChangeRequest; approve: boolean; onClose: () => void; onSaved: () => void }) {
  const toast = useToast();
  const [error, setError] = useState("");
  const submit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    try {
      await api.post(`/w/${firm.id}/requests/${r.id}/${approve ? "approve" : "reject"}/`, { note: new FormData(e.currentTarget).get("note") });
      toast(approve ? "Wniosek przyjęty — grafik już zmieniony." : "Wniosek odrzucony.");
      onSaved();
      onClose();
    } catch (err) {
      setError((err as Error).message);
    }
  };
  return (
    <Dialog open onClose={onClose} title={approve ? "Przyjąć wniosek?" : "Odrzucić wniosek?"}>
      <form onSubmit={submit} style={{ display: "grid", gap: 14 }}>
        {error && <p className="error">{error}</p>}
        <p>
          <strong>{r.name}</strong> — {r.kind_label.toLowerCase()}: {describe(r)}
          {r.reason && <><br />Powód: „{r.reason}”</>}
        </p>
        {approve && <p className="hint">Po przyjęciu grafik zmieni się od razu. Jeśli zmiana koliduje z urlopem lub inną zmianą, dostaniesz komunikat i nic się nie zmieni.</p>}
        <Field label="Uwaga dla pracownika (opcjonalnie)">{(id) => <input id={id} name="note" type="text" maxLength={500} />}</Field>
        <div className="dialog-actions">
          <button type="button" className="btn quiet" onClick={onClose}>Anuluj</button>
          <button className={`btn ${approve ? "primary" : "danger"}`}>{approve ? "Przyjmij" : "Odrzuć"}</button>
        </div>
      </form>
    </Dialog>
  );
}
