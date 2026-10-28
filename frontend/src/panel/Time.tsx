// Czas pracy: planned vs. punched hours per month. Corrections are new entries with a reason —
// the original punch stays visible, crossed out.
import { useState, type FormEvent } from "react";
import { api, useApi, type Department, type Punch, type Report, type ReportPerson, type Workplace } from "./api.ts";
import { addMonths, dayLabel, hours, monthLabel } from "./time.ts";
import { Dialog, Field, useToast } from "./ui.tsx";

export default function Time({ firm }: { firm: Workplace }) {
  const [month, setMonth] = useState<string | null>(null);
  const [department, setDepartment] = useState("");
  const query = new URLSearchParams({ ...(month ? { month } : {}), ...(department ? { department } : {}) });
  const report = useApi<Report>(`/w/${firm.id}/report/?${query}`);
  const departments = useApi<Department[]>(`/w/${firm.id}/departments/`);
  const [open, setOpen] = useState<string | null>(null);
  const r = report.data;
  const person = r?.people.find((p) => p.employee === open) ?? null;
  const director = firm.role === "dyrektor" || firm.role === "admin";

  return (
    <main className="page">
      <div className="page-head">
        <div>
          <h1>Czas pracy</h1>
          <p>Godziny z grafiku i z odbić NFC. Kliknij osobę, żeby zobaczyć dni i odbicia{firm.role !== "pracownik" && " albo wpisać korektę"}.</p>
        </div>
        <div className="actions">
          {r && <a className="btn" href={`/api/w/${firm.id}/report.csv?${new URLSearchParams({ month: r.month, ...(department ? { department } : {}) })}`}>Pobierz CSV</a>}
          <button className="btn" onClick={() => window.print()}>Drukuj</button>
        </div>
      </div>
      <div className="week-nav">
        <button className="btn" onClick={() => r && setMonth(addMonths(r.month, -1))} aria-label="Poprzedni miesiąc">←</button>
        <strong>{r ? monthLabel(r.month) : "…"}</strong>
        <button className="btn" onClick={() => r && setMonth(addMonths(r.month, 1))} aria-label="Następny miesiąc">→</button>
        {director && (departments.data ?? []).length > 0 && (
          <select value={department} onChange={(e) => setDepartment(e.target.value)} aria-label="Dział">
            <option value="">Wszystkie działy</option>
            {departments.data!.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
          </select>
        )}
      </div>
      {report.error && <p className="error">{report.error}</p>}
      {r && (
        <table className="report">
          <thead>
            <tr>
              <th>Osoba</th>
              <th>Dział</th>
              <th>Plan</th>
              <th>Przepracowane</th>
              <th>Różnica</th>
              <th>Do wyjaśnienia</th>
            </tr>
          </thead>
          <tbody>
            {r.people.map((p) => (
              <tr key={p.employee} className="clickable" onClick={() => setOpen(p.employee)} tabIndex={0} onKeyDown={(e) => e.key === "Enter" && setOpen(p.employee)}>
                <td><strong>{p.name}</strong></td>
                <td>{p.department ?? "—"}</td>
                <td>{hours(p.planned)}</td>
                <td>{hours(p.worked)}</td>
                <td>{p.worked >= p.planned ? "+" : "−"}{hours(Math.abs(p.worked - p.planned))}</td>
                <td className={p.problems ? "problem" : undefined}>{p.problems || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {r && r.people.length === 0 && <p className="empty">Brak osób w tym zestawieniu.</p>}
      {person && r && <PersonDialog firm={firm} person={person} month={r.month} onClose={() => setOpen(null)} onChanged={report.reload} />}
    </main>
  );
}

function PersonDialog({ firm, person, month, onClose, onChanged }: { firm: Workplace; person: ReportPerson; month: string; onClose: () => void; onChanged: () => void }) {
  const toast = useToast();
  const punches = useApi<Punch[]>(`/w/${firm.id}/punches/?employee=${person.employee}&month=${month}`);
  const [error, setError] = useState("");
  const [voiding, setVoiding] = useState<Punch | null>(null);
  const canCorrect = firm.role !== "pracownik"; // the backend narrows it to the manager's own department
  const refresh = () => {
    punches.reload();
    onChanged();
  };

  const add = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const form = e.currentTarget;
    const f = new FormData(form);
    try {
      await api.post(`/w/${firm.id}/punches/`, { employee: person.employee, kind: f.get("kind"), at: f.get("at"), note: f.get("note") });
      setError("");
      form.reset();
      toast("Odbicie dopisane jako korekta.");
      refresh();
    } catch (err) {
      setError((err as Error).message);
    }
  };
  const voidIt = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    try {
      await api.post(`/w/${firm.id}/punches/${voiding!.id}/void/`, { note: new FormData(e.currentTarget).get("note") });
      setVoiding(null);
      toast("Odbicie anulowane. Zostaje widoczne jako przekreślone.");
      refresh();
    } catch (err) {
      setError((err as Error).message);
    }
  };

  return (
    <Dialog open onClose={onClose} title={`${person.name} — ${monthLabel(month)}`} side>
      <p className="num">Plan <strong>{hours(person.planned)}</strong> · przepracowane <strong>{hours(person.worked)}</strong></p>
      {error && <p className="error">{error}</p>}
      <table className="report">
        <thead>
          <tr><th>Dzień</th><th>Plan</th><th>Odbicia</th><th>Godz.</th></tr>
        </thead>
        <tbody>
          {person.days.map((d) => (
            <tr key={d.date}>
              <td>{dayLabel(d.date)}</td>
              <td>{d.shifts.map((s) => `${s.start}–${s.end}`).join(", ") || "—"}</td>
              <td>
                {d.sessions.map((s, i) => (
                  <div key={i} className={s.problem ? "problem" : undefined}>
                    {s.start ?? "?"}–{s.end ?? (s.ongoing ? "teraz" : "?")}{s.problem && <strong style={{ color: "var(--russet)" }}> · {s.problem}</strong>}
                  </div>
                ))}
                {d.sessions.length === 0 && "—"}
              </td>
              <td>{hours(d.worked)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <h3 className="section-title">Odbicia</h3>
      <ul className="plain-list">
        {(punches.data ?? []).map((p) => (
          <li key={p.id}>
            <span className={p.voided ? "punch-void" : undefined}>
              {p.local} · {p.kind_label}
              <span className="muted"> · {p.source_label}{p.point && `, ${p.point}`}{p.note && ` · „${p.note}”`}{p.recorded_by && ` · ${p.recorded_by}`}</span>
            </span>
            {canCorrect && p.kind !== "void" && !p.voided && <button className="btn quiet" onClick={() => setVoiding(p)}>Anuluj</button>}
          </li>
        ))}
        {punches.data?.length === 0 && <li className="muted">Brak odbić w tym miesiącu.</li>}
      </ul>
      {voiding && (
        <form className="inline-form" onSubmit={voidIt}>
          <Field label={`Powód anulowania: ${voiding.local} ${voiding.kind_label.toLowerCase()}`}>{(id) => <input id={id} name="note" type="text" required maxLength={200} autoFocus />}</Field>
          <button className="btn danger">Anuluj odbicie</button>
          <button type="button" className="btn quiet" onClick={() => setVoiding(null)}>Zostaw</button>
        </form>
      )}
      {canCorrect && (
        <form onSubmit={add} style={{ display: "grid", gap: 12 }}>
          <h3 className="section-title">Dopisz odbicie <small>(ktoś zapomniał karty, nie działał internet)</small></h3>
          <div className="grid-2">
            <Field label="Rodzaj">
              {(id) => (
                <select id={id} name="kind">
                  <option value="in">Wejście</option>
                  <option value="out">Wyjście</option>
                </select>
              )}
            </Field>
            <Field label="Kiedy">{(id) => <input id={id} name="at" type="datetime-local" required />}</Field>
          </div>
          <Field label="Powód korekty">{(id) => <input id={id} name="note" type="text" required maxLength={200} />}</Field>
          <button className="btn">Dopisz</button>
        </form>
      )}
    </Dialog>
  );
}
