"""
Programmatic Word document builder for resumes and cover letters.

Formatting spec:
  - Font: Arial throughout (default / CLASSIC theme)
  - Body text: 10pt
  - Section headings: 12pt, Bold, ALL CAPS
  - Name header: 14pt, Bold, Centered
  - Contact line: 10pt, Centered
  - Company/location line: 10pt, Bold — company LEFT, dates RIGHT-TABBED
  - Role: 10pt, Italic
  - Bullets: 10pt, 0.25" hanging indent
  - Education & Certs: borderless 2-column table (left=education, right=certs);
    single-column if no certs returned
"""

import os
import re
from datetime import date
from typing import TYPE_CHECKING

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor, Twips

from src.models import CoverLetterJSON, ResumeJSON
from src.themes import ThemeConfig, CLASSIC

if TYPE_CHECKING:
    from docx.document import Document as DocxDocument


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

RIGHT_TAB_POS = Twips(9360)  # 6.5" at 1" margins on US Letter


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------


def _set_font(run, size_pt: int, bold: bool = False, italic: bool = False,
              color: RGBColor | None = None, font_name: str = "Arial"):
    run.font.name = font_name
    run.font.size = Pt(size_pt)
    run.font.bold = bold
    run.font.italic = italic
    if color:
        run.font.color.rgb = color


def _add_right_tab(paragraph, pos_twips: int | None = None):
    """Add a right-aligned tab stop at the right margin."""
    pPr = paragraph._p.get_or_add_pPr()
    tabs = OxmlElement("w:tabs")
    tab = OxmlElement("w:tab")
    tab.set(qn("w:val"), "right")
    tab.set(qn("w:pos"), str(pos_twips or RIGHT_TAB_POS))
    tabs.append(tab)
    pPr.append(tabs)


def _set_space(paragraph, before_pt: float = 0, after_pt: float = 0,
               line_rule: str | None = None, line_val: int | None = None):
    pPr = paragraph._p.get_or_add_pPr()
    spacing = OxmlElement("w:spacing")
    spacing.set(qn("w:before"), str(int(before_pt * 20)))
    spacing.set(qn("w:after"), str(int(after_pt * 20)))
    if line_rule and line_val:
        spacing.set(qn("w:line"), str(line_val))
        spacing.set(qn("w:lineRule"), line_rule)
    pPr.append(spacing)


def _no_border_cell(cell):
    """Remove all borders from a table cell."""
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    tcBorders = OxmlElement("w:tcBorders")
    for side in ("top", "left", "bottom", "right", "insideH", "insideV"):
        el = OxmlElement(f"w:{side}")
        el.set(qn("w:val"), "none")
        tcBorders.append(el)
    tcPr.append(tcBorders)


def _shade_cell(cell, hex_color: str):
    """Set cell background fill color via XML."""
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_color)
    tcPr.append(shd)


def _cell_bullet(cell, text: str):
    """Add a bullet-style paragraph inside a table cell."""
    p = cell.add_paragraph()
    _set_space(p, before_pt=1, after_pt=1)
    # Hanging indent to mimic bullet style
    pPr = p._p.get_or_add_pPr()
    ind = OxmlElement("w:ind")
    ind.set(qn("w:left"), "360")   # 0.25"
    ind.set(qn("w:hanging"), "360")
    pPr.append(ind)
    # Bullet character + text
    bullet_run = p.add_run("\u2022\t")
    _set_font(bullet_run, 10)
    text_run = p.add_run(text)
    _set_font(text_run, 10)
    return p


def _section_heading(doc: "DocxDocument", text: str, theme: "ThemeConfig"):
    p = doc.add_paragraph()
    p.alignment = (
        WD_ALIGN_PARAGRAPH.LEFT if theme.name_align == "left"
        else WD_ALIGN_PARAGRAPH.CENTER
    )
    _set_space(p, before_pt=8, after_pt=2)
    run = p.add_run(text.upper())
    _set_font(run, theme.heading_pt, bold=True, color=RGBColor(*theme.accent_color),
              font_name=theme.font)
    pPr = p._p.get_or_add_pPr()
    if theme.heading_rule:
        pBdr = OxmlElement("w:pBdr")
        top = OxmlElement("w:top")
        top.set(qn("w:val"), "single")
        top.set(qn("w:sz"), "4")
        top.set(qn("w:space"), "1")
        top.set(qn("w:color"), "000000")
        pBdr.append(top)
        pPr.append(pBdr)
    if theme.heading_underline:
        pBdr = OxmlElement("w:pBdr")
        bottom = OxmlElement("w:bottom")
        bottom.set(qn("w:val"), "single")
        bottom.set(qn("w:sz"), "6")
        bottom.set(qn("w:space"), "1")
        r2, g2, b2 = theme.accent_color
        bottom.set(qn("w:color"), f"{r2:02x}{g2:02x}{b2:02x}")
        pBdr.append(bottom)
        pPr.append(pBdr)
    keepNext = OxmlElement("w:keepNext")
    pPr.append(keepNext)
    return p


