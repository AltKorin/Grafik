// E2E on the seeded demo (backend: `manage.py seed_demo --reset > ../.seed-links.txt`).
// Usage: CHROME=<chromium> BASE=http://127.0.0.1:5180 npm run e2e   — screenshots in e2e/shots/.
// Changes demo data (a shift, a person, punches, a request) → reseed afterwards.
import { readFileSync, mkdirSync } from "node:fs";
import { chromium } from "playwright-core";

const BASE = process.env.BASE ?? "http://127.0.0.1:5180";
const PASSWORD = process.env.DEMO_PASSWORD ?? "demo-haslo-do-testow";
const links = readFileSync(new URL("../../.seed-links.txt", import.meta.url), "utf8");
const tag = links.match(/Naklejka NFC: (\S+)/)[1];
const kiosk = links.match(/Kiosk:\s+(\S+)/)[1];
mkdirSync(new URL("./shots/", import.meta.url), { recursive: true });
const shot = (page, name) => page.screenshot({ path: new URL(`./shots/${name}.png`, import.meta.url).pathname, fullPage: true });

let failures = 0;
async function step(name, fn) {
  try {
    await fn();
    console.log(`OK    ${name}`);
  } catch (error) {
    failures++;
    console.log(`BŁĄD  ${name}: ${error.message.split("\n")[0]}`);
  }
}
const expectText = async (page, text, timeout = 5000) => page.getByText(text, { exact: false }).first().waitFor({ timeout });

async function login(page, user) {
  await page.getByLabel("Login lub e-mail").fill(user);
  await page.getByLabel("Hasło").fill(PASSWORD);
  await page.getByRole("button", { name: "Zaloguj się" }).click();
}

// The flow drives the Polish UI; the language follows the browser (i18n.ts), so every page is pl-PL.
const PL = { locale: "pl-PL" };
const browser = await chromium.launch({ executablePath: process.env.CHROME, headless: true });
const desk = await browser.newPage({ ...PL, viewport: { width: 1360, height: 900 } });
const errors = [];
desk.on("pageerror", (e) => errors.push(e.message));

await step("landing i rejestracja się otwierają", async () => {
  await desk.goto(BASE);
  await expectText(desk, "Grafik pracy i czas pracy przez NFC");
  await shot(desk, "01-landing");
  await desk.goto(`${BASE}/rejestracja`);
  await desk.getByLabel("Nazwa firmy").waitFor();
});

await step("dyrektor: pulpit Dziś z obecnością", async () => {
  await desk.goto(`${BASE}/panel`);
  await login(desk, "dyrektor-demo");
  await expectText(desk, "W pracy teraz");
  await shot(desk, "02-dzis-dyrektor");
});

await step("grafik: dodanie zmiany przez + i widoczny urlop", async () => {
  await desk.getByRole("link", { name: "Grafik" }).click();
  await expectText(desk, "Anna Nowak");
  await desk.getByRole("button", { name: "Następny tydzień" }).click(); // next week: Tomek's holiday
  await expectText(desk, "Urlop");
  const add = desk.getByRole("button", { name: /Dodaj zmianę: Dorota Dyrektor/ }).first();
  await add.click();
  const dialog = desk.getByRole("dialog");
  await dialog.getByLabel("Od", { exact: true }).fill("07:30");
  await dialog.getByLabel("Do", { exact: true }).fill("15:30");
  await dialog.getByLabel("Uwagi").fill("E2E");
  await dialog.getByRole("button", { name: "Dodaj zmianę" }).click();
  await desk.locator("table.week .chip", { hasText: "07:30–15:30" }).waitFor({ timeout: 5000 }); // in the grid, not the toast
  await shot(desk, "03-grafik");
});

