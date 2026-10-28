// PL/EN like Narrative Framework: the Polish text is the key, English lives in en.ts.
// The choice is per browser (localStorage) and mirrored to the `django_language` cookie, so API errors,
// labels, the CSV and the terms come back in the same language. No browser (node checks) → Polish.
import { EN } from "./en.ts";

export type Language = "pl" | "en";
const KEY = "lang";
const browser = typeof window !== "undefined";

function initial(): Language {
  if (!browser) return "pl";
  try {
    const saved = localStorage.getItem(KEY);
    if (saved === "pl" || saved === "en") return saved;
  } catch {
    /* private mode: fall back to the browser language */
  }
  return navigator.language.toLowerCase().startsWith("pl") ? "pl" : "en";
}

export const lang: Language = initial();
export const locale = lang === "en" ? "en-GB" : "pl-PL";

function remember(l: Language) {
  document.cookie = `django_language=${l}; path=/; max-age=31536000; samesite=lax`;
}

if (browser) {
  document.documentElement.lang = lang;
  remember(lang);
}

/** Switching reloads the page: every module reads `lang` once, no context to thread through the tree. */
export function setLanguage(l: Language) {
  try {
    localStorage.setItem(KEY, l);
  } catch {
    /* the cookie still carries it for this session */
  }
  remember(l);
  window.location.reload();
}

/** t('Dodaj') → 'Add'; t('{n} osób', { n: 3 }) fills {params} after translating. */
export function t(text: string, params?: Record<string, string | number>): string {
  let out = text;
  if (lang === "en") out = EN[text] ?? text; // i18n.check.ts guarantees the entry exists
  return params ? out.replace(/\{(\w+)\}/g, (m, k: string) => (k in params ? String(params[k]) : m)) : out;
}