def _body_paragraph(doc: "DocxDocument", text: str, italic: bool = False,
                    before_pt: float = 0, after_pt: float = 2, body_pt: int = 10,
                    font_name: str = "Arial"):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    _set_space(p, before_pt=before_pt, after_pt=after_pt)
    run = p.add_run(text)
    _set_font(run, body_pt, italic=italic, font_name=font_name)
    return p


def _bullet(doc: "DocxDocument", text: str, body_pt: int = 10, font_name: str = "Arial"):
    p = doc.add_paragraph(style="List Bullet")
    _set_space(p, before_pt=0, after_pt=1)
    # Clear default run and add our own with correct font
    for run in p.runs:
        p._p.remove(run._r)
    run = p.add_run(text)
    _set_font(run, body_pt, font_name=font_name)
    return p


def _company_line(doc: "DocxDocument", company: str, location: str, dates: str,
                  right_tab_twips: int | None = None, body_pt: int = 10,
                  font_name: str = "Arial"):
    """Company + location LEFT, dates RIGHT using a tab stop."""
    p = doc.add_paragraph()
    _set_space(p, before_pt=6, after_pt=0)
    if right_tab_twips:
        _add_right_tab(p, right_tab_twips)
    else:
        _add_right_tab(p)
    left_text = f"{company}  |  {location}" if location else company
    run_left = p.add_run(left_text)
    _set_font(run_left, body_pt, bold=True, font_name=font_name)
    run_tab = p.add_run("\t")
    run_tab.font.size = Pt(body_pt)
    run_dates = p.add_run(dates)
    _set_font(run_dates, body_pt, bold=True, font_name=font_name)
    return p


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _end_year(exp) -> int:
    """Extract the end year from an ExperienceEntry's dates string for sorting.

    Returns 9999 for 'Present' / 'Current' so active roles sort to the top.
    Falls back to the last 4-digit year found, or 0 if none.
    """
    dates = exp.dates or ""
    if re.search(r"\b(present|current)\b", dates, re.IGNORECASE):
        return 9999
    years = re.findall(r"\b(19|20)\d{2}\b", dates)
    return int(years[-1]) if years else 0


# ---------------------------------------------------------------------------
# Sidebar resume builder (Creative theme)
# ---------------------------------------------------------------------------