await step("grafik: zmiana na dzień urlopu jest zablokowana", async () => {
  const row = desk.getByRole("row", { name: /Tomasz/ });
  const away = row.getByRole("button", { name: "Urlop" }).first();
  await away.waitFor();
  const cellAdd = row.getByRole("button", { name: /Dodaj zmianę/ });
  // the first "+" in a cell that shows Urlop
  const count = await cellAdd.count();
  for (let i = 0; i < count; i++) {
    const cell = cellAdd.nth(i).locator("..");
    if (await cell.getByText("Urlop").count()) {
      await cellAdd.nth(i).click();
      break;
    }
  }
  await desk.getByRole("dialog").getByRole("button", { name: "Dodaj zmianę" }).click();
  await expectText(desk, "poproś o wycofanie zgłoszenia");
  await desk.getByRole("dialog").getByRole("button", { name: "Anuluj" }).click();
});

let newPassword = "";
await step("zespół: nowy pracownik z loginem, hasło pokazane raz", async () => {
  await desk.getByRole("link", { name: "Zespół i NFC" }).click();
  await desk.getByRole("button", { name: "Dodaj pracownika" }).click();
  await desk.getByLabel("Imię i nazwisko").fill("Ewa E2E");
  await desk.getByText("Nadam login i hasło").click(); // segmented: the radio itself is hidden
  await desk.getByLabel("Login", { exact: true }).fill(`ewa.e2e${Date.now() % 100000}`);
  await desk.getByRole("button", { name: "Dodaj", exact: true }).click();
  await expectText(desk, "przekaż je teraz");
  newPassword = await desk.locator(".notice.secret strong").nth(2).innerText();
  if (newPassword.length < 12) throw new Error(`hasło: ${newPassword}`);
  await shot(desk, "04-zespol");
});

const phone = await browser.newContext({ ...PL, viewport: { width: 390, height: 800 }, isMobile: true });
const tapPage = await phone.newPage();
await step("telefon przy naklejce: logowanie, potem odbicie", async () => {
  await tapPage.goto(`${BASE}${tag}`);
  await expectText(tapPage, "zaloguj się raz na tym telefonie");
  await login(tapPage, "anna");
  await tapPage.waitForURL("**/panel", { timeout: 5000 }); // replaced after the punch: a restored tab must not punch again
  await tapPage.getByRole("heading", { name: /^(Wejście|Wyjście) \d\d:\d\d$/ }).waitFor();
  await shot(tapPage, "05-telefon-odbicie");
});

await step("telefon: drugie przyłożenie w ciągu minuty nie liczy się drugi raz", async () => {
  await tapPage.goto(`${BASE}${tag}`);
  await expectText(tapPage, "nie liczymy go drugi raz");
});

const tablet = await browser.newPage({ ...PL, viewport: { width: 1180, height: 820 } });
await step("kiosk: karta z separatorami odbija, nieznana karta nie", async () => {
  await tablet.goto(`${BASE}${kiosk}`);
  await expectText(tablet, "Przyłóż kartę");
  await tablet.keyboard.type("04:77:aa:11");
  await tablet.keyboard.press("Enter");
  await expectText(tablet, "Aleksandra Lewandowska");
  await shot(tablet, "06-kiosk-ok");
  await tablet.waitForTimeout(4200);
  await tablet.keyboard.type("CAFEBABE");
  await tablet.keyboard.press("Enter");
  await expectText(tablet, "Nieznana karta");
  await shot(tablet, "07-kiosk-nieznana");
});

await step("zespół: nieznana karta z kiosku do przypisania", async () => {
  await desk.reload();
  const row = desk.locator(".settings-list li", { hasText: "Ewa E2E" });
  await row.getByRole("button", { name: "Zmień" }).click();
  await expectText(desk, "…BABE");
  await desk.getByRole("button", { name: "Przypisz" }).first().click();
  await expectText(desk, "Karta przypisana");
  await desk.keyboard.press("Escape");
});

