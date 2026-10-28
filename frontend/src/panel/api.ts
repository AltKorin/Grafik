// Panel ↔ Django API. Session cookie + CSRF header; errors carry the server's message in the chosen language
// (the django_language cookie from i18n.ts).
import { useEffect, useState } from "react";
import { t } from "../i18n.ts";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

let csrf = "";

async function call<T>(path: string, method = "GET", body?: unknown): Promise<T> {
  const response = await fetch(`/api${path}`, {
    method,
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", "X-CSRFToken": csrf },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new ApiError(response.status, data.error ?? data.detail ?? t("Błąd serwera ({status})", { status: response.status }));
  return data as T;
}

export const api = {
  get: <T,>(path: string) => call<T>(path),
  post: <T,>(path: string, body: unknown = {}) => call<T>(path, "POST", body),
  patch: <T,>(path: string, body: unknown) => call<T>(path, "PATCH", body),
  delete: <T,>(path: string, body: unknown) => call<T>(path, "DELETE", body),
};

type Session = { user: string | null; csrf: string };

export async function loadSession(): Promise<string | null> {
  const s = await call<Session>("/session/");
  csrf = s.csrf;
  return s.user;
}

export async function logIn(username: string, password: string): Promise<string | null> {
  const s = await call<Session>("/session/", "POST", { username, password });
  csrf = s.csrf; // Django rotates the token on login
  return s.user;
}

export async function logOut() {
  await call("/session/", "DELETE");
  await loadSession();
}

// --- shapes (mirror backend/grafik services) ---

export type Role = "admin" | "dyrektor" | "kierownik" | "pracownik";
export type Workplace = { id: string; name: string; timezone: string; role: Role; me: string | null; department: string | null };
export type Department = { id: string; name: string; color: string; people: number };
export type Employee = {
  id: string; name: string; role: Exclude<Role, "admin">; active: boolean; department: string | null;
  card: string | null; login: string | null; last_login: string | null; me: boolean; password?: string;
};
export type Shift = { id: string; employee: string; date: string; start: string; end: string; notes: string; minutes: number };
export type Away = { id: string; employee: string; date_from: string; date_to: string; kind: "urlop" | "l4" | "inne"; kind_label: string; note: string; conflicts?: Shift[] };
export type Week = {
  week: string; days: string[]; today: string;
  people: { id: string; name: string; department: string | null; editable: boolean }[];
  shifts: Shift[]; unavailability: Away[];
};
export type RequestKind = "swap" | "cancel" | "modify" | "add";
export type ChangeRequest = {
  id: string; kind: RequestKind; kind_label: string; status: "pending" | "approved" | "rejected" | "withdrawn"; status_label: string;
  employee: string; name: string; shift: (Shift & { name: string }) | null; swap_shift: (Shift & { name: string }) | null;
  new_date: string | null; new_start: string | null; new_end: string | null; reason: string; review_note: string;
  reviewed_by: string | null; created_at: string; mine: boolean; reviewable: boolean;
};
export type Status = { inside: boolean; since: string | null; last: { kind: string; local: string } | null };
export type Today = {
  date: string;
  me: (Status & { shifts: Shift[]; unavailability: { date_from: string; date_to: string; kind: string }[] }) | null;
  presence: (Status & { employee: string; name: string; department: string | null; today: string[] })[] | null;
};
export type WorkSession = { start: string | null; end: string | null; minutes: number; problem: string | null; ongoing: boolean };
export type ReportDay = { date: string; shifts: Shift[]; sessions: WorkSession[]; planned: number; worked: number };
export type ReportPerson = { employee: string; name: string; department: string | null; planned: number; worked: number; problems: number; days: ReportDay[] };
export type Report = { month: string; first: string; last: string; people: ReportPerson[] };
export type Punch = {
  id: number; employee: string; kind: "in" | "out" | "void"; kind_label: string; at: string; local: string;
  source: "tag" | "kiosk" | "manual"; source_label: string; point: string | null; note: string; voids: number | null;
  voided: boolean; recorded_by: string | null;
};
export type ClockPoint = { id: string; name: string; tag_path: string; kiosk: boolean; punches: number; kiosk_path?: string };
export type UnknownCard = { uid: string; at: string; point: string };
export type TapResult = { name: string; kind: "in" | "out"; kind_label: string; at: string; time: string; repeated: boolean };

/** Small loader hook: data, error, reload. */
export function useApi<T>(path: string | null) {
  const [state, setState] = useState<{ data: T | null; error: string | null }>({ data: null, error: null });
  const [tick, setTick] = useState(0);
  useEffect(() => {
    if (!path) return;
    let alive = true;
    api
      .get<T>(path)
      .then((data) => alive && setState({ data, error: null }))
      .catch((e: Error) => alive && setState({ data: null, error: e.message }));
    return () => {
      alive = false;
    };
  }, [path, tick]);
  return { ...state, reload: () => setTick((t) => t + 1), set: (data: T) => setState({ data, error: null }) };
}