def _build_resume_sidebar(resume_json: ResumeJSON, personal: dict, education: list,
                           output_path: str, theme: ThemeConfig):
    """Render resume with two-column sidebar layout (Creative theme)."""
    doc = Document()
    sr, sg, sb = theme.sidebar_color
    sidebar_hex = f"{sr:02x}{sg:02x}{sb:02x}"

    for section in doc.sections:
        section.top_margin = Inches(theme.margin_top)
        section.bottom_margin = Inches(theme.margin_bottom)
        section.left_margin = Inches(theme.margin_left)
        section.right_margin = Inches(theme.margin_right)

    sec = doc.sections[0]
    text_width_emu = (sec.page_width or 0) - (sec.left_margin or 0) - (sec.right_margin or 0)
    sidebar_width_emu = int(text_width_emu * 0.28)
    main_width_emu = text_width_emu - sidebar_width_emu

    table = doc.add_table(rows=1, cols=2)
    table.autofit = False
    left_cell = table.cell(0, 0)
    right_cell = table.cell(0, 1)
    _no_border_cell(left_cell)
    _no_border_cell(right_cell)

    left_cell.width = sidebar_width_emu
    right_cell.width = main_width_emu
    _shade_cell(left_cell, sidebar_hex)

    # --- Sidebar content ---
    p = left_cell.paragraphs[0]
    _set_space(p, before_pt=6, after_pt=2)
    run = p.add_run(personal["name"])
    _set_font(run, theme.name_pt, bold=True, color=RGBColor(255, 255, 255),
              font_name=theme.font)

    loc = personal.get("location", {})
    location_str = (
        ", ".join(part for part in [loc.get("city", ""), loc.get("region", "")] if part)
        if isinstance(loc, dict) else str(loc or "")
    )
    for line in filter(None, [
        location_str,
        personal.get("phone", ""),
        personal.get("email", ""),
    ]):
        cp = left_cell.add_paragraph()
        _set_space(cp, before_pt=1, after_pt=1)
        cr = cp.add_run(line)
        _set_font(cr, theme.body_pt - 1, color=RGBColor(200, 200, 200),
                  font_name=theme.font)

    def _sidebar_section(text: str):
        sp = left_cell.add_paragraph()
        _set_space(sp, before_pt=10, after_pt=3)
        sr = sp.add_run(text.upper())
        _set_font(sr, theme.heading_pt, bold=True, color=RGBColor(180, 180, 180),
                  font_name=theme.font)
        pPr = sp._p.get_or_add_pPr()
        pBdr = OxmlElement("w:pBdr")
        bottom = OxmlElement("w:bottom")
        bottom.set(qn("w:val"), "single")
        bottom.set(qn("w:sz"), "4")
        bottom.set(qn("w:space"), "1")
        bottom.set(qn("w:color"), "666666")
        pBdr.append(bottom)
        pPr.append(pBdr)

    _sidebar_section("Skills")
    for cat in resume_json.skill_categories:
        lp = left_cell.add_paragraph()
        _set_space(lp, before_pt=3, after_pt=1)
        lr = lp.add_run(cat.name)
        _set_font(lr, theme.body_pt - 1, bold=True, color=RGBColor(220, 220, 220),
                  font_name=theme.font)
        for skill in cat.skills:
            sp2 = left_cell.add_paragraph()
            _set_space(sp2, before_pt=1, after_pt=0)
            sr2 = sp2.add_run(skill)
            _set_font(sr2, theme.body_pt - 1, color=RGBColor(190, 190, 190),
                      font_name=theme.font)

    if education:
        _sidebar_section("Education")
        for ed in education:
            degree_parts = [ed.get("studyType", ""), ed.get("area", "")]
            degree = " - ".join(pt for pt in degree_parts if pt)
            ep = left_cell.add_paragraph()
            _set_space(ep, before_pt=3, after_pt=1)
            er = ep.add_run(degree or ed.get("institution", ""))
            _set_font(er, theme.body_pt - 1, bold=True, color=RGBColor(220, 220, 220),
                      font_name=theme.font)
            if degree and ed.get("institution"):
                ip = left_cell.add_paragraph()
                _set_space(ip, before_pt=0, after_pt=0)
                ir = ip.add_run(ed["institution"])
                _set_font(ir, theme.body_pt - 1, color=RGBColor(190, 190, 190),
                          font_name=theme.font)

    # --- Main column content ---
    def _main_section(text: str):
        mp = right_cell.add_paragraph()
        _set_space(mp, before_pt=10, after_pt=3)
        mr = mp.add_run(text.upper())
        _set_font(mr, theme.heading_pt, bold=True, font_name=theme.font)
        pPr = mp._p.get_or_add_pPr()
        if theme.heading_underline:
            pBdr = OxmlElement("w:pBdr")
            bottom = OxmlElement("w:bottom")
            bottom.set(qn("w:val"), "single")
            bottom.set(qn("w:sz"), "6")
            bottom.set(qn("w:space"), "1")
            bottom.set(qn("w:color"), "000000")
            pBdr.append(bottom)
            pPr.append(pBdr)
        keepNext = OxmlElement("w:keepNext")
        pPr.append(keepNext)

    right_tab = int(main_width_emu / 635)

    _main_section("Professional Summary")
    sp = right_cell.add_paragraph()
    _set_space(sp, before_pt=2, after_pt=4)
    sr = sp.add_run(resume_json.summary.strip())
    _set_font(sr, theme.body_pt, font_name=theme.font)

    _main_section("Professional Experience")
    for exp in sorted(resume_json.experience, key=_end_year, reverse=True):
        cp = right_cell.add_paragraph()
        _set_space(cp, before_pt=6, after_pt=0)
        if right_tab:
            _add_right_tab(cp, right_tab)
        lr = cp.add_run(f"{exp.company}")
        _set_font(lr, theme.body_pt, bold=True, font_name=theme.font)
        tr = cp.add_run("\t" + exp.dates)
        _set_font(tr, theme.body_pt, bold=True, font_name=theme.font)
        rp = right_cell.add_paragraph()
        _set_space(rp, before_pt=1, after_pt=1)
        rr = rp.add_run(exp.role)
        _set_font(rr, theme.body_pt, italic=True, font_name=theme.font)
        for bullet in exp.bullets:
            bp = right_cell.add_paragraph(style="List Bullet")
            _set_space(bp, before_pt=0, after_pt=1)
            for run in bp.runs:
                bp._p.remove(run._r)
            brun = bp.add_run(bullet)
            _set_font(brun, theme.body_pt, font_name=theme.font)

    if resume_json.projects:
        _main_section(resume_json.projects_section_heading)
        for proj in resume_json.projects:
            pp = right_cell.add_paragraph()
            _set_space(pp, before_pt=4, after_pt=0)
            pr = pp.add_run(proj.title)
            _set_font(pr, theme.body_pt, bold=True, font_name=theme.font)
            for bullet in proj.bullets:
                bp = right_cell.add_paragraph(style="List Bullet")
                _set_space(bp, before_pt=0, after_pt=1)
                for run in bp.runs:
                    bp._p.remove(run._r)
                brun = bp.add_run(bullet)
                _set_font(brun, theme.body_pt, font_name=theme.font)

    if resume_json.certifications:
        _sidebar_section("Certifications")
        for cert in resume_json.certifications:
            cp2 = left_cell.add_paragraph()
            _set_space(cp2, before_pt=2, after_pt=1)
            cr2 = cp2.add_run(cert)
            _set_font(cr2, theme.body_pt - 1, color=RGBColor(190, 190, 190),
                      font_name=theme.font)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    doc.save(output_path)
    return output_path


