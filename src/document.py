"""
Programmatic Word document builder for resumes and cover letters.

Formatting spec:
  - Font: Arial throughout
  - Body text: 10pt
  - Section headings: 12pt, Bold, ALL CAPS
  - Name header: 14pt, Bold, Centered
  - Contact line: 10pt, Centered
  - Company/location line: 10pt, Bold — company LEFT, dates RIGHT-TABBED
  - Role: 10pt, Italic
  - Bullets: 10pt, 0.25" hanging indent
  - Education & Certs: borderless 2-column table (left=education, right=certs); single-column if no certs returned
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

if TYPE_CHECKING:
    from docx.document import Document as DocxDocument


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

FONT_NAME = "Arial"
BODY_PT = 10
HEADING_PT = 12
NAME_PT = 14
RIGHT_TAB_POS = Twips(9360)  # 6.5" at 1" margins on US Letter


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------


def _set_font(run, size_pt: int, bold: bool = False, italic: bool = False,
              color: RGBColor | None = None):
    run.font.name = FONT_NAME
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
    _set_font(bullet_run, BODY_PT)
    text_run = p.add_run(text)
    _set_font(text_run, BODY_PT)
    return p


def _section_heading(doc: "DocxDocument", text: str):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _set_space(p, before_pt=8, after_pt=2)
    run = p.add_run(text.upper())
    _set_font(run, HEADING_PT, bold=True)
    # Thin top border above heading
    pPr = p._p.get_or_add_pPr()
    pBdr = OxmlElement("w:pBdr")
    top = OxmlElement("w:top")
    top.set(qn("w:val"), "single")
    top.set(qn("w:sz"), "4")
    top.set(qn("w:space"), "1")
    top.set(qn("w:color"), "000000")
    pBdr.append(top)
    pPr.append(pBdr)
    # Keep heading on the same page as the following content
    keepNext = OxmlElement("w:keepNext")
    pPr.append(keepNext)
    return p


def _body_paragraph(doc: "DocxDocument", text: str, italic: bool = False,
                    before_pt: float = 0, after_pt: float = 2):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    _set_space(p, before_pt=before_pt, after_pt=after_pt)
    run = p.add_run(text)
    _set_font(run, BODY_PT, italic=italic)
    return p


def _bullet(doc: "DocxDocument", text: str):
    p = doc.add_paragraph(style="List Bullet")
    _set_space(p, before_pt=0, after_pt=1)
    # Clear default run and add our own with correct font
    for run in p.runs:
        p._p.remove(run._r)
    run = p.add_run(text)
    _set_font(run, BODY_PT)
    return p


def _company_line(doc: "DocxDocument", company: str, location: str, dates: str,
                  right_tab_twips: int | None = None):
    """Company + location LEFT, dates RIGHT using a tab stop."""
    p = doc.add_paragraph()
    _set_space(p, before_pt=6, after_pt=0)
    if right_tab_twips:
        _add_right_tab(p, right_tab_twips)
    else:
        _add_right_tab(p)
    left_text = f"{company}  |  {location}" if location else company
    run_left = p.add_run(left_text)
    _set_font(run_left, BODY_PT, bold=True)
    run_tab = p.add_run("\t")
    run_tab.font.name = FONT_NAME
    run_tab.font.size = Pt(BODY_PT)
    run_dates = p.add_run(dates)
    _set_font(run_dates, BODY_PT, bold=True)
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
# Resume builder
# ---------------------------------------------------------------------------


def build_resume(resume_json: ResumeJSON, personal: dict, education: list,
                 output_path: str):
    doc = Document()

    # Page margins: 0.6" top/bottom, 0.75" left/right for one-page fit
    for section in doc.sections:
        section.top_margin = Inches(0.6)
        section.bottom_margin = Inches(0.6)
        section.left_margin = Inches(0.75)
        section.right_margin = Inches(0.75)

    # Compute right-tab position from actual page geometry (EMU → twips)
    sec = doc.sections[0]
    text_width_emu = (sec.page_width or 0) - (sec.left_margin or 0) - (sec.right_margin or 0)
    right_tab = int(text_width_emu / 635)  # 1 twip = 635 EMU

    # --- Header ---
    name_p = doc.add_paragraph()
    name_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _set_space(name_p, before_pt=0, after_pt=2)
    name_run = name_p.add_run(personal["name"])
    _set_font(name_run, NAME_PT, bold=True)

    loc = personal.get("location", {})
    location_str = ", ".join(p for p in [loc.get("city", ""), loc.get("region", ""), loc.get("countryCode", "")] if p) if isinstance(loc, dict) else str(loc or "")
    linkedin = next((p.get("username", "") for p in personal.get("profiles", []) if p.get("network") == "LinkedIn"), "")
    github = next((p.get("username", "") for p in personal.get("profiles", []) if p.get("network") == "GitHub"), "")
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
    _set_font(contact_run, BODY_PT)

    # --- Summary ---
    _section_heading(doc, "Professional Summary")
    _body_paragraph(doc, resume_json.summary.strip(), after_pt=2)

    # --- Professional Experience ---
    _section_heading(doc, "Professional Experience")
    for exp in sorted(resume_json.experience, key=_end_year, reverse=True):
        _company_line(doc, exp.company, "", exp.dates, right_tab_twips=right_tab)
        _body_paragraph(doc, exp.role, italic=True, before_pt=1, after_pt=1)
        for bullet in exp.bullets:
            _bullet(doc, bullet)

    # --- Skills ---
    _section_heading(doc, "Skills")
    for cat in resume_json.skill_categories:
        p = doc.add_paragraph(style="List Bullet")
        _set_space(p, before_pt=1, after_pt=1)
        for run in p.runs:
            p._p.remove(run._r)
        label_run = p.add_run(f"{cat.name}: ")
        _set_font(label_run, BODY_PT, bold=True)
        skills_run = p.add_run(", ".join(cat.skills))
        _set_font(skills_run, BODY_PT)

    # --- Projects (conditional) ---
    if resume_json.projects:
        _section_heading(doc, resume_json.projects_section_heading)
        for proj in resume_json.projects:
            # Project title line
            p = doc.add_paragraph()
            _set_space(p, before_pt=4, after_pt=0)
            title_run = p.add_run(proj.title)
            _set_font(title_run, BODY_PT, bold=True)
            if proj.focus:
                focus_run = p.add_run(f"  —  {proj.focus}")
                _set_font(focus_run, BODY_PT, italic=True)
            for bullet in proj.bullets:
                _bullet(doc, bullet)
            if proj.url:
                url_p = doc.add_paragraph()
                _set_space(url_p, before_pt=0, after_pt=1)
                url_run = url_p.add_run(proj.url)
                _set_font(url_run, BODY_PT, italic=True)

    # --- Education & Certificates (2-column bullets when certs present) ---
    has_certs = bool(resume_json.certifications)
    _section_heading(doc, "Education & Certificates" if has_certs else "Education")

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
            _bullet(doc, text)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    doc.save(output_path)
    return output_path


# ---------------------------------------------------------------------------
# Cover letter builder
# ---------------------------------------------------------------------------

COVER_PT = 12  # body font size for cover letters (larger than resume's 10pt)


def _cover_paragraph(doc: "DocxDocument", text: str, indent: bool = False,
                     before_pt: float = 6, after_pt: float = 6) -> object:
    p = doc.add_paragraph()
    _set_space(p, before_pt=before_pt, after_pt=after_pt)
    if indent:
        p.paragraph_format.first_line_indent = Inches(0.5)
    run = p.add_run(text.strip())
    _set_font(run, COVER_PT)
    return p


def _cover_bullet(doc: "DocxDocument", text: str):
    p = doc.add_paragraph(style="List Bullet")
    _set_space(p, before_pt=0, after_pt=2)
    for run in p.runs:
        p._p.remove(run._r)
    run = p.add_run(text)
    _set_font(run, COVER_PT)
    return p


def build_cover_letter(cover_json: CoverLetterJSON, personal: dict,
                       company: str, job_title: str, output_path: str):
    doc = Document()

    for section in doc.sections:
        section.top_margin = Inches(1.0)
        section.bottom_margin = Inches(1.0)
        section.left_margin = Inches(1.0)
        section.right_margin = Inches(1.0)

    # --- Personal header ---
    name_p = doc.add_paragraph()
    _set_space(name_p, before_pt=0, after_pt=2)
    name_run = name_p.add_run(personal["name"])
    _set_font(name_run, 14, bold=True)

    loc = personal.get("location", {})
    location_str = ", ".join(p for p in [loc.get("city", ""), loc.get("region", ""), loc.get("countryCode", "")] if p) if isinstance(loc, dict) else str(loc or "")
    linkedin = next((p.get("username", "") for p in personal.get("profiles", []) if p.get("network") == "LinkedIn"), "")
    github = next((p.get("username", "") for p in personal.get("profiles", []) if p.get("network") == "GitHub"), "")
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
    _set_font(run1, COVER_PT)
    if line2:
        run1.add_break()
        run2 = contact_p.add_run(line2)
        _set_font(run2, COVER_PT)

    # --- Date (right-aligned) ---
    today = date.today().strftime("%B %d, %Y")
    date_p = doc.add_paragraph()
    date_p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    _set_space(date_p, after_pt=12)
    date_run = date_p.add_run(today)
    _set_font(date_run, COVER_PT)

    # --- Greeting ---
    greeting_p = doc.add_paragraph()
    _set_space(greeting_p, after_pt=6)
    greeting_run = greeting_p.add_run(f"Dear Hiring Manager at {company},")
    _set_font(greeting_run, COVER_PT)

    # --- Opening paragraph ---
    _cover_paragraph(doc, cover_json.opening, indent=True)

    # --- Body paragraphs ---
    for para in cover_json.body_paragraphs:
        _cover_paragraph(doc, para, indent=True)

    # --- Highlights bullets (optional) ---
    if cover_json.highlights:
        intro = cover_json.highlights_intro or "A few highlights from my background:"
        _cover_paragraph(doc, intro, indent=True, before_pt=6, after_pt=2)
        for item in cover_json.highlights:
            _cover_bullet(doc, item)

    # --- Closing paragraph ---
    _cover_paragraph(doc, cover_json.closing, indent=True, before_pt=8)

    # --- Sign-off ---
    signoff_p = doc.add_paragraph()
    _set_space(signoff_p, before_pt=16, after_pt=2)
    signoff_run = signoff_p.add_run("Sincerely,")
    _set_font(signoff_run, COVER_PT)

    sig_name_p = doc.add_paragraph()
    _set_space(sig_name_p, before_pt=24, after_pt=0)
    sig_name_run = sig_name_p.add_run(personal["name"])
    _set_font(sig_name_run, COVER_PT, bold=True)

    sig_contact_parts = [personal.get("email", ""), personal.get("phone", "")]
    sig_contact_p = doc.add_paragraph()
    _set_space(sig_contact_p, before_pt=2, after_pt=0)
    sig_contact_run = sig_contact_p.add_run("  |  ".join(p for p in sig_contact_parts if p))
    _set_font(sig_contact_run, COVER_PT)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    doc.save(output_path)
    return output_path
