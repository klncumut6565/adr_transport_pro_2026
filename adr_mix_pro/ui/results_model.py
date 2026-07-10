"""Sonuç tablosu için Qt model sınıfı.

``QTableWidget`` yerine ``QAbstractTableModel`` kullanılmıştır; bu, özellikle
yüzlerce/binlerce satırlık sonuç listelerinde (büyük UN listeleri ile
oluşan kombinasyon sayısı hızla büyür) çok daha iyi performans sağlar ve
sıralama/filtreleme gibi özelliklerin eklenmesini kolaylaştırır.
"""

from __future__ import annotations

from PyQt6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PyQt6.QtGui import QColor

from ..constants import (
    STATUS_EXPLOSIVE_SPECIAL,
    STATUS_FOOD_CAUTION,
    STATUS_FORBIDDEN,
    STATUS_LABELS,
    STATUS_OK,
    STATUS_UNKNOWN,
)
from ..models import PairCheckResult

_COLUMNS = ["UN 1", "Madde 1", "UN 2", "Madde 2", "Durum", "ADR", "Açıklama", "Risk"]

# --------------------------------------------------------------------------
# Renk paletleri
# --------------------------------------------------------------------------
# ÖNEMLİ: Önceki sürümde tek bir (açık tema'ya uygun, pastel) arka plan
# rengi seti vardı ve metin rengi sadece "Karışık yükleme yasak" durumu
# için tanımlıydı. Koyu tema açıldığında genel stylesheet metin rengini
# açık griye çeviriyor; bu da açık pastel arka planların üzerinde açık
# renkli metne (düşük kontrast, okunamaz) yol açıyordu. Çözüm: her iki
# tema için de hem arka plan hem de yazı rengini BİRLİKTE, açıkça
# tanımlamak (sadece birini açık temaya göre bırakıp diğerini
# stylesheet'e havale etmemek).

_ROW_COLORS_LIGHT = {
    STATUS_OK: QColor("#E2F0D9"),
    STATUS_FORBIDDEN: QColor("#F8CBAD"),
    STATUS_UNKNOWN: QColor("#FFF2CC"),
    STATUS_EXPLOSIVE_SPECIAL: QColor("#D9D2E9"),
    STATUS_FOOD_CAUTION: QColor("#FCE4D6"),
}

_TEXT_COLORS_LIGHT = {
    STATUS_OK: QColor("#1E4620"),
    STATUS_FORBIDDEN: QColor("#7F1D1D"),
    STATUS_UNKNOWN: QColor("#6B4F00"),
    STATUS_EXPLOSIVE_SPECIAL: QColor("#3B2A5E"),
    STATUS_FOOD_CAUTION: QColor("#7C3A0D"),
}

# Koyu temada pastel zeminler üzerine koyu yazı OKUNMUYOR; bu yüzden koyu
# temada arka planlar da "koyu+doygun", yazılar da "açık+canlı" olacak
# şekilde ayrı bir palet kullanılır (genel koyu arayüzle uyumlu, rozet/etiket
# görünümü).
_ROW_COLORS_DARK = {
    STATUS_OK: QColor("#163A22"),
    STATUS_FORBIDDEN: QColor("#4C1818"),
    STATUS_UNKNOWN: QColor("#473408"),
    STATUS_EXPLOSIVE_SPECIAL: QColor("#332256"),
    STATUS_FOOD_CAUTION: QColor("#4A2A12"),
}

_TEXT_COLORS_DARK = {
    STATUS_OK: QColor("#6FE39B"),
    STATUS_FORBIDDEN: QColor("#FF9B9B"),
    STATUS_UNKNOWN: QColor("#FFD666"),
    STATUS_EXPLOSIVE_SPECIAL: QColor("#D6BBFF"),
    STATUS_FOOD_CAUTION: QColor("#FFB37A"),
}


class ResultsTableModel(QAbstractTableModel):
    def __init__(self, results: list[PairCheckResult] | None = None, parent=None):
        super().__init__(parent)
        self._results: list[PairCheckResult] = results or []
        self._dark_mode: bool = False

    # ------------------------------------------------------------------
    def set_results(self, results: list[PairCheckResult]) -> None:
        self.beginResetModel()
        self._results = results
        self.endResetModel()

    def set_dark_mode(self, enabled: bool) -> None:
        """Aktif renk paletini değiştirir ve görünür hücreleri yeniden boyatır.

        Ana pencere, koyu tema açılıp kapatıldığında bu metodu çağırmalıdır
        (bkz. ``MainWindow._toggle_dark_theme``); aksi halde tablo, genel
        uygulama temasıyla tutarsız (ve okunaksız) kalır.
        """

        if enabled == self._dark_mode:
            return

        self._dark_mode = enabled
        if self._results:
            top_left = self.index(0, 0)
            bottom_right = self.index(len(self._results) - 1, len(_COLUMNS) - 1)
            self.dataChanged.emit(
                top_left,
                bottom_right,
                [Qt.ItemDataRole.BackgroundRole, Qt.ItemDataRole.ForegroundRole],
            )

    def results(self) -> list[PairCheckResult]:
        return self._results

    def result_at(self, row: int) -> PairCheckResult | None:
        if 0 <= row < len(self._results):
            return self._results[row]
        return None

    # ------------------------------------------------------------------
    # QAbstractTableModel arayüzü
    # ------------------------------------------------------------------
    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self._results)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(_COLUMNS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):  # noqa: N802
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal:
            return _COLUMNS[section]
        return str(section + 1)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None

        result = self._results[index.row()]
        column = index.column()

        if role == Qt.ItemDataRole.DisplayRole:
            return self._display_value(result, column)

        if role == Qt.ItemDataRole.BackgroundRole:
            palette = _ROW_COLORS_DARK if self._dark_mode else _ROW_COLORS_LIGHT
            return palette.get(result.status)

        if role == Qt.ItemDataRole.ForegroundRole:
            palette = _TEXT_COLORS_DARK if self._dark_mode else _TEXT_COLORS_LIGHT
            return palette.get(result.status)

        if role == Qt.ItemDataRole.ToolTipRole:
            return result.reason + ("\n\n" + "\n".join(result.notes) if result.notes else "")

        return None

    @staticmethod
    def _display_value(result: PairCheckResult, column: int):
        return [
            result.un1,
            result.name1,
            result.un2,
            result.name2,
            STATUS_LABELS.get(result.status, result.status),
            result.adr_reference,
            result.reason,
            str(result.risk_score),
        ][column]