# ---------------------------------------------------------------------------
# Resume builder
# ---------------------------------------------------------------------------


def build_resume(resume_json: ResumeJSON, personal: dict, education: list,
                 output_path: str, theme: ThemeConfig = CLASSIC):
    if theme.layout == "sidebar":
        return _build_resume_sidebar(resume_json, personal, education, output_path, theme)

    doc = Document()

    # Page margins from theme
    for section in doc.sections:
        section.top_margin = Inches(theme.margin_top)
        section.bottom_margin = Inches(theme.margin_bottom)
        section.left_margin = Inches(theme.margin_left)
        section.right_margin = Inches(theme.margin_right)

    # Compute right-tab position from actual page geometry (EMU → twips)
    sec = doc.sections[0]
    text_width_emu = (sec.page_width or 0) - (sec.left_margin or 0) - (sec.right_margin or 0)
    right_tab = int(text_width_emu / 635)  # 1 twip = 635 EMU

    # --- Header ---
    name_p = doc.add_paragraph()
    name_p.alignment = (
        WD_ALIGN_PARAGRAPH.LEFT if theme.name_align == "left"
        else WD_ALIGN_PARAGRAPH.CENTER
    )
    _set_space(name_p, before_pt=0, after_pt=2)
    name_run = name_p.add_run(personal["name"])
    _set_font(name_run, theme.name_pt, bold=True, color=RGBColor(*theme.accent_color),
              font_name=theme.font)

    loc = personal.get("location", {})
    loc_parts = [loc.get("city", ""), loc.get("region", ""), loc.get("countryCode", "")]
    location_str = (
        ", ".join(p for p in loc_parts if p) if isinstance(loc, dict) else str(loc or "")
    )
    linkedin = next(
        (p.get("username", "") for p in personal.get("profiles", [])
         if p.get("network") == "LinkedIn"), ""
    )
    github = next(
        (p.get("username", "") for p in personal.get("profiles", [])
         if p.get("network") == "GitHub"), ""
    )
    contact_parts = [
        location_str,
        personal.get("phone", ""),
        personal.get("email", ""),
        f"LinkedIn: {linkedin}" if linkedin else "",
        f"GitHub: {github}" if github else "",
    ]
    contact_line = " \u2219 ".join(p for p in contact_parts if p)
    contact_p = doc.add_paragraph()
    contact_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _set_space(contact_p, before_pt=0, after_pt=4)
    contact_run = contact_p.add_run(contact_line)
    _set_font(contact_run, theme.body_pt, font_name=theme.font)

    # --- Summary ---
    _section_heading(doc, "Professional Summary", theme)
    _body_paragraph(doc, resume_json.summary.strip(), after_pt=2, body_pt=theme.body_pt,
                    font_name=theme.font)

    # --- Professional Experience ---
    _section_heading(doc, "Professional Experience", theme)
    for exp in sorted(resume_json.experience, key=_end_year, reverse=True):
        _company_line(doc, exp.company, "", exp.dates, right_tab_twips=right_tab,
                      body_pt=theme.body_pt, font_name=theme.font)
        _body_paragraph(doc, exp.role, italic=True, before_pt=1, after_pt=1,
                        body_pt=theme.body_pt, font_name=theme.font)
        for bullet in exp.bullets:
            _bullet(doc, bullet, body_pt=theme.body_pt, font_name=theme.font)

    # --- Skills ---
    _section_heading(doc, "Skills", theme)
    for cat in resume_json.skill_categories:
        p = doc.add_paragraph(style="List Bullet")
        _set_space(p, before_pt=1, after_pt=1)
        for run in p.runs:
            p._p.remove(run._r)
        label_run = p.add_run(f"{cat.name}: ")
        _set_font(label_run, theme.body_pt, bold=True, font_name=theme.font)
        skills_run = p.add_run(", ".join(cat.skills))
        _set_font(skills_run, theme.body_pt, font_name=theme.font)

    # --- Projects (conditional) ---
    if resume_json.projects:
        _section_heading(doc, resume_json.projects_section_heading, theme)
        for proj in resume_json.projects:
            # Project title line
            p = doc.add_paragraph()
            _set_space(p, before_pt=4, after_pt=0)
            title_run = p.add_run(proj.title)
            _set_font(title_run, theme.body_pt, bold=True, font_name=theme.font)
            if proj.focus:
                focus_run = p.add_run(f"  —  {proj.focus}")
                _set_font(focus_run, theme.body_pt, italic=True, font_name=theme.font)
            for bullet in proj.bullets:
                _bullet(doc, bullet, body_pt=theme.body_pt, font_name=theme.font)
            if proj.url:
                url_p = doc.add_paragraph()
                _set_space(url_p, before_pt=0, after_pt=1)
                url_run = url_p.add_run(proj.url)
                _set_font(url_run, theme.body_pt, italic=True, font_name=theme.font)

    # --- Education & Certificates (2-column bullets when certs present) ---
    has_certs = bool(resume_json.certifications)
    _section_heading(doc, "Education & Certificates" if has_certs else "Education", theme)

    if has_certs:
        table = doc.add_table(rows=1, cols=2)
        table.autofit = True
        left_cell = table.cell(0, 0)
        right_cell = table.cell(0, 1)
        _no_border_cell(left_cell)
        _no_border_cell(right_cell)

        left_cell.paragraphs[0].clear()
        for ed in education:
            degree_parts = [ed.get("studyType", ""), ed.get("area", "")]
            degree = " - ".join(p for p in degree_parts if p)
            parts = [degree, ed.get("institution", "")]
            text = " | ".join(p for p in parts if p)
            _cell_bullet(left_cell, text)

        right_cell.paragraphs[0].clear()
        for cert in resume_json.certifications:
            _cell_bullet(right_cell, cert)
    else:
        for ed in education:
            degree_parts = [ed.get("studyType", ""), ed.get("area", "")]
            degree = " - ".join(p for p in degree_parts if p)
            parts = [degree, ed.get("institution", "")]
            text = " | ".join(p for p in parts if p)
            _bullet(doc, text, body_pt=theme.body_pt, font_name=theme.font)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    doc.save(output_path)
    return output_path


