// Pure date/time helpers for the panel; ISO dates (RRRR-MM-DD) as plain strings, UTC noon to dodge DST.
const noon = (d: string) => new Date(`${d}T12:00:00Z`);

export function addDays(day: string, n: number): string {
  const d = noon(day);
  d.setUTCDate(d.getUTCDate() + n);
  return d.toISOString().slice(0, 10);
}

/** Same rule as the backend: end ≤ start means the shift ends the next day. */
export function shiftMinutes(start: string, end: string): number {
  const m = (t: string) => Number(t.slice(0, 2)) * 60 + Number(t.slice(3, 5));
  return (((m(end) - m(start)) % 1440) + 1440) % 1440;
}

/** 485 → "8:05" */
export function hours(minutes: number): string {
  return `${Math.floor(minutes / 60)}:${String(minutes % 60).padStart(2, "0")}`;
}

const weekday = new Intl.DateTimeFormat("pl-PL", { weekday: "short", timeZone: "UTC" });
const monthYear = new Intl.DateTimeFormat("pl-PL", { month: "long", year: "numeric", timeZone: "UTC" });

/** "2026-11-03" → "wt 3.11" */
export function dayLabel(day: string): string {
  return `${weekday.format(noon(day)).replace(".", "")} ${Number(day.slice(8))}.${day.slice(5, 7)}`;
}

/** "2026-11" → "listopad 2026" */
export function monthLabel(month: string): string {
  return monthYear.format(noon(`${month}-01`));
}

export function addMonths(month: string, n: number): string {
  const [y, m] = month.split("-").map(Number);
  const total = y * 12 + (m - 1) + n;
  return `${Math.floor(total / 12)}-${String((total % 12) + 1).padStart(2, "0")}`;
}

export function inRange(day: string, from: string, to: string): boolean {
  return from <= day && day <= to;
}
