"""Seçili sonuç için anlık (live) güncellenen ayrıntı paneli.

v2.2: Artık sadece ikili karşılaştırma sonucu değil, her iki ürünün
TAM bilgisi (sınıf, sınıflandırma kodu, uyumluluk grubu, paketleme
grubu, özel hükümler, taşıma kategorisi, tünel kodu) de gösterilir.
Ayrıca tüm metin alanları satır kaydırmalı (word-wrap) olup, uzun
açıklamalar için YATAY KAYDIRMA YERİNE dikey büyüyen bir kaydırma alanı
(QScrollArea) kullanılır.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame,
    QLabel,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ..constants import STATUS_LABELS
from ..core.advisory_engine import build_advisory
from ..core.database import ProductDatabase
from ..models import PairCheckResult, ProductRecord


def _bullet_html(items: list[str]) -> str:
    return "<br>".join(f"• {item}" for item in items)


def _product_info_html(record: ProductRecord | None, un_no: str, name_fallback: str) -> str:
    if record is None:
        return f"<b>{un_no}</b> — {name_fallback} <i>(veritabanında ayrıntı bulunamadı)</i>"

    rows = [f"<b>{record.un_no} — {record.display_name}</b>"]

    fields = [
        ("Sınıf", record.hazard_class),
        ("Sınıflandırma kodu", record.classification_code),
        ("Uyumluluk grubu", record.compatibility_group),
        ("Etiketler", ", ".join(record.labels) if record.labels else ""),
        ("Paketleme grubu", record.packing_group),
        ("Özel hükümler", record.special_provisions),
        ("Taşıma kategorisi", record.transport_category),
        ("Tünel sınırlama kodu", record.tunnel_code),
    ]
    detail_parts = [f"{label}: {value}" for label, value in fields if value]
    if detail_parts:
        rows.append(" &nbsp;|&nbsp; ".join(detail_parts))

    return "<br>".join(rows)


class ResultDetailPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        self.stack = QStackedWidget()
        outer_layout.addWidget(self.stack)

        self.stack.addWidget(self._build_placeholder_page())
        self.stack.addWidget(self._build_detail_page())

        self.set_result(None)

    # ------------------------------------------------------------------
    def _build_placeholder_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        label = QLabel(
            "Ayrıntıları görmek için soldaki sonuç tablosundan bir satır seçin."
        )
        label.setWordWrap(True)
        label.setStyleSheet("color: #777;")
        layout.addStretch(1)
        layout.addWidget(label)
        layout.addStretch(1)
        return page

    def _build_detail_page(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setSpacing(10)

        # --- Ürün bilgisi kartları ---
        self.product1_label = QLabel()
        self.product1_label.setWordWrap(True)
        self.product1_label.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(self._wrap_in_card(self.product1_label))

        self.product2_label = QLabel()
        self.product2_label.setWordWrap(True)
        self.product2_label.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(self._wrap_in_card(self.product2_label))

        # --- Sonuç / durum ---
        self.status_label = QLabel()
        self.status_label.setWordWrap(True)
        self.status_label.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(self.status_label)

        self.reason_label = QLabel()
        self.reason_label.setWordWrap(True)
        self.reason_label.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(self.reason_label)

        self.notes_label = QLabel()
        self.notes_label.setWordWrap(True)
        self.notes_label.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(self.notes_label)

        # --- Tavsiye ---
        self.advisory_label = QLabel()
        self.advisory_label.setWordWrap(True)
        self.advisory_label.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(self.advisory_label)

        self.actions_label = QLabel()
        self.actions_label.setWordWrap(True)
        self.actions_label.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(self.actions_label)

        layout.addStretch(1)
        scroll.setWidget(content)
        return scroll

    @staticmethod
    def _wrap_in_card(label: QLabel) -> QFrame:
        card = QFrame()
        card.setObjectName("Card")
        card_layout = QVBoxLayout(card)
        card_layout.addWidget(label)
        return card

    # ------------------------------------------------------------------
    def set_result(
        self,
        result: PairCheckResult | None,
        database: ProductDatabase | None = None,
    ) -> None:
        """Paneli verilen sonuca göre anında günceller (ya da boş duruma alır).

        ``database`` verilirse, sonuçtaki UN numaraları üzerinden tam ürün
        kaydı (sınıflandırma kodu, uyumluluk grubu, paketleme grubu vb.)
        aranıp gösterilir; verilmezse (örn. veritabanı yüklü değilken bir
        proje açıldıysa) sadece sonuçta saklı temel bilgiler gösterilir.
        """

        if result is None:
            self.stack.setCurrentIndex(0)
            return

        record1 = database.try_get_record(result.un1) if database else None
        record2 = database.try_get_record(result.un2) if database else None

        self.product1_label.setText(_product_info_html(record1, result.un1, result.name1))
        self.product2_label.setText(_product_info_html(record2, result.un2, result.name2))

        self.status_label.setText(
            f"<b>Durum:</b> {STATUS_LABELS.get(result.status, result.status)} "
            f"({result.adr_reference})"
        )
        self.reason_label.setText(f"<b>Açıklama:</b> {result.reason}")

        if result.notes:
            self.notes_label.setText("<b>Ek Notlar:</b><br>" + _bullet_html(result.notes))
            self.notes_label.show()
        else:
            self.notes_label.hide()

        advisory = build_advisory(result.status)
        self.advisory_label.setText(f"<b>Tavsiye:</b> {advisory.summary}")

        if advisory.actions:
            self.actions_label.setText(_bullet_html(advisory.actions))
            self.actions_label.show()
        else:
            self.actions_label.hide()

        self.stack.setCurrentIndex(1)

    def clear(self) -> None:
        self.set_result(None)
