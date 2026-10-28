// Landing: the product shown with a fictional week (the real grid styles) and the two ways of punching.
import { t } from "../i18n.ts";
import { DemoButton } from "../panel/Demo.tsx";

const DAYS = [t("pon"), t("wt"), t("śr"), t("czw"), t("pt")];
const PEOPLE: { name: string; color: string; cells: (string | null)[] }[] = [
  { name: `Anna (${t("kuchnia")})`, color: "#c95a1e", cells: ["6:00–14:00", "6:00–14:00", null, "14:00–22:00", "14:00–22:00"] },
  { name: `Tomek (${t("kuchnia")})`, color: "#c95a1e", cells: ["14:00–22:00", t("urlop"), t("urlop"), "6:00–14:00", null] },
  { name: `Ola (${t("sala")})`, color: "#1e5f9b", cells: [null, "10:00–18:00", "10:00–18:00", "10:00–18:00", "16:00–24:00"] },
  { name: `Piotr (${t("sala")})`, color: "#1e5f9b", cells: ["16:00–24:00", "16:00–24:00", t("L4"), null, "10:00–18:00"] },
];

export default function Landing() {
  const deleted = new URLSearchParams(window.location.search).has("usunieto");
  return (
    <main>
      {deleted && <p className="site-notice" role="status">{t("Firma i jej dane zostały usunięte. Dziękujemy, że korzystaliście z Grafiku.")}</p>}
      <section className="hero">
        <div className="hero-text">
          <p className="kicker">{t("Dla restauracji, hoteli, sklepów i małych firm usługowych")}</p>
          <h1>{t("Grafik pracy i czas pracy przez NFC — za darmo, w przeglądarce")}</h1>
          <p className="lead">
            {t("Układasz zmiany na tydzień, zespół widzi je w telefonie. Urlop i L4 zgłasza się samemu, zamianę — wnioskiem do kierownika.")}{" "}
            {t("Wejście i wyjście: telefonem przy naklejce NFC albo kartą w kiosku. Na koniec miesiąca plan kontra odbicia, w CSV dla księgowej.")}
          </p>
          <p className="hero-actions">
            <a className="btn primary big" href="/rejestracja">{t("Załóż konto za darmo")}</a>
            <DemoButton />
            <a className="btn big" href="#jak-to-dziala">{t("Jak to działa")}</a>
          </p>
        </div>
      </section>

      <section className="demo" aria-label={t("Przykładowy grafik")}>
        <div className="demo-stage">
          <figure className="sheet-demo">
            <div className="grid-wrap">
              <table className="week" style={{ minWidth: 640 }}>
                <thead>
                  <tr>
                    <th>{t("Osoba")}</th>
                    {DAYS.map((d) => <th key={d}>{d}</th>)}
                  </tr>
                </thead>
                <tbody>
                  {PEOPLE.map((p) => (
                    <tr key={p.name}>
                      <td><div className="person"><span className="swatch" style={{ background: p.color }} />{p.name}</div></td>
                      {p.cells.map((c, i) => (
                        <td key={i}>
                          <div className="cell">
                            {c && <span className={`chip${/^\d/.test(c) ? "" : " away"}`} style={{ ["--dept" as string]: p.color }}>{c}</span>}
                          </div>
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <figcaption>{t("Grafik działu — każdy widzi swój zespół, kierownik klika dzień i dodaje zmianę")}</figcaption>
          </figure>
          <figure className="phone">
            <div className="phone-screen tap-demo">
              <span className="tap-mark">→</span>
              <strong>{t("Wejście")} 7:58</strong>
              <span>Anna · {t("Wejście dla personelu")}</span>
            </div>
            <figcaption>{t("Telefon przyłożony do naklejki NFC przy wejściu")}</figcaption>
          </figure>
        </div>
      </section>

      <section id="jak-to-dziala" className="steps">
        <h2>{t("Jak to działa")}</h2>
        <ol>
          <li>
            <h3>{t("Dodajesz zespół")}</h3>
            <p>{t("Działy, osoby, loginy. Kierownik działu układa grafik swojego zespołu, dyrektor widzi wszystko.")}</p>
          </li>
          <li>
            <h3>{t("Układasz tydzień")}</h3>
            <p>{t("Klik w dzień — zmiana. „Skopiuj poprzedni tydzień” robi resztę. Urlopu i L4 nie da się przeoczyć: zmiany na ten dzień nie zapiszesz.")}</p>
          </li>
          <li>
            <h3>{t("Zespół się odbija")}</h3>
            <p>{t("Naklejka NFC za kilka złotych przy wejściu — telefon pracownika wystarczy. Albo tablet z czytnikiem i breloki dla osób bez smartfona.")}</p>
          </li>
        </ol>
      </section>

      <section className="faq">
        <h2>{t("Pytania")}</h2>
        <dl>
          <dt>{t("Ile to kosztuje?")}</dt>
          <dd>{t("Nic. Grafik jest darmowy, nie prosimy o kartę.")}</dd>
          <dt>{t("Czego potrzebuję do NFC?")}</dt>
          <dd>
            {t("Najtaniej: naklejki NFC (NTAG213) przy wejściu — link zapiszesz na niej z panelu (Android, Chrome) albo darmową aplikacją NFC Tools. Pracownik przykłada telefon, na którym jest zalogowany.")}{" "}
            {t("Dla osób bez smartfona: tablet przy wejściu, czytnik kart USB (działa jak klawiatura) i karty lub breloki.")}
          </dd>
          <dt>{t("Czy ktoś może się odbić z domu?")}</dt>
          <dd>{t("Odbicie wymaga zalogowanego konta i linku z naklejki. Gdy podejrzewasz, że link wyciekł, jednym przyciskiem wymieniasz go na nowy — stara naklejka przestaje działać. Każde odbicie ma źródło (telefon / kiosk / korekta).")}</dd>
          <dt>{t("A gdy ktoś zapomni karty?")}</dt>
          <dd>{t("Kierownik dopisuje odbicie z powodem. Pomyłkę anuluje — też z powodem. Pierwotne odbicie zostaje widoczne, nic nie znika po cichu.")}</dd>
          <dt>{t("Czy to zastępuje ewidencję czasu pracy?")}</dt>
          <dd>{t("To pomoc: plan i odbicia w jednym zestawieniu, z eksportem CSV. Za ewidencję zgodną z Kodeksem pracy i jej przechowywanie odpowiada pracodawca.")}</dd>
          <dt>{t("Co z danymi pracowników?")}</dt>
          <dd>{t("Należą do firmy. Pobierzesz je w każdej chwili, a firmę usuniesz jednym przyciskiem. Przetwarzamy je w imieniu firmy (umowa powierzenia jest w regulaminie).")}</dd>
        </dl>
        <p className="hero-actions">
          <a className="btn primary big" href="/rejestracja">{t("Załóż konto za darmo")}</a>
          <DemoButton />
        </p>
      </section>
    </main>
  );
}