# ---------------------------------------------------------------------------
# Cover letter builder
# ---------------------------------------------------------------------------

COVER_PT = 12  # body font size for cover letters (larger than resume's 10pt)


def _cover_paragraph(doc: "DocxDocument", text: str, indent: bool = False,
                     before_pt: float = 6, after_pt: float = 6,
                     cover_pt: int = COVER_PT, font_name: str = "Arial") -> object:
    p = doc.add_paragraph()
    _set_space(p, before_pt=before_pt, after_pt=after_pt)
    if indent:
        p.paragraph_format.first_line_indent = Inches(0.5)
    run = p.add_run(text.strip())
    _set_font(run, cover_pt, font_name=font_name)
    return p


def _cover_bullet(doc: "DocxDocument", text: str, cover_pt: int = COVER_PT,
                  font_name: str = "Arial"):
    p = doc.add_paragraph(style="List Bullet")
    _set_space(p, before_pt=0, after_pt=2)
    for run in p.runs:
        p._p.remove(run._r)
    run = p.add_run(text)
    _set_font(run, cover_pt, font_name=font_name)
    return p


def build_cover_letter(cover_json: CoverLetterJSON, personal: dict,
                       company: str, _job_title: str, output_path: str,
                       theme: ThemeConfig = CLASSIC):
    doc = Document()
    cover_pt = theme.body_pt + 2

    for section in doc.sections:
        section.top_margin = Inches(max(theme.margin_top, 1.0))
        section.bottom_margin = Inches(max(theme.margin_bottom, 1.0))
        section.left_margin = Inches(max(theme.margin_left, 1.0))
        section.right_margin = Inches(max(theme.margin_right, 1.0))

    # --- Personal header ---
    name_p = doc.add_paragraph()
    _set_space(name_p, before_pt=0, after_pt=2)
    name_run = name_p.add_run(personal["name"])
    _set_font(name_run, theme.name_pt, bold=True, color=RGBColor(*theme.accent_color),
              font_name=theme.font)

    loc = personal.get("location", {})
    loc_parts = [loc.get("city", ""), loc.get("region", ""), loc.get("countryCode", "")]
    location_str = (
        ", ".join(p for p in loc_parts if p) if isinstance(loc, dict) else str(loc or "")
    )
    linkedin = next(
        (p.get("username", "") for p in personal.get("profiles", [])
         if p.get("network") == "LinkedIn"), ""
    )
    github = next(
        (p.get("username", "") for p in personal.get("profiles", [])
         if p.get("network") == "GitHub"), ""
    )
    line1_parts = [
        location_str,
        personal.get("phone", ""),
        personal.get("email", ""),
    ]
    line2_parts = [
        f"LinkedIn: {linkedin}" if linkedin else "",
        f"GitHub: {github}" if github else "",
    ]
    contact_p = doc.add_paragraph()
    _set_space(contact_p, before_pt=0, after_pt=12)
    line1 = " \u2219 ".join(p for p in line1_parts if p)
    line2 = " \u2219 ".join(p for p in line2_parts if p)
    run1 = contact_p.add_run(line1)
    _set_font(run1, cover_pt, font_name=theme.font)
    if line2:
        run1.add_break()
        run2 = contact_p.add_run(line2)
        _set_font(run2, cover_pt, font_name=theme.font)

    # --- Date (right-aligned) ---
    today = date.today().strftime("%B %d, %Y")
    date_p = doc.add_paragraph()
    date_p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    _set_space(date_p, after_pt=12)
    date_run = date_p.add_run(today)
    _set_font(date_run, cover_pt, font_name=theme.font)

    # --- Greeting ---
    greeting_p = doc.add_paragraph()
    _set_space(greeting_p, after_pt=6)
    greeting_run = greeting_p.add_run(f"Dear Hiring Manager at {company},")
    _set_font(greeting_run, cover_pt, font_name=theme.font)

    # --- Opening paragraph ---
    _cover_paragraph(doc, cover_json.opening, indent=True, cover_pt=cover_pt,
                     font_name=theme.font)

    # --- Body paragraphs ---
    for para in cover_json.body_paragraphs:
        _cover_paragraph(doc, para, indent=True, cover_pt=cover_pt, font_name=theme.font)

    # --- Highlights bullets (optional) ---
    if cover_json.highlights:
        intro = cover_json.highlights_intro or "A few highlights from my background:"
        _cover_paragraph(doc, intro, indent=True, before_pt=6, after_pt=2, cover_pt=cover_pt,
                         font_name=theme.font)
        for item in cover_json.highlights:
            _cover_bullet(doc, item, cover_pt=cover_pt, font_name=theme.font)

    # --- Closing paragraph ---
    _cover_paragraph(doc, cover_json.closing, indent=True, before_pt=8, cover_pt=cover_pt,
                     font_name=theme.font)

    # --- Sign-off ---
    signoff_p = doc.add_paragraph()
    _set_space(signoff_p, before_pt=16, after_pt=2)
    signoff_run = signoff_p.add_run("Sincerely,")
    _set_font(signoff_run, cover_pt, font_name=theme.font)

    sig_name_p = doc.add_paragraph()
    _set_space(sig_name_p, before_pt=24, after_pt=0)
    sig_name_run = sig_name_p.add_run(personal["name"])
    _set_font(sig_name_run, cover_pt, bold=True, font_name=theme.font)

    sig_contact_parts = [personal.get("email", ""), personal.get("phone", "")]
    sig_contact_p = doc.add_paragraph()
    _set_space(sig_contact_p, before_pt=2, after_pt=0)
    sig_contact_run = sig_contact_p.add_run("  |  ".join(p for p in sig_contact_parts if p))
    _set_font(sig_contact_run, cover_pt, font_name=theme.font)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    doc.save(output_path)
    return output_path
