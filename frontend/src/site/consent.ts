// GA4 with Consent Mode v2, public pages only (landing, rejestracja, regulamin) — same contract as
// fc.sudomie.pl: everything denied until "Akceptuję", choice in localStorage "cc". No id = no tag.
declare global {
  interface Window {
    dataLayer: unknown[];
    gtag: (...args: unknown[]) => void;
  }
}

export type Choice = "accepted" | "declined" | null;

export function readChoice(): Choice {
  try {
    const v = localStorage.getItem("cc");
    return v === "accepted" || v === "declined" ? v : null;
  } catch {
    return null;
  }
}

let started: Promise<string> | null = null;

/** Resolves to the measurement id ("" when analytics is off for this deployment). */
export function startAnalytics(): Promise<string> {
  started ??= fetch("/api/public-config/")
    .then((r) => r.json())
    .then(({ ga_measurement_id: id }: { ga_measurement_id: string }) => {
      if (!id) return "";
      window.dataLayer = window.dataLayer || [];
      window.gtag = function () {
        // gtag.js reads the Arguments object itself, not an array copy
        // eslint-disable-next-line prefer-rest-params
        window.dataLayer.push(arguments);
      };
      window.gtag("consent", "default", { analytics_storage: "denied", ad_storage: "denied", ad_user_data: "denied", ad_personalization: "denied" });
      if (readChoice() === "accepted") window.gtag("consent", "update", { analytics_storage: "granted" });
      window.gtag("js", new Date());
      window.gtag("config", id);
      const script = document.createElement("script");
      script.async = true;
      script.src = `https://www.googletagmanager.com/gtag/js?id=${encodeURIComponent(id)}`;
      document.head.append(script);
      return id;
    })
    .catch(() => "");
  return started;
}

export function choose(choice: Exclude<Choice, null>) {
  try {
    localStorage.setItem("cc", choice);
  } catch {
    /* private mode: the banner simply comes back next time */
  }
  window.gtag?.("consent", "update", { analytics_storage: choice === "accepted" ? "granted" : "denied" });
  if (choice === "declined") {
    // Withdrawal as easy as consent (art. 7 ust. 3 RODO): drop the cookies GA already set.
    const parent = location.hostname.split(".").slice(-2).join(".");
    for (const name of document.cookie.split("; ").map((c) => c.split("=")[0]).filter((n) => n.startsWith("_ga"))) {
      for (const domain of ["", `; domain=.${parent}`]) document.cookie = `${name}=; Max-Age=0; path=/${domain}`;
    }
  }
}
