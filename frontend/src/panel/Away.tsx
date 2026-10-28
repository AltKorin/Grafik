// Niedyspozycyjność: one dialog for add / edit / delete, used on "Dziś" (own) and in the week grid (manager).
import { useState, type FormEvent } from "react";
import { api, type Away } from "./api.ts";
import { Dialog, Field, dateRange, useToast } from "./ui.tsx";
import { t } from "../i18n.ts";

export const AWAY_KINDS: [Away["kind"], string][] = [["urlop", t("Urlop")], ["l4", t("L4")], ["inne", t("Niedostępność")]];

export function AwayDialog({ firmId, away, employee, defaultDay, onClose, onSaved }: {
  firmId: string;
  away: Away | null; // null = new
  employee?: { id: string; name: string }; // manager reporting for someone; omitted = me
  defaultDay?: string;
  onClose: () => void;
  onSaved: () => void;
}) {
  const toast = useToast();
  const [error, setError] = useState("");
  const [confirming, setConfirming] = useState(false);
  const submit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const body = {
      employee: employee?.id ?? away?.employee,
      date_from: f.get("date_from"),
      date_to: f.get("date_to"),
      kind: f.get("kind"),
      note: f.get("note"),
    };
    try {
      const saved = away
        ? await api.patch<Away>(`/w/${firmId}/unavailability/${away.id}/`, body)
        : await api.post<Away>(`/w/${firmId}/unavailability/`, body);
      const clashes = saved.conflicts?.length ?? 0;
      toast(clashes === 1 ? t("Zapisano. W tym czasie jest zaplanowana zmiana — kierownik zobaczy konflikt w grafiku.")
        : clashes ? t("Zapisano. W tym czasie są zaplanowane zmiany ({n}) — kierownik zobaczy konflikt w grafiku.", { n: clashes })
        : t("Zapisano. Widać to od razu w grafiku."));
      onSaved();
      onClose();
    } catch (err) {
      setError((err as Error).message);
    }
  };
  const remove = async () => {
    if (!away) return;
    try {
      await api.delete(`/w/${firmId}/unavailability/${away.id}/`, {});
      toast(t("Zgłoszenie usunięte. Zmiany na te dni można już planować."));
      onSaved();
      onClose();
    } catch (err) {
      setError((err as Error).message);
    }
  };
  const from = away?.date_from ?? defaultDay ?? "";
  return (
    <Dialog open onClose={onClose} title={away ? t("Zmień zgłoszenie") : employee ? `${t("Niedyspozycyjność")} — ${employee.name}` : t("Zgłoś niedyspozycyjność")}>
      <form onSubmit={submit} style={{ display: "grid", gap: 14 }}>
        {error && <p className="error">{error}</p>}
        <Field label={t("Rodzaj")}>
          {(id) => (
            <select id={id} name="kind" defaultValue={away?.kind ?? "urlop"}>
              {AWAY_KINDS.map(([v, label]) => <option key={v} value={v}>{label}</option>)}
            </select>
          )}
        </Field>
        <div className="grid-2">
          <Field label={t("Od")}>{(id) => <input id={id} name="date_from" type="date" required defaultValue={from} />}</Field>
          <Field label={t("Do (włącznie)")}>{(id) => <input id={id} name="date_to" type="date" required defaultValue={away?.date_to ?? from} />}</Field>
        </div>
        <Field label={t("Uwagi")} hint={t("Bez szczegółów zdrowotnych — wystarczy rodzaj.")}>
          {(id) => <input id={id} name="note" type="text" maxLength={200} defaultValue={away?.note ?? ""} />}
        </Field>
        <p className="hint">{t("Widać od razu, bez akceptacji. Na te dni nie da się zaplanować zmiany, dopóki zgłoszenie istnieje.")}</p>
        <div className="dialog-actions">
          {away && (confirming ? (
            <button type="button" className="btn danger" onClick={remove}>{t("Tak, usuń zgłoszenie")}</button>
          ) : (
            <button type="button" className="btn danger" onClick={() => setConfirming(true)}>{t("Usuń")}</button>
          ))}
          <button type="button" className="btn quiet" onClick={onClose}>{t("Anuluj")}</button>
          <button className="btn primary">{t("Zapisz")}</button>
        </div>
      </form>
    </Dialog>
  );
}

export function awayText(a: { date_from: string; date_to: string; kind: string }) {
  const label = AWAY_KINDS.find(([v]) => v === a.kind)?.[1] ?? a.kind;
  return `${label}: ${dateRange(a.date_from, a.date_to)}`;
}
