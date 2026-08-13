"""Clinician-facing PDF export of a checkup.

Renders the decrypted report as a print-ready A4 document: patient
context, overall risk, per-marker results with reference ranges, the
measurement-quality verdict, analysis provenance (solver, prior source,
burst size), and a trends appendix over the last 30 days.

The document is deliberately conservative: it carries the same
\"not a medical device\" disclaimer as the UI and never suggests a
diagnosis. It is built with fpdf2's built-in (non-embedded) fonts, so
any non-Latin-1 character is normalized to ASCII before rendering.
"""

from __future__ import annotations

from typing import Any

from fpdf import FPDF
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.checkup import Checkup
from app.models.user import User
from app.services.trends import build_trends
from app.utils import crypto

TRENDS_WINDOW_DAYS = 30

_DISCLAIMER = (
    "Not a medical device. Generated from a consumer home test reading; "
    "confirm any clinically significant finding with laboratory testing "
    "and a clinician."
)

# Accent colour (brand green) and a muted grey for table rules.
_ACCENT = (47, 112, 89)
_GREY = (100, 116, 139)
_LIGHT = (241, 245, 249)

_STATE_LABELS = {"low": "Low", "normal": "Normal", "high": "High"}
_RISK_LABELS = {"low": "LOW", "medium": "MEDIUM", "high": "HIGH"}

# Character normalization for the built-in latin-1 core fonts.
_CHAR_MAP = {
    "\u2013": "-",  # en dash
    "\u2014": "-",  # em dash
    "\u2192": "->",  # right arrow
    "\u2018": "'",
    "\u2019": "'",
    "\u201c": '"',
    "\u201d": '"',
    "\u00b5": "u",  # micro sign -> ug/dL
    "\u00b7": "*",  # middle dot
}


def _pdf_safe(text: str | None) -> str:
    """Normalize text to ASCII-compatible latin-1 for the core fonts."""
    if text is None:
        return ""
    for old, new in _CHAR_MAP.items():
        text = text.replace(old, new)
    return text.encode("latin-1", errors="replace").decode("latin-1")


def _fmt(value: float) -> str:
    """Short decimal formatting, dropping trailing zeros."""
    return f"{value:.2f}".rstrip("0").rstrip(".")


class _ReportPdf(FPDF):
    """Small A4 document with a consistent header/footer."""

    def header(self) -> None:
        self.set_font("helvetica", "B", 14)
        self.set_text_color(*_ACCENT)
        self.cell(0, 8, "Doctordrobe Biomarker Report", new_x="LMARGIN", new_y="NEXT")
        self.set_font("helvetica", "", 8)
        self.set_text_color(*_GREY)
        self.cell(0, 4, "Home health analysis", new_x="LMARGIN", new_y="NEXT")
        self.ln(3)

    def footer(self) -> None:
        self.set_y(-15)
        self.set_font("helvetica", "I", 7)
        self.set_text_color(*_GREY)
        self.cell(0, 10, f"Page {self.page_no()}/{{nb}}", align="C")


def _section_heading(pdf: _ReportPdf, text: str) -> None:
    pdf.set_font("helvetica", "B", 11)
    pdf.set_text_color(*_ACCENT)
    pdf.cell(0, 7, _pdf_safe(text), new_x="LMARGIN", new_y="NEXT")
    pdf.set_draw_color(*_ACCENT)
    pdf.set_line_width(0.4)
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
    pdf.ln(2)


def _kv_row(pdf: _ReportPdf, key: str, value: str) -> None:
    pdf.set_font("helvetica", "B", 9)
    pdf.set_text_color(30, 41, 59)
    pdf.cell(45, 6, _pdf_safe(key))
    pdf.set_font("helvetica", "", 9)
    pdf.cell(0, 6, _pdf_safe(value), new_x="LMARGIN", new_y="NEXT")


def _patient_block(pdf: _ReportPdf, user: User) -> None:
    _section_heading(pdf, "Patient")
    bmi = (
        user.weight_kg / ((user.height_cm / 100) ** 2)
        if user.height_cm > 0
        else 0.0
    )
    _kv_row(pdf, "Age / sex", f"{user.age} / {user.sex}")
    _kv_row(pdf, "Height / weight", f"{_fmt(user.height_cm)} cm / {_fmt(user.weight_kg)} kg")
    _kv_row(pdf, "BMI", f"{bmi:.1f}" if bmi else "—")
    _kv_row(pdf, "Activity level", user.activity_level.replace("_", " "))
    _kv_row(pdf, "Device", user.device_id)
    pdf.ln(2)


def _risk_block(pdf: _ReportPdf, report: dict[str, Any], checkup: Checkup) -> None:
    _section_heading(pdf, "Result")
    _kv_row(pdf, "Analyzed on", checkup.created_at.strftime("%Y-%m-%d %H:%M"))
    pdf.set_font("helvetica", "B", 12)
    pdf.set_text_color(*_ACCENT)
    pdf.cell(0, 8, f"Overall risk: {_RISK_LABELS.get(report['overall_risk'], report['overall_risk'])}")
    pdf.ln(4)
    pdf.set_font("helvetica", "", 9)
    pdf.set_text_color(30, 41, 59)
    pdf.multi_cell(0, 5, _pdf_safe(report["text_summary"]), new_x="LMARGIN")
    pdf.ln(2)

    quality = report.get("quality")
    if quality:
        grade = quality.get("grade", "good")
        pdf.set_font("helvetica", "B", 9)
        pdf.set_text_color(*_GREY)
        pdf.cell(0, 5, f"Measurement quality: {grade.upper()}")
        pdf.ln(5)
        pdf.set_font("helvetica", "", 8)
        for reason in quality.get("reasons", []):
            pdf.multi_cell(0, 4, "- " + _pdf_safe(reason), new_x="LMARGIN")
        action = quality.get("recommended_action")
        if action == "retake_reading":
            pdf.multi_cell(
                0, 4, "- Recommended action: retake the reading with a fresh strip.", new_x="LMARGIN"
            )
        pdf.ln(2)


