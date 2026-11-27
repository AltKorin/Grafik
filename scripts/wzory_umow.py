"""Wzory umów i aneksów dla pracowników → frontend/public/wzory/*.docx (do pobrania w panelu: Zespół i NFC).

Treść pochodzi ze skryptów projektu Malbork (~/Claude/Malbork/scripts: umowy_pracownicze.py, aneksy_odpowiedzialnosc.py),
pisanych dla jednej restauracji. Tu ta sama treść bez danych tej restauracji, z ramką „WZÓR — dostosuj do swojego obiektu”.
Zmiana treści = zmiana w Malborku, potem:  python3 scripts/wzory_umow.py  (potrzebne python-docx; tylko na maszynie z Malborkiem).
"""
import sys
import zipfile
from pathlib import Path

import docx
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor

sys.path.insert(0, str(Path.home() / "Claude/Malbork/scripts"))
import aneksy_odpowiedzialnosc as an  # noqa: E402
import umowa_impreza as ui  # noqa: E402
import umowy_pracownicze as up  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "frontend/public/wzory"
NAZWY = {
    "umowa-o-prace-sami-swoi.docx": "umowa-o-prace-wzor.docx",
    "umowa-zlecenia-sami-swoi.docx": "umowa-zlecenia-wzor.docx",
    "aneks-odpowiedzialnosc-materialna-umowa-o-prace-sami-swoi.docx": "aneks-odpowiedzialnosc-umowa-o-prace-wzor.docx",
    "aneks-odpowiedzialnosc-za-mienie-umowa-zlecenia-sami-swoi.docx": "aneks-odpowiedzialnosc-umowa-zlecenia-wzor.docx",
}
PODMIEN = [  # dane restauracji z Malborka → pola do uzupełnienia
    (f"Przystanek Wielbark – Restauracje Sami Swoi, {ui.LOKAL}", "[nazwa i adres lokalu]"),
    ("biuro@przystanekwielbark.pl", "[e-mail]"),
    ("w Malborku", "w [miejscowość]"),
]
ZAKAZANE = ("Sami Swoi", "Wielbark", "Malbork", "Zielińsk", "5862353087", "Zamkowa", "Głowackiego")
FIRMA = ("[nazwa firmy albo imię i nazwisko przedsiębiorcy], [adres siedziby], NIP [...], REGON [...][, KRS ...], "
         "reprezentowaną przez [imię i nazwisko – funkcja], zwaną dalej **{rola}**,")
RAMKA = ("**WZÓR — przed użyciem dostosuj do swojego obiektu.** Dokument przygotowano dla restauracji "
         "(stan prawny: listopad 2026). Uzupełnij lub usuń pola w [nawiasach], sprawdź stanowiska, stawki, czas pracy "
         "i zasady rozliczeń, a całość daj do sprawdzenia kadrom lub księgowej. Tę ramkę usuń przed podpisaniem.")


def neutralnie(s):
    for stare, nowe in PODMIEN:
        s = s.replace(stare, nowe)
    return s


_akapit, _punkt = ui.akapit, ui.punkt


def akapit(d, s="", *a, **k):
    return _akapit(d, neutralnie(s), *a, **k)


def punkt(d, nr, s):
    return _punkt(d, nr, neutralnie(s))


def ramka(p):
    pbdr = OxmlElement("w:pBdr")
    for bok in ("top", "left", "bottom", "right"):
        b = OxmlElement(f"w:{bok}")
        for k, v in (("val", "single"), ("sz", "12"), ("space", "4"), ("color", "C95A1E")):
            b.set(qn(f"w:{k}"), v)
        pbdr.append(b)
    shd = OxmlElement("w:shd")
    for k, v in (("val", "clear"), ("color", "auto"), ("fill", "FBEFE6")):
        shd.set(qn(f"w:{k}"), v)
    ppr = p._p.get_or_add_pPr()
    ppr.append(pbdr)
    ppr.append(shd)


def szkielet(etykieta):
    """Style z szablonu Malborka (tytuły, tabela), bez logo i stopki restauracji; „WZÓR” w nagłówku i ramce na górze."""
    d = docx.Document(ui.SZABLON)
    body = d.element.body
    for el in list(body):
        if el.tag != qn("w:sectPr"):
            body.remove(el)
    d.styles["Normal"].font.size = Pt(10.5)
    h2 = d.styles["Heading 2"].font
    h2.name, h2.size, h2.color.rgb = "Bookman Old Style", Pt(11.5), RGBColor.from_string(ui.BRAZ)
    s = d.sections[0]
    s.top_margin, s.bottom_margin = Pt(72), Pt(72)
    s.different_first_page_header_footer = False
    for hf in (s.header, s.footer, s.first_page_header, s.first_page_footer):
        for p in hf.paragraphs:
            p._p.getparent().remove(p._p)
        for t in hf.tables:
            t._tbl.getparent().remove(t._tbl)
        for rid in list(hf.part.rels):  # logo i linki restauracji zostałyby w paczce bez odwołań
            hf.part.drop_rel(rid)
    hp = s.header.add_paragraph()
    hp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    r = hp.add_run(f"WZÓR do dostosowania · {etykieta}")
    r.font.size, r.font.color.rgb = Pt(8.5), RGBColor.from_string("C95A1E")
    fp = s.footer.add_paragraph()
    fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for txt, fld in ((f"{etykieta} – strona ", "PAGE"), (" z ", "NUMPAGES")):
        r = fp.add_run(txt); r.font.size = Pt(8.5)
        r = fp.add_run(); r.font.size = Pt(8.5); ui.pole(r, fld)
    p = _akapit(d, RAMKA, after=12, size=9.5)
    ramka(p)
    return d


def zapisz(d, out):
    out = OUT / NAZWY[out.name]
    tekst = "\n".join(p.text for p in d.paragraphs) + "\n".join(
        c.text for t in d.tables for row in t.rows for c in row.cells)
    zostalo = [z for z in ZAKAZANE if z in tekst]
    assert not zostalo, f"{out.name}: zostały dane restauracji {zostalo}"
    assert "WZÓR" in tekst, out.name
    d.core_properties.title = f"WZÓR – {out.stem}"
    out.parent.mkdir(parents=True, exist_ok=True)
    d.save(out)
    with zipfile.ZipFile(out) as z:  # cała paczka: nagłówki, stopki, relacje, media
        caly = b"".join(z.read(n) for n in z.namelist()).decode("utf-8", "ignore").lower()
    zostalo = [z for z in ZAKAZANE + ("przystanek",) if z.lower() in caly]
    assert not zostalo and "media/" not in caly, f"{out.name}: w paczce zostało {zostalo or 'logo'}"
    print(out)


# ponytail: podmiana funkcji w modułach Malborka zamiast kopii treści; gdy Malbork zmieni nazwy funkcji, assert w zapisz() albo ImportError to pokaże
ui.punkt = punkt  # paragrafy() woła punkt z umowa_impreza
for m in (up, an):
    m.akapit, m.szkielet, m.zapisz, m.SPOLKA = akapit, szkielet, zapisz, FIRMA
up.punkt = punkt

if __name__ == "__main__":
    up.umowa_o_prace()
    up.umowa_zlecenia()
    for k in an.WARIANTY:
        an.aneks(k)
