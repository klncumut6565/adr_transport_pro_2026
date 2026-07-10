"""Hakkında diyaloğu."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QVBoxLayout

from .. import __version__
from ..constants import APP_NAME


class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"{APP_NAME} Hakkında")
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)

        title = QLabel(APP_NAME)
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title)

        version_label = QLabel(f"Sürüm {__version__}")
        version_label.setStyleSheet("color: #777;")
        layout.addWidget(version_label)

        description = QLabel(
            "ADR 7.5.2 (Karışık yükleme yasağı) kapsamında, UN numarası, "
            "tehlike sınıfı ve etiket bilgisi bilinen ürünlerin aynı araç "
            "veya konteyner içinde birlikte taşınıp taşınamayacağını "
            "analiz eden bir karar destek aracıdır."
        )
        description.setWordWrap(True)
        layout.addWidget(description)

        disclaimer = QLabel(
            "<b>Yasal Uyarı:</b> Bu yazılım ADR Tablo 7.5.2.1'in "
            "basitleştirilmiş bir uygulamasıdır. Sınıf 1 (patlayıcı) "
            "uyumluluk grupları, miktar bazlı istisnalar ve tank "
            "taşımacılığına özel hükümler kapsam dışındadır. Nihai "
            "sevkiyat kararından önce güncel ADR metni ile bir Tehlikeli "
            "Madde Güvenlik Danışmanına (TMGD/DGSA) danışılması önerilir."
        )
        disclaimer.setWordWrap(True)
        disclaimer.setStyleSheet("color: #B45309; margin-top: 8px;")
        layout.addWidget(disclaimer)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)
