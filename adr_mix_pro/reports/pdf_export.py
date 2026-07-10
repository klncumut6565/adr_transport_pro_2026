"""Sonuçların profesyonel görünümlü bir PDF rapor olarak dışa aktarılması."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from ..config import FONT_BOLD_PATH, FONT_REGULAR_PATH
from ..constants import (
    APP_NAME,
    REPORT_TITLE,
    STATUS_EXPLOSIVE_SPECIAL,
    STATUS_FOOD_CAUTION,
    STATUS_FORBIDDEN,
    STATUS_LABELS,
    STATUS_OK,
    STATUS_UNKNOWN,
)
from ..exceptions import ExportError
from ..models import PairCheckResult

FONT_NAME = "Helvetica"
FONT_NAME_BOLD = "Helvetica-Bold"
_FONTS_REGISTERED = False


def _register_fonts() -> None:
    """Türkçe karakterler (ç, ğ, ı, ö, ş, ü) için DejaVu Sans yazı tipini kaydeder.

    Bundan sonra rapor genelinde varsayılan Helvetica yerine bu fontlar
    kullanılır. Paketlenen .ttf dosyaları bulunamazsa (örn. kurulum
    bozuksa), sessizce Helvetica'ya geri döner; bu durumda yalnızca Türkçe'ye
    özgü karakterler (ı, ğ, ş) PDF'te eksik görüntülenebilir, uygulama
    çökmez.
    """

    global FONT_NAME, FONT_NAME_BOLD, _FONTS_REGISTERED

    if _FONTS_REGISTERED:
        return

    try:
        pdfmetrics.registerFont(TTFont("DejaVuSans", str(FONT_REGULAR_PATH)))
        pdfmetrics.registerFont(TTFont("DejaVuSans-Bold", str(FONT_BOLD_PATH)))
        FONT_NAME = "DejaVuSans"
        FONT_NAME_BOLD = "DejaVuSans-Bold"
    except Exception:
        FONT_NAME = "Helvetica"
        FONT_NAME_BOLD = "Helvetica-Bold"

    _FONTS_REGISTERED = True

_ROW_COLOR_BY_STATUS = {
    STATUS_OK: colors.HexColor("#E2F0D9"),
    STATUS_FORBIDDEN: colors.HexColor("#F8CBAD"),
    STATUS_UNKNOWN: colors.HexColor("#FFF2CC"),
    STATUS_EXPLOSIVE_SPECIAL: colors.HexColor("#D9D2E9"),
    STATUS_FOOD_CAUTION: colors.HexColor("#FCE4D6"),
}

_PRIMARY_COLOR = colors.HexColor("#1F3864")


def _build_styles():
    _register_fonts()
    styles = getSampleStyleSheet()
    styles["Normal"].fontName = FONT_NAME
    styles["Title"].fontName = FONT_NAME_BOLD
    styles["Heading2"].fontName = FONT_NAME_BOLD
    styles.add(
        ParagraphStyle(
            name="ReportTitle",
            parent=styles["Title"],
            textColor=_PRIMARY_COLOR,
            fontName=FONT_NAME_BOLD,
            fontSize=20,
            spaceAfter=6,
        )
    )
    styles.add(
        ParagraphStyle(
            name="ReportSubtitle",
            parent=styles["Normal"],
            textColor=colors.HexColor("#595959"),
            fontName=FONT_NAME,
            fontSize=11,
            spaceAfter=18,
        )
    )
    styles.add(
        ParagraphStyle(
            name="SectionHeading",
            parent=styles["Heading2"],
            textColor=_PRIMARY_COLOR,
            fontName=FONT_NAME_BOLD,
            spaceBefore=14,
            spaceAfter=8,
        )
    )
    styles.add(
        ParagraphStyle(
            name="CellText",
            parent=styles["Normal"],
            fontName=FONT_NAME,
            fontSize=8,
            leading=10,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Disclaimer",
            parent=styles["Normal"],
            fontName=FONT_NAME,
            fontSize=8,
            textColor=colors.HexColor("#7F7F7F"),
        )
    )
    return styles


def _summary_table(results: list[PairCheckResult], styles) -> Table:
    counts: dict[str, int] = {}
    for r in results:
        counts[r.status] = counts.get(r.status, 0) + 1

    rows = [["Durum", "Adet"]]
    for status, label in STATUS_LABELS.items():
        if counts.get(status):
            rows.append([label, str(counts[status])])
    rows.append(["TOPLAM", str(len(results))])

    table = Table(rows, colWidths=[10 * cm, 3 * cm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), _PRIMARY_COLOR),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), FONT_NAME_BOLD),
                ("FONTNAME", (0, 1), (-1, -2), FONT_NAME),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#BFBFBF")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, colors.HexColor("#F2F2F2")]),
                ("FONTNAME", (0, -1), (-1, -1), FONT_NAME_BOLD),
                ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#D9D9D9")),
            ]
        )
    )
    return table


def _results_table(results: list[PairCheckResult], styles) -> Table:
    header = ["UN 1", "Madde 1", "UN 2", "Madde 2", "Durum", "ADR", "Açıklama"]
    rows = [header]

    for r in results:
        rows.append(
            [
                Paragraph(r.un1, styles["CellText"]),
                Paragraph(r.name1, styles["CellText"]),
                Paragraph(r.un2, styles["CellText"]),
                Paragraph(r.name2, styles["CellText"]),
                Paragraph(STATUS_LABELS.get(r.status, r.status), styles["CellText"]),
                Paragraph(r.adr_reference, styles["CellText"]),
                Paragraph(r.reason, styles["CellText"]),
            ]
        )

    col_widths = [1.6 * cm, 4 * cm, 1.6 * cm, 4 * cm, 2.6 * cm, 1.8 * cm, 5.4 * cm]
    table = Table(rows, colWidths=col_widths, repeatRows=1)

    style_commands = [
        ("BACKGROUND", (0, 0), (-1, 0), _PRIMARY_COLOR),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), FONT_NAME_BOLD),
        ("FONTSIZE", (0, 0), (-1, 0), 8),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#BFBFBF")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]

    for row_index, r in enumerate(results, start=1):
        color = _ROW_COLOR_BY_STATUS.get(r.status)
        if color is not None:
            style_commands.append(("BACKGROUND", (0, row_index), (-1, row_index), color))

    table.setStyle(TableStyle(style_commands))
    return table


def export_results_to_pdf(
    results: list[PairCheckResult],
    filepath: str | Path,
    prepared_by: str = "",
    company_name: str = "",
) -> None:
    if not results:
        raise ExportError("Dışa aktarılacak sonuç bulunmuyor.")

    styles = _build_styles()
    story = []

    story.append(Paragraph(REPORT_TITLE, styles["ReportTitle"]))
    subtitle = f"{APP_NAME} tarafından oluşturuldu — {datetime.now().strftime('%d.%m.%Y %H:%M')}"
    if company_name:
        subtitle = f"{company_name} | {subtitle}"
    story.append(Paragraph(subtitle, styles["ReportSubtitle"]))

    story.append(Paragraph("Özet", styles["SectionHeading"]))
    story.append(_summary_table(results, styles))
    story.append(Spacer(1, 16))

    story.append(Paragraph("Detaylı Sonuçlar", styles["SectionHeading"]))
    story.append(_results_table(results, styles))
    story.append(Spacer(1, 20))

    disclaimer = (
        "Bu rapor, ADR Tablo 7.5.2.1'in basitleştirilmiş bir uygulamasına "
        "dayanmaktadır. Sınıf 1 (patlayıcı) uyumluluk grupları (7.5.2.2), "
        "miktar bazlı istisnalar ve tank taşımacılığına özel hükümler bu "
        "raporun kapsamı dışındadır. Nihai sevkiyat kararından önce güncel "
        "ADR metni ile bir Tehlikeli Madde Güvenlik Danışmanına (TMGD/DGSA) "
        "danışılması önerilir."
    )
    story.append(Paragraph(disclaimer, styles["Disclaimer"]))

    if prepared_by:
        story.append(Spacer(1, 30))
        story.append(
            KeepTogether(
                [
                    Paragraph("Hazırlayan: " + prepared_by, styles["Normal"]),
                    Spacer(1, 24),
                    Paragraph("İmza: ____________________________", styles["Normal"]),
                ]
            )
        )

    try:
        doc = SimpleDocTemplate(
            str(filepath),
            pagesize=A4,
            topMargin=2 * cm,
            bottomMargin=2 * cm,
            leftMargin=1.6 * cm,
            rightMargin=1.6 * cm,
            title=REPORT_TITLE,
            author=APP_NAME,
        )
        doc.build(story)
    except Exception as exc:  # reportlab çok çeşitli hata tipleri fırlatabilir
        raise ExportError(f"PDF rapor oluşturulamadı: {exc}") from exc