def _biomarker_table(pdf: _ReportPdf, biomarkers: list[dict[str, Any]]) -> None:
    _section_heading(pdf, "Biomarkers")
    col_w = pdf.w - pdf.l_margin - pdf.r_margin
    widths = [col_w * 0.30, col_w * 0.22, col_w * 0.24, col_w * 0.12, col_w * 0.12]
    headers = ["Biomarker", "Value", "Reference", "State", "Conf."]

    pdf.set_fill_color(*_ACCENT)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("helvetica", "B", 8)
    for w, label in zip(widths, headers):
        pdf.cell(w, 6, label, border=1, fill=True)
    pdf.ln()

    pdf.set_font("helvetica", "", 8)
    pdf.set_text_color(30, 41, 59)
    for marker in biomarkers:
        ref = (
            f"{_fmt(marker['ref_low'])} - {_fmt(marker['ref_high'])} {marker['unit']}"
            if marker.get("ref_low") is not None and marker.get("ref_high") is not None
            else "—"
        )
        state = _STATE_LABELS.get(marker["state"], marker["state"])
        confidence = marker.get("confidence")
        value = f"{_fmt(marker['value'])} {marker['unit']}"
        conf = f"{confidence:.0%}" if confidence is not None else "—"
        row = [marker["name"], value, ref, state, conf]
        for w, cell in zip(widths, row):
            pdf.cell(w, 6, _pdf_safe(cell), border=1)
        pdf.ln()
    pdf.ln(2)


def _analysis_block(pdf: _ReportPdf, report: dict[str, Any]) -> None:
    analysis = report.get("analysis")
    if not analysis:
        return
    _section_heading(pdf, "Analysis method")
    pdf.set_font("helvetica", "", 8)
    pdf.set_text_color(*_GREY)
    method = analysis.get("method", "unknown")
    prior = analysis.get("prior_source", "unknown")
    n = analysis.get("n_measurements", "?")
    residual = analysis.get("reconstruction_residual")
    condition = analysis.get("condition_number")
    text = (
        f"Solver: {method}. Prior: {prior}. Snapshots analysed: {n}."
        + (f" Reconstruction residual: {residual}." if residual is not None else "")
        + (f" Condition number: {condition}." if condition is not None else "")
    )
    pdf.multi_cell(0, 4, _pdf_safe(text), new_x="LMARGIN")
    pdf.ln(2)


def _trends_block(pdf: _ReportPdf, trends: dict[str, Any]) -> None:
    _section_heading(pdf, f"Trends (last {trends['window_days']} days)")
    markers = trends.get("markers", {})
    active = [
        marker
        for marker in markers.values()
        if marker.get("stats") is not None and marker["stats"]["count"] >= 2
    ]
    if not active:
        pdf.set_font("helvetica", "", 8)
        pdf.set_text_color(*_GREY)
        pdf.multi_cell(0, 4, "Not enough checkups in this window to show trends.", new_x="LMARGIN")
        return

    pdf.set_font("helvetica", "", 8)
    pdf.set_text_color(30, 41, 59)
    for marker in active:
        stats = marker["stats"]
        pdf.set_font("helvetica", "B", 8)
        pdf.multi_cell(0, 4, f"{marker['name']}  ({stats['count']} checkups)", new_x="LMARGIN")
        pdf.set_font("helvetica", "", 8)
        pdf.multi_cell(
            0,
            4,
            f"  Latest {_fmt(stats['latest'])} {marker['unit']}; "
            f"mean {_fmt(stats['mean'])}; min {_fmt(stats['min'])}; max {_fmt(stats['max'])}.",
            new_x="LMARGIN",
        )
        for alert in marker.get("alerts", []):
            pdf.multi_cell(0, 4, f"  - {_pdf_safe(alert['message'])}", new_x="LMARGIN")
        pdf.ln(1)


async def build_clinician_pdf(
    db: AsyncSession, checkup: Checkup, user: User
) -> bytes:
    """Render a checkup's decrypted report as a PDF document (bytes)."""
    report = crypto.decrypt_json(checkup.encrypted_data)
    trends = await build_trends(db, user.id, TRENDS_WINDOW_DAYS)

    pdf = _ReportPdf(format="A4")
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.set_margins(15, 15, 15)
    pdf.alias_nb_pages()
    pdf.add_page()

    # Title block with the disclaimer.
    pdf.set_font("helvetica", "B", 16)
    pdf.set_text_color(30, 41, 59)
    pdf.multi_cell(0, 8, "Biomarker Checkup Report", new_x="LMARGIN")
    pdf.set_font("helvetica", "I", 8)
    pdf.set_text_color(*_GREY)
    pdf.multi_cell(0, 4, _DISCLAIMER, new_x="LMARGIN")
    pdf.ln(4)

    _patient_block(pdf, user)
    _risk_block(pdf, report, checkup)
    _biomarker_table(pdf, report.get("biomarkers", []))
    _analysis_block(pdf, report)
    _trends_block(pdf, trends)

    return bytes(pdf.output())
