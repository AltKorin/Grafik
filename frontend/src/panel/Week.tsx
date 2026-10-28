// Grafik: people × days of one week. Managers click a cell to add a shift, a shift to change it.
import { useMemo, useState, type FormEvent } from "react";
import { api, useApi, type Away, type Department, type Shift, type Week, type Workplace } from "./api.ts";
import { AwayDialog } from "./Away.tsx";
import { addDays, dayLabel, hours, inRange, shiftMinutes } from "./time.ts";
import { Dialog, Field, dateRange, useToast } from "./ui.tsx";

type Person = Week["people"][number];
type Editing =
  | { kind: "shift"; person: Person; day: string; shift: Shift | null }
  | { kind: "away"; person: Person; day: string; away: Away | null };

export default function WeekPage({ firm }: { firm: Workplace }) {
  const toast = useToast();
  const [week, setWeek] = useState<string | null>(null);
  const [department, setDepartment] = useState("");
  const query = new URLSearchParams({ ...(week ? { week } : {}), ...(department ? { department } : {}) });
  const data = useApi<Week>(`/w/${firm.id}/week/?${query}`);
  const departments = useApi<Department[]>(`/w/${firm.id}/departments/`);
  const [editing, setEditing] = useState<Editing | null>(null);
  const colors = Object.fromEntries((departments.data ?? []).map((d) => [d.id, d.color]));
  const w = data.data;
  const manager = firm.role !== "pracownik";
  const director = firm.role === "dyrektor" || firm.role === "admin";

  // Quick hours: the start–end pairs already used this week, most frequent first.
  const presets = useMemo(() => {
    const count = new Map<string, number>();
    for (const s of w?.shifts ?? []) count.set(`${s.start}–${s.end}`, (count.get(`${s.start}–${s.end}`) ?? 0) + 1);
    return [...count.entries()].sort((a, b) => b[1] - a[1]).slice(0, 4).map(([k]) => k);
  }, [w]);

  const copy = async () => {
    if (!w) return;
    try {
      const r = await api.post<{ copied: number; skipped: string[] }>(`/w/${firm.id}/week/copy/`, { week: w.week });
      toast(r.skipped.length ? `Skopiowano ${r.copied}. Pominięto ${r.skipped.length}: ${r.skipped[0]}` : `Skopiowano zmian: ${r.copied}.`);
      data.reload();
    } catch (err) {
      toast((err as Error).message);
    }
  };

  return (
    <main className="page" style={{ maxWidth: 1400 }}>
      <div className="page-head">
        <div>
          <h1>Grafik</h1>
          <p>{manager ? "Kliknij dzień, żeby dodać zmianę; kliknij zmianę, żeby ją zmienić lub usunąć." : "Grafik twojego działu. Zmiany zgłaszasz we Wnioskach."}</p>
        </div>
        <div className="actions">
          {manager && <button className="btn" onClick={copy} title="Dodaje zmiany z poprzedniego tygodnia; istniejące zostają, konflikty są pomijane">Skopiuj poprzedni tydzień</button>}
          <button className="btn" onClick={() => window.print()}>Drukuj</button>
        </div>
      </div>
      <div className="week-nav">
        <button className="btn" onClick={() => w && setWeek(addDays(w.week, -7))} aria-label="Poprzedni tydzień">←</button>
        <strong>{w ? dateRange(w.days[0], w.days[6]) : "…"}</strong>
        <button className="btn" onClick={() => w && setWeek(addDays(w.week, 7))} aria-label="Następny tydzień">→</button>
        <button className="btn quiet" onClick={() => setWeek(null)}>Ten tydzień</button>
        {director && (departments.data ?? []).length > 0 && (
          <select value={department} onChange={(e) => setDepartment(e.target.value)} aria-label="Dział">
            <option value="">Wszystkie działy</option>
            {departments.data!.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
          </select>
        )}
      </div>
      {data.error && <p className="error">{data.error}</p>}
      {w && w.people.length === 0 && (
        <div className="empty">
          <p>W grafiku nie ma jeszcze nikogo.</p>
          {director && <p className="hint">Dodaj działy i pracowników w zakładce „Zespół i NFC”.</p>}
        </div>
      )}
      {w && w.people.length > 0 && (
        <div className="grid-wrap">
          <table className="week">
            <thead>
              <tr>
                <th>Osoba</th>
                {w.days.map((d) => <th key={d} className={d === w.today ? "today" : undefined}>{dayLabel(d)}</th>)}
              </tr>
            </thead>
            <tbody>
              {w.people.map((p) => {
                const mine = w.shifts.filter((s) => s.employee === p.id);
                const total = mine.reduce((sum, s) => sum + s.minutes, 0);
                return (
                  <tr key={p.id}>
                    <td>
                      <div className="person">
                        {p.department && <span className="swatch" style={{ background: colors[p.department] }} />}
                        {p.name}
                        <small className="num">{hours(total)} h w tygodniu</small>
                      </div>
                    </td>
                    {w.days.map((d) => {
                      const shifts = mine.filter((s) => s.date === d);
                      const away = w.unavailability.filter((a) => a.employee === p.id && inRange(d, a.date_from, a.date_to));
                      return (
                        <td key={d}>
                          <div className="cell">
                            {away.map((a) => (
                              <button key={a.id} className="chip away" disabled={!p.editable} onClick={() => setEditing({ kind: "away", person: p, day: d, away: a })}>
                                {a.kind_label}
                                {a.note && <small>{a.note}</small>}
                              </button>
                            ))}
                            {shifts.map((s) => (
                              <button
                                key={s.id}
                                className={`chip${away.length ? " clash" : ""}`}
                                style={{ ["--dept" as string]: p.department ? colors[p.department] : undefined }}
                                disabled={!p.editable}
                                title={away.length ? "Konflikt: zgłoszona niedyspozycyjność" : undefined}
                                onClick={() => setEditing({ kind: "shift", person: p, day: d, shift: s })}
                              >
                                {s.start}–{s.end}
                                {s.notes && <small>{s.notes}</small>}
                              </button>
                            ))}
                            {p.editable && (
                              <button className="add no-print" aria-label={`Dodaj zmianę: ${p.name}, ${dayLabel(d)}`} onClick={() => setEditing({ kind: "shift", person: p, day: d, shift: null })}>
                                <span className="add-hint">+</span>
                              </button>
                            )}
                          </div>
                        </td>
                      );
                    })}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
      {editing?.kind === "shift" && (
        <ShiftDialog
          firmId={firm.id}
          editing={editing}
          presets={presets}
          onClose={() => setEditing(null)}
          onSaved={data.reload}
          onAway={() => setEditing({ kind: "away", person: editing.person, day: editing.day, away: null })}
        />
      )}
      {editing?.kind === "away" && (
        <AwayDialog
          firmId={firm.id}
          away={editing.away}
          employee={editing.person}
          defaultDay={editing.day}
          onClose={() => setEditing(null)}
          onSaved={data.reload}
        />
      )}
    </main>
  );
}

function ShiftDialog({ firmId, editing, presets, onClose, onSaved, onAway }: {
  firmId: string;
  editing: Extract<Editing, { kind: "shift" }>;
  presets: string[];
  onClose: () => void;
  onSaved: () => void;
  onAway: () => void;
}) {
  const toast = useToast();
  const { person, shift } = editing;
  const [start, setStart] = useState(shift?.start ?? "08:00");
  const [end, setEnd] = useState(shift?.end ?? "16:00");
  const [error, setError] = useState("");
  const [confirming, setConfirming] = useState(false);
  const minutes = start && end && start !== end ? shiftMinutes(start, end) : 0;

  const submit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const body = { employee: person.id, date: f.get("date"), start, end, notes: f.get("notes") };
    try {
      if (shift) await api.patch(`/w/${firmId}/shifts/${shift.id}/`, body);
      else await api.post(`/w/${firmId}/shifts/`, body);
      toast(shift ? "Zmiana zapisana." : `Dodano zmianę: ${person.name}, ${start}–${end}.`);
      onSaved();
      onClose();
    } catch (err) {
      setError((err as Error).message);
    }
  };
  const remove = async () => {
    try {
      await api.delete(`/w/${firmId}/shifts/${shift!.id}/`, {});
      toast("Zmiana usunięta z grafiku.");
      onSaved();
      onClose();
    } catch (err) {
      setError((err as Error).message);
    }
  };

  return (
    <Dialog open onClose={onClose} title={`${shift ? "Zmiana" : "Nowa zmiana"} — ${person.name}`}>
      <form onSubmit={submit} style={{ display: "grid", gap: 14 }}>
        {error && <p className="error">{error}</p>}
        <Field label="Dzień">{(id) => <input id={id} name="date" type="date" required defaultValue={shift?.date ?? editing.day} />}</Field>
        {presets.length > 0 && (
          <div className="inline-form">
            {presets.map((p) => (
              <button key={p} type="button" className="btn quiet" onClick={() => { const [a, b] = p.split("–"); setStart(a); setEnd(b); }}>
                {p}
              </button>
            ))}
          </div>
        )}
        <div className="grid-2">
          <Field label="Od">{(id) => <input id={id} type="time" required value={start} onChange={(e) => setStart(e.target.value)} />}</Field>
          <Field label="Do" hint={end && start && end <= start && start !== end ? "Kończy się następnego dnia." : undefined}>
            {(id) => <input id={id} type="time" required value={end} onChange={(e) => setEnd(e.target.value)} />}
          </Field>
        </div>
        <p className="hint num">Długość: {hours(minutes)} h</p>
        <Field label="Uwagi" hint="Np. „pomoc w kuchni”, „szkolenie”.">
          {(id) => <input id={id} name="notes" type="text" maxLength={200} defaultValue={shift?.notes ?? ""} />}
        </Field>
        {!shift && (
          <button type="button" className="btn quiet" style={{ justifySelf: "start" }} onClick={onAway}>
            Zamiast tego: zgłoś urlop / L4 tej osoby
          </button>
        )}
        <div className="dialog-actions">
          {shift && (confirming ? (
            <button type="button" className="btn danger" onClick={remove}>Tak, usuń zmianę</button>
          ) : (
            <button type="button" className="btn danger" onClick={() => setConfirming(true)}>Usuń</button>
          ))}
          <button type="button" className="btn quiet" onClick={onClose}>Anuluj</button>
          <button className="btn primary">{shift ? "Zapisz" : "Dodaj zmianę"}</button>
        </div>
      </form>
    </Dialog>
  );
}