await step("wniosek pracownika i akceptacja kierownika zmienia grafik", async () => {
  const anna = await phone.newPage();
  await anna.goto(`${BASE}/panel/wnioski`);
  await anna.getByRole("button", { name: "Nowy wniosek" }).click();
  await anna.getByText("Odwołanie", { exact: true }).click();
  const select = anna.getByLabel("Moja zmiana");
  await select.locator("option").nth(1).waitFor({ state: "attached" });
  const options = await select.locator("option").allInnerTexts();
  if (options.length < 2) throw new Error("brak zmian do wyboru");
  await select.selectOption({ index: options.length - 1 });
  await anna.getByLabel("Powód").fill("E2E: wizyta u lekarza");
  await anna.getByRole("button", { name: "Wyślij wniosek" }).click();
  await expectText(anna, "Wniosek wysłany");
  const boss = await browser.newPage(PL);
  await boss.goto(`${BASE}/panel`);
  await login(boss, "kuchnia-kier");
  await expectText(boss, "Wnioski do rozpatrzenia");
  await boss.getByRole("link", { name: "Wnioski" }).click();
  await boss.getByRole("button", { name: "Przyjmij" }).first().click();
  await boss.getByRole("dialog").getByRole("button", { name: "Przyjmij" }).click();
  await expectText(boss, "grafik już zmieniony");
  await shot(boss, "08-wnioski");
});

await step("czas pracy: zestawienie, szczegóły osoby, CSV", async () => {
  await desk.getByRole("link", { name: "Czas pracy" }).click();
  await expectText(desk, "Przepracowane");
  await desk.getByRole("row", { name: /Anna Nowak/ }).click();
  await expectText(desk, "Karta w kiosku"); // the raw punches, not only the heading
  await shot(desk, "09-czas-pracy");
  const href = await desk.getByRole("link", { name: "Pobierz CSV" }).getAttribute("href");
  const csv = await desk.evaluate(async (u) => (await fetch(u)).text(), href);
  if (!csv.includes("Pracownik;Dział;Plan")) throw new Error("CSV bez nagłówka");
});

await step("kierownik: nowy pracownik z zaproszeniem, pracownik sam zakłada konto (raz)", async () => {
  const mgr = await browser.newPage(PL);
  await mgr.goto(`${BASE}/panel`);
  await login(mgr, "kuchnia-kier");
  await mgr.getByRole("link", { name: "Zespół", exact: true }).click();
  await expectText(mgr, "Pracownicy twojego działu");
  if (await mgr.getByText("Punkty odbić (NFC)").count()) throw new Error("kierownik widzi punkty NFC");
  await mgr.getByRole("button", { name: "Dodaj pracownika" }).click();
  await mgr.getByLabel("Imię i nazwisko").fill("Zenon Zaproszony");
  await mgr.getByRole("button", { name: "Dodaj", exact: true }).click(); // default: an invitation link
  await expectText(mgr, "Zaproszenie:");
  const link = await mgr.locator(".notice.secret code").innerText();
  await shot(mgr, "11a-zaproszenie");
  const invitee = await phone.newPage();
  await invitee.goto(link);
  await expectText(invitee, "Witaj, Zenon Zaproszony");
  await invitee.getByLabel("Login", { exact: true }).fill(`zenon${Date.now() % 100000}`);
  await invitee.getByLabel("Hasło", { exact: true }).fill(PASSWORD);
  await invitee.getByLabel("Powtórz hasło").fill(PASSWORD);
  await shot(invitee, "11b-zaproszenie-telefon");
  await invitee.getByRole("button", { name: "Załóż konto" }).click();
  await invitee.waitForURL("**/panel");
  await invitee.getByRole("heading", { name: "Dziś" }).waitFor();
  await invitee.goto(link);
  await expectText(invitee, "Zaproszenie nie działa");
  await mgr.reload();
  await expectText(mgr, "Zenon Zaproszony");
});

await step("demo bez rejestracji: własna kopia, zmiana roli, kiosk", async () => {
  const visitor = await browser.newPage(PL);
  await visitor.goto(BASE);
  await visitor.getByRole("button", { name: "Wypróbuj demo — bez rejestracji" }).first().click();
  await visitor.waitForURL("**/panel");
  await expectText(visitor, "Twoja własna kopia firmy przykładowej");
  await visitor.getByRole("link", { name: "Zespół i NFC" }).waitFor();
  await shot(visitor, "11c-demo-dyrektor");
  await visitor.getByRole("button", { name: "Pracownik", exact: true }).click();
  await expectText(visitor, "Odbij się telefonem");
  if (await visitor.getByRole("link", { name: "Zespół i NFC" }).count()) throw new Error("pracownik widzi Zespół");
  const [kioskTab] = await Promise.all([visitor.waitForEvent("popup"), visitor.getByRole("link", { name: /Kiosk \(tablet\)/ }).click()]);
  await expectText(kioskTab, "Przyłóż kartę");
  await kioskTab.keyboard.type("04A1B2C3");
  await kioskTab.keyboard.press("Enter");
  await expectText(kioskTab, "Anna Nowak");
});

