import { AnimatePresence, motion } from "motion/react";
import { createContext, useCallback, useContext, useEffect, useId, useRef, useState, type ReactNode } from "react";
import { lang, locale, setLanguage, t } from "../i18n.ts";

/** Native <dialog>: focus trap, Esc and backdrop for free. `side` renders it as a drawer. */
export function Dialog({ open, onClose, title, children, side = false, wide = false }: {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  side?: boolean;
  wide?: boolean;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);
  return (
    <dialog
      ref={ref}
      className={`${side ? "drawer" : "modal"}${wide ? " wide" : ""}`}
      onCancel={(e) => {
        e.preventDefault();
        onClose();
      }}
      onClick={(e) => e.target === ref.current && onClose()}
      aria-label={title}
    >
      <div className="dialog-inner">
        <header className="dialog-head">
          <h2>{title}</h2>
          <button type="button" className="icon-button" onClick={onClose} aria-label={t("Zamknij")}>
            ×
          </button>
        </header>
        {open && children}
      </div>
    </dialog>
  );
}

export function Field({ label, hint, children }: { label: string; hint?: string; children: (id: string) => ReactNode }) {
  const id = useId();
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      {children(id)}
      {hint && <p className="hint">{hint}</p>}
    </div>
  );
}

export function Segmented<T extends string>({ label, value, options, onChange }: {
  label: string;
  value: T;
  options: [T, string][];
  onChange: (v: T) => void;
}) {
  return (
    <fieldset className="segmented">
      <legend>{label}</legend>
      <div>
        {options.map(([v, text]) => (
          <label key={v} className={v === value ? "on" : undefined}>
            <input type="radio" checked={v === value} onChange={() => onChange(v)} />
            {text}
          </label>
        ))}
      </div>
    </fieldset>
  );
}

// --- toast: one readable message after each action ---

const ToastContext = createContext<(message: string) => void>(() => {});
export const useToast = () => useContext(ToastContext);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [message, setMessage] = useState<{ text: string; key: number } | null>(null);
  const show = useCallback((text: string) => setMessage({ text, key: Date.now() }), []);
  useEffect(() => {
    if (!message) return;
    const id = window.setTimeout(() => setMessage(null), 5000);
    return () => window.clearTimeout(id);
  }, [message]);
  return (
    <ToastContext.Provider value={show}>
      {children}
      <div className="toast-slot" role="status" aria-live="polite">
        <AnimatePresence>
          {message && (
            <motion.p
              key={message.key}
              className="toast"
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 8 }}
            >
              {message.text}
            </motion.p>
          )}
        </AnimatePresence>
      </div>
    </ToastContext.Provider>
  );
}

const dayMonth = new Intl.DateTimeFormat(locale, { day: "numeric", month: "long", timeZone: "UTC" });
const dayOnly = new Intl.DateTimeFormat(locale, { day: "numeric", timeZone: "UTC" });
const weekdayShort = new Intl.DateTimeFormat(locale, { weekday: "short", timeZone: "UTC" });
const utcNoon = (d: string) => new Date(`${d}T12:00:00Z`);

/** "9–11 października", "30 września – 2 października", "10 października" (en: "9–11 October"). */
export function dateRange(first: string, last: string): string {
  if (first === last) return dayMonth.format(utcNoon(first));
  if (first.slice(0, 7) === last.slice(0, 7) && lang === "pl") return `${dayOnly.format(utcNoon(first))}–${dayMonth.format(utcNoon(last))}`;
  return `${dayMonth.format(utcNoon(first))} – ${dayMonth.format(utcNoon(last))}`;
}

export function dayTab(date: string): { weekday: string; date: string } {
  const w = weekdayShort.format(utcNoon(date)).replace(".", "");
  return { weekday: w.charAt(0).toUpperCase() + w.slice(1), date: `${Number(date.slice(8))}${lang === "en" ? "/" : "."}${date.slice(5, 7)}` };
}

/** PL | EN — the current one is pressed; switching reloads (i18n.ts). */
export function LangSwitch({ className = "lang" }: { className?: string }) {
  return (
    <span className={className} role="group" aria-label="Język / Language">
      {(["pl", "en"] as const).map((l) => (
        <button key={l} type="button" className="link" aria-pressed={l === lang} onClick={() => l !== lang && setLanguage(l)}>
          {l.toUpperCase()}
        </button>
      ))}
    </span>
  );
}
