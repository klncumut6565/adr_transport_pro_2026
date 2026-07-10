"""Veritabanında UN numarası / madde adı ile arama yapan diyalog penceresi."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
)

from ..core.database import ProductDatabase
from ..models import ProductRecord


class SearchDialog(QDialog):
    """Kullanıcının veritabanından bir veya daha fazla ürün seçmesini sağlar."""

    def __init__(self, database: ProductDatabase, parent=None):
        super().__init__(parent)
        self.database = database
        self.selected_records: list[ProductRecord] = []

        self.setWindowTitle("Veritabanında Ara")
        self.setMinimumSize(560, 480)

        self._build_ui()
        self._populate(self.database.all_records())

    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        search_row = QHBoxLayout()
        search_row.addWidget(QLabel("Ara (UN No. veya isim):"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("örn. 1090 veya Aseton")
        self.search_edit.textChanged.connect(self._on_search_changed)
        search_row.addWidget(self.search_edit)
        layout.addLayout(search_row)

        self.result_list = QListWidget()
        self.result_list.setSelectionMode(
            QListWidget.SelectionMode.ExtendedSelection
        )
        self.result_list.setWordWrap(True)
        self.result_list.itemDoubleClicked.connect(lambda _: self.accept())
        layout.addWidget(self.result_list)

        self.info_label = QLabel("")
        self.info_label.setStyleSheet("color: #777;")
        layout.addWidget(self.info_label)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    # ------------------------------------------------------------------
    def _populate(self, records: list[ProductRecord]) -> None:
        self.result_list.clear()
        for record in records:
            label = f"{record.un_no}  —  {record.display_name}"
            details = []
            if record.labels:
                details.append("Etiket: " + ", ".join(record.labels))
            if record.classification_code:
                details.append(f"Sınıflandırma kodu: {record.classification_code}")
            if record.compatibility_group:
                details.append(f"Uyumluluk grubu: {record.compatibility_group}")
            if details:
                label += "\n      " + " | ".join(details)
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, record)
            self.result_list.addItem(item)

        self.info_label.setText(f"{len(records)} sonuç bulundu.")

    def _on_search_changed(self, text: str) -> None:
        results = self.database.search(text)
        self._populate(results)

    # ------------------------------------------------------------------
    def accept(self) -> None:  # noqa: D102
        self.selected_records = [
            item.data(Qt.ItemDataRole.UserRole)
            for item in self.result_list.selectedItems()
        ]
        super().accept()