// English: an en-GB browser gets English everywhere. Polish letters left on a page = a text missed by t().
// Allowed: people and places from the demo data and the company's legal address in the footer and terms.
const POLISH_DATA = ["Tomasz Wiśniewski", "Piotr Zieliński", "Wejście dla personelu", "Kościerzyna-Wybudowanie", "Gdańsk-Północ", "Gdańsku", "Gdańsk"];
async function noPolish(page, where) {
  await page.waitForLoadState("networkidle");
  let text = await page.locator("body").innerText();
  for (const d of POLISH_DATA) text = text.replaceAll(d, "");
  const left = [...new Set(text.match(/\S*[ąćęłńóśźżĄĆĘŁŃÓŚŹŻ]\S*/g) ?? [])];
  if (left.length) throw new Error(`${where}: ${left.slice(0, 8).join(", ")}`);
}

await step("wersja angielska: strona, panel, CSV, API, kiosk i naklejka bez polskich tekstów", async () => {
  const en = await browser.newContext({ locale: "en-GB", viewport: { width: 1360, height: 900 } });
  const page = await en.newPage();
  page.on("pageerror", (e) => errors.push(e.message));
  for (const path of ["/", "/rejestracja", "/regulamin"]) {
    await page.goto(`${BASE}${path}`);
    await noPolish(page, path);
  }
  await expectText(page, "Polish version is binding");
  await page.goto(`${BASE}/panel`);
  await page.getByLabel("Login or e-mail").fill("dyrektor-demo");
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Log in" }).click();
  for (const name of ["Today", "Schedule", "Requests", "Working time", "Team & NFC"]) {
    // client-side route: wait for its data, or the scan would only see an empty page
    await Promise.all([page.waitForResponse((r) => r.url().includes("/api/w/")), page.getByRole("link", { name, exact: true }).click()]);
    await page.locator(".settings-list li, .report tbody tr, .week tbody tr, .group-list li, .card").first().waitFor();
    await noPolish(page, name);
  }
  await shot(page, "12-en-zespol");
  await page.getByRole("link", { name: "Working time", exact: true }).click();
  await page.getByRole("row", { name: /Anna Nowak/ }).click();
  await expectText(page, "Card at the kiosk"); // punch sources and kinds come translated from the API
  await noPolish(page, "Working time → person");
  await page.keyboard.press("Escape");
  const href = await page.getByRole("link", { name: "Download CSV" }).getAttribute("href");
  const csv = await page.evaluate(async (u) => (await fetch(u)).text(), href);
  if (!csv.includes("Employee;Department;Plan")) throw new Error(`CSV not in English: ${csv.slice(0, 60)}`);
  const answer = await page.evaluate(async () => (await fetch("/api/w/00000000-0000-0000-0000-000000000000/week/")).json());
  if (answer.error !== "Company: not found") throw new Error(`API not in English: ${JSON.stringify(answer)}`);
  await page.goto(`${BASE}${kiosk}`);
  await noPolish(page, "kiosk");
  await shot(page, "13-en-kiosk");
  await page.goto(`${BASE}${tag}`);
  await noPolish(page, "naklejka");
  await page.goto(`${BASE}/panel`);
  await page.getByRole("button", { name: "PL" }).click();
  await expectText(page, "Zespół i NFC");
  await en.close();
});

await step("brak błędów JS na stronach", async () => {
  if (errors.length) throw new Error(errors.join(" | "));
});

await browser.close();
console.log(failures ? `\nBłędów: ${failures}` : "\nWszystko OK.");
process.exit(failures ? 1 : 0);
