"""Ana uygulama penceresi.

Kenar çubuğu (sidebar) ile gezilen 4 sayfadan oluşur:
    1) Pano (Dashboard)      - genel durum özeti
    2) Karışık Yükleme       - UN listesi oluşturma ve kontrol çalıştırma
    3) Raporlar              - Excel/PDF dışa aktarım
    4) Ayarlar               - tema, kural dosyası, hakkında/yardım
"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QButtonGroup,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QStatusBar,
    QTableView,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from .. import __version__
from ..config import (
    DEFAULT_RULE_FILE,
    DEFAULT_SAMPLE_DATABASE,
    SIDEBAR_WIDTH,
    SUPPORTED_DATA_FILE_FILTER,
    SUPPORTED_PROJECT_FILE_FILTER,
    WINDOW_HEIGHT,
    WINDOW_TITLE,
    WINDOW_WIDTH,
)
from ..constants import APP_NAME, MAX_UN_ITEMS, STATUS_LABELS
from ..core.checker import MixChecker
from ..core.database import ProductDatabase
from ..core.rule_engine import SegregationRuleEngine
from ..exceptions import ADRError
from ..logging_setup import get_logger
from ..models import PairCheckResult, ProductRecord
from ..reports.excel_export import export_results_to_excel
from ..reports.pdf_export import export_results_to_pdf
from ..storage.project_io import load_project, save_project
from ..validators import is_valid_un, normalize_un
from .about_dialog import AboutDialog
from .help_dialog import HelpDialog
from .result_detail_panel import ResultDetailPanel
from .results_model import ResultsTableModel
from .search_dialog import SearchDialog
from .theme import load_dark_stylesheet

logger = get_logger()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(WINDOW_TITLE)
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)

        # ------------------------------------------------------------
        # Uygulama durumu
        # ------------------------------------------------------------
        self.database: ProductDatabase | None = None
        self.database_path: Path | None = None
        self.rule_file_path: Path = DEFAULT_RULE_FILE
        self.rule_engine: SegregationRuleEngine | None = None
        self.checker: MixChecker | None = None

        self.added_records: dict[str, ProductRecord] = {}
        self.last_results: list[PairCheckResult] = []
        self.last_missing: list[str] = []

        self._dark_theme_enabled = False

        # ------------------------------------------------------------
        # Arayüz
        # ------------------------------------------------------------
        self._build_menu_bar()
        self._build_toolbar()
        self._build_central_widget()
        self.setStatusBar(QStatusBar())
        self._set_status("Hazır.")

        # Varsayılan segregasyon kural dosyasını yükle (uygulama her zaman
        # bir kural setiyle açılır; kullanıcı isterse Ayarlar'dan değiştirir).
        self._load_rule_engine(self.rule_file_path)

        self._refresh_dashboard()

    # ======================================================================
    # Menü / araç çubuğu
    # ======================================================================
    def _build_menu_bar(self) -> None:
        menu_bar = self.menuBar()

        file_menu = menu_bar.addMenu("&Dosya")
        file_menu.addAction("Veritabanı Yükle...", self._action_load_database)
        file_menu.addAction("Örnek Veritabanını Yükle (Demo)", self._action_load_sample_database)
        file_menu.addSeparator()
        file_menu.addAction("Projeyi Kaydet...", self._action_save_project)
        file_menu.addAction("Proje Aç...", self._action_open_project)
        file_menu.addSeparator()
        file_menu.addAction("Çıkış", self.close)

        tools_menu = menu_bar.addMenu("&Araçlar")
        tools_menu.addAction("Kontrol Et", self._action_run_check)
        tools_menu.addAction("Listeyi Temizle", self._action_clear_list)

        view_menu = menu_bar.addMenu("&Görünüm")
        self.dark_theme_action = view_menu.addAction("Koyu Tema")
        self.dark_theme_action.setCheckable(True)
        self.dark_theme_action.toggled.connect(self._toggle_dark_theme)

        help_menu = menu_bar.addMenu("&Yardım")
        help_menu.addAction("Kullanım Kılavuzu", self._action_show_help)
        help_menu.addAction("Hakkında", self._action_show_about)

    def _build_toolbar(self) -> None:
        toolbar = QToolBar("Ana Araç Çubuğu")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        toolbar.addAction("Veritabanı Yükle", self._action_load_database)
        toolbar.addSeparator()
        toolbar.addAction("Kontrol Et", self._action_run_check)
        toolbar.addSeparator()
        toolbar.addAction("Excel'e Aktar", self._action_export_excel)
        toolbar.addAction("PDF Rapor", self._action_export_pdf)

    # ======================================================================
    # Merkezi widget: kenar çubuğu + sayfalar
    # ======================================================================
    def _build_central_widget(self) -> None:
        central = QWidget()
        root_layout = QHBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        root_layout.addWidget(self._build_sidebar())

        self.pages = QStackedWidget()
        self.pages.addWidget(self._build_dashboard_page())
        self.pages.addWidget(self._build_check_page())
        self.pages.addWidget(self._build_reports_page())
        self.pages.addWidget(self._build_settings_page())
        root_layout.addWidget(self.pages, stretch=1)

        self.setCentralWidget(central)

    def _build_sidebar(self) -> QWidget:
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(SIDEBAR_WIDTH)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        title = QLabel(APP_NAME)
        title.setObjectName("AppTitleLabel")
        layout.addWidget(title)

        subtitle = QLabel("ADR 7.5.2 Karışık Yükleme Analizi")
        subtitle.setObjectName("AppSubtitleLabel")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)

        nav_items = [
            ("📊 Pano", 0),
            ("🚚 Karışık Yükleme", 1),
            ("📄 Raporlar", 2),
            ("⚙️ Ayarlar", 3),
        ]

        for text, index in nav_items:
            button = QPushButton(text)
            button.setObjectName("SidebarButton")
            button.setCheckable(True)
            button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            button.clicked.connect(lambda _checked, i=index: self.pages.setCurrentIndex(i))
            self.nav_group.addButton(button, index)
            layout.addWidget(button)

        self.nav_group.button(0).setChecked(True)
        layout.addStretch(1)

        version_label = QLabel(f"v{__version__}")
        version_label.setStyleSheet("color: #888; padding: 8px 16px;")
        layout.addWidget(version_label)

        return sidebar

    # ======================================================================
    # Sayfa: Pano (Dashboard)
    # ======================================================================
    def _build_dashboard_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        heading = QLabel("Pano")
        heading.setObjectName("CardTitle")
        layout.addWidget(heading)

        self.dashboard_db_label = QLabel()
        self.dashboard_db_label.setWordWrap(True)
        layout.addWidget(self.dashboard_db_label)

        self.dashboard_items_label = QLabel()
        layout.addWidget(self.dashboard_items_label)

        self.dashboard_summary_label = QLabel()
        self.dashboard_summary_label.setWordWrap(True)
        layout.addWidget(self.dashboard_summary_label)

        quick_actions = QHBoxLayout()
        load_db_btn = QPushButton("Veritabanı Yükle")
        load_db_btn.clicked.connect(self._action_load_database)
        quick_actions.addWidget(load_db_btn)

        sample_btn = QPushButton("Örnek Veriyi Dene (Demo)")
        sample_btn.clicked.connect(self._action_load_sample_database)
        quick_actions.addWidget(sample_btn)

        goto_check_btn = QPushButton("Karışık Yükleme Sekmesine Git")
        goto_check_btn.setObjectName("PrimaryButton")
        goto_check_btn.clicked.connect(lambda: self._navigate_to(1))
        quick_actions.addWidget(goto_check_btn)

        quick_actions.addStretch(1)
        layout.addLayout(quick_actions)
        layout.addStretch(1)

        return page

    def _navigate_to(self, index: int) -> None:
        self.pages.setCurrentIndex(index)
        button = self.nav_group.button(index)
        if button is not None:
            button.setChecked(True)

    # ======================================================================
    # Sayfa: Karışık Yükleme (Check)
    # ======================================================================
    def _build_check_page(self) -> QWidget:
        page = QWidget()
        outer_layout = QVBoxLayout(page)
        outer_layout.setContentsMargins(24, 24, 24, 24)
        outer_layout.setSpacing(10)

        heading = QLabel("Karışık Yükleme Kontrolü")
        heading.setObjectName("CardTitle")
        outer_layout.addWidget(heading)

        self.check_db_label = QLabel()
        outer_layout.addWidget(self.check_db_label)

        # Sayfanın asıl gövdesi: SOL = kurulum + sonuç tablosu (kompakt),
        # SAĞ = ayrıntı paneli (sayfanın TAM YÜKSEKLİĞİNİ kaplar, geniş).
        # Önceki sürümde ayrıntı paneli sayfanın en altına, dar bir şerit
        # olarak sıkıştırılmıştı; bu, hem az yer kaplıyor hem de görmek
        # için sayfanın altına kaydırmayı gerektiriyordu. Şimdi her zaman
        # tam yükseklikte ve geniş, yatay kaydırma gerektirmeden okunabilir.
        main_splitter = QSplitter(Qt.Orientation.Horizontal)

        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(8)

        # --- UN ekleme satırı ---
        add_row = QHBoxLayout()
        self.un_input = QLineEdit()
        self.un_input.setPlaceholderText("UN numarası girin (örn. 1090) ve Enter'a basın")
        self.un_input.returnPressed.connect(self._action_add_un_from_input)
        add_row.addWidget(self.un_input, stretch=1)

        add_btn = QPushButton("Ekle")
        add_btn.clicked.connect(self._action_add_un_from_input)
        add_row.addWidget(add_btn)

        search_btn = QPushButton("Veritabanında Ara...")
        search_btn.clicked.connect(self._action_open_search_dialog)
        add_row.addWidget(search_btn)

        left_layout.addLayout(add_row)

        # --- Eklenen ürünler listesi (kompakt) ---
        self.added_list = QListWidget()
        self.added_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.added_list.setWordWrap(True)
        self.added_list.setMaximumHeight(110)
        left_layout.addWidget(self.added_list)

        list_actions = QHBoxLayout()
        remove_btn = QPushButton("Seçileni Kaldır")
        remove_btn.clicked.connect(self._action_remove_selected)
        list_actions.addWidget(remove_btn)

        clear_btn = QPushButton("Tümünü Temizle")
        clear_btn.setObjectName("DangerButton")
        clear_btn.clicked.connect(self._action_clear_list)
        list_actions.addWidget(clear_btn)

        list_actions.addStretch(1)

        run_btn = QPushButton("Kontrol Et")
        run_btn.setObjectName("PrimaryButton")
        run_btn.clicked.connect(self._action_run_check)
        list_actions.addWidget(run_btn)

        left_layout.addLayout(list_actions)

        # --- Sonuç tablosu ---
        results_heading = QLabel(
            "Sonuçlar (bir satır seçin; ayrıntılar sağda anında güncellenir)"
        )
        left_layout.addWidget(results_heading)

        self.results_model = ResultsTableModel()
        self.results_table = QTableView()
        self.results_table.setModel(self.results_model)
        self.results_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.results_table.horizontalHeader().setSectionResizeMode(
            4, QHeaderView.ResizeMode.ResizeToContents
        )
        self.results_table.horizontalHeader().setSectionResizeMode(
            5, QHeaderView.ResizeMode.ResizeToContents
        )
        self.results_table.setSelectionBehavior(
            QTableView.SelectionBehavior.SelectRows
        )
        self.results_table.setSelectionMode(
            QTableView.SelectionMode.SingleSelection
        )
        self.results_table.selectionModel().selectionChanged.connect(
            self._on_result_selection_changed
        )
        left_layout.addWidget(self.results_table, stretch=1)

        self.results_summary_label = QLabel("")
        left_layout.addWidget(self.results_summary_label)

        main_splitter.addWidget(left_widget)

        # --- Ayrıntı paneli (sağda, tam yükseklik, geniş) ---
        self.detail_panel = ResultDetailPanel()
        detail_card = QFrame()
        detail_card.setObjectName("Card")
        detail_card_layout = QVBoxLayout(detail_card)
        detail_card_layout.addWidget(self.detail_panel)
        main_splitter.addWidget(detail_card)

        # Ayırıcı sürüklenirken her iki bölmenin de kullanılamayacak kadar
        # küçülmesini önlemek için makul asgari genişlikler.
        left_widget.setMinimumWidth(360)
        detail_card.setMinimumWidth(320)

        # 3:2 oranı -> ayrıntı paneli pencerenin ~%40'ını alır; dar bir
        # şerit değil, gerçekten okunabilir bir alan.
        main_splitter.setStretchFactor(0, 3)
        main_splitter.setStretchFactor(1, 2)
        main_splitter.setSizes([560, 420])

        outer_layout.addWidget(main_splitter, stretch=1)

        return page

    # ======================================================================
    # Sayfa: Raporlar
    # ======================================================================
    def _build_reports_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        heading = QLabel("Raporlar")
        heading.setObjectName("CardTitle")
        layout.addWidget(heading)

        self.reports_status_label = QLabel(
            "Henüz bir kontrol çalıştırılmadı. Önce 'Karışık Yükleme' "
            "sekmesinden bir kontrol çalıştırın."
        )
        self.reports_status_label.setWordWrap(True)
        layout.addWidget(self.reports_status_label)

        form_row = QHBoxLayout()
        self.report_company_input = QLineEdit()
        self.report_company_input.setPlaceholderText("Firma adı (isteğe bağlı)")
        form_row.addWidget(self.report_company_input)

        self.report_author_input = QLineEdit()
        self.report_author_input.setPlaceholderText("Hazırlayan (isteğe bağlı)")
        form_row.addWidget(self.report_author_input)
        layout.addLayout(form_row)

        actions_row = QHBoxLayout()
        excel_btn = QPushButton("Excel'e Aktar (.xlsx)")
        excel_btn.clicked.connect(self._action_export_excel)
        actions_row.addWidget(excel_btn)

        pdf_btn = QPushButton("PDF Rapor Oluştur (.pdf)")
        pdf_btn.setObjectName("PrimaryButton")
        pdf_btn.clicked.connect(self._action_export_pdf)
        actions_row.addWidget(pdf_btn)

        actions_row.addStretch(1)
        layout.addLayout(actions_row)
        layout.addStretch(1)

        return page

    # ======================================================================
    # Sayfa: Ayarlar
    # ======================================================================
    def _build_settings_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        heading = QLabel("Ayarlar")
        heading.setObjectName("CardTitle")
        layout.addWidget(heading)

        self.settings_rule_file_label = QLabel()
        self.settings_rule_file_label.setWordWrap(True)
        layout.addWidget(self.settings_rule_file_label)

        rule_file_btn = QPushButton("Kural Dosyasını Değiştir...")
        rule_file_btn.clicked.connect(self._action_change_rule_file)
        layout.addWidget(rule_file_btn)

        help_row = QHBoxLayout()
        help_btn = QPushButton("Kullanım Kılavuzu")
        help_btn.clicked.connect(self._action_show_help)
        help_row.addWidget(help_btn)

        about_btn = QPushButton("Hakkında")
        about_btn.clicked.connect(self._action_show_about)
        help_row.addWidget(about_btn)
        help_row.addStretch(1)
        layout.addLayout(help_row)

        layout.addStretch(1)
        self._refresh_settings_page()
        return page

    def _refresh_settings_page(self) -> None:
        self.settings_rule_file_label.setText(
            f"<b>Segregasyon kural dosyası:</b><br>{self.rule_file_path}"
        )

    # ======================================================================
    # Eylemler: Veritabanı
    # ======================================================================
    def _action_load_database(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Veritabanı Dosyası Seç", "", SUPPORTED_DATA_FILE_FILTER
        )
        if path:
            self._load_database(Path(path))

    def _action_load_sample_database(self) -> None:
        self._load_database(DEFAULT_SAMPLE_DATABASE)

    def _load_database(self, path: Path) -> None:
        try:
            self.database = ProductDatabase(path)
            self.database_path = path
        except ADRError as exc:
            logger.exception("Veritabanı yüklenemedi")
            QMessageBox.critical(self, "Hata", str(exc))
            return

        self._rebuild_checker()
        self._set_status(
            f"Veritabanı yüklendi: {path.name} ({self.database.total_records()} kayıt)"
        )
        self._refresh_dashboard()
        self.check_db_label.setText(
            f"<b>Veritabanı:</b> {path.name} — {self.database.total_records()} kayıt"
        )

    def _load_rule_engine(self, path: Path) -> None:
        try:
            self.rule_engine = SegregationRuleEngine(path)
            self.rule_file_path = path
        except ADRError as exc:
            logger.exception("Kural dosyası yüklenemedi")
            QMessageBox.critical(self, "Hata", str(exc))
            return

        self._rebuild_checker()
        if hasattr(self, "settings_rule_file_label"):
            self._refresh_settings_page()

    def _rebuild_checker(self) -> None:
        if self.database is not None and self.rule_engine is not None:
            self.checker = MixChecker(self.database, self.rule_engine)

    # ======================================================================
    # Eylemler: UN listesi
    # ======================================================================
    def _action_add_un_from_input(self) -> None:
        text = self.un_input.text().strip()
        self.un_input.clear()

        if not text:
            return

        if not is_valid_un(text):
            QMessageBox.warning(
                self, "Geçersiz UN Numarası", f"'{text}' geçerli bir UN numarası değil (4 hane)."
            )
            return

        if self.database is None:
            QMessageBox.information(
                self, "Veritabanı Yok", "Önce bir veritabanı yükleyin (Dosya > Veritabanı Yükle)."
            )
            return

        record = self.database.try_get_record(text)
        if record is None:
            reply = QMessageBox.question(
                self,
                "Bulunamadı",
                f"UN {normalize_un(text)} veritabanında bulunamadı. Yine de "
                "listeye eklensin mi? (Kontrol sırasında atlanacaktır.)",
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
            self._add_to_list(normalize_un(text), None)
        else:
            self._add_to_list(record.un_no, record)

    def _action_open_search_dialog(self) -> None:
        if self.database is None:
            QMessageBox.information(
                self, "Veritabanı Yok", "Önce bir veritabanı yükleyin (Dosya > Veritabanı Yükle)."
            )
            return

        dialog = SearchDialog(self.database, self)
        if dialog.exec():
            for record in dialog.selected_records:
                self._add_to_list(record.un_no, record)

    def _add_to_list(self, un_no: str, record: ProductRecord | None) -> None:
        if un_no in self.added_records:
            return

        if len(self.added_records) >= MAX_UN_ITEMS:
            QMessageBox.warning(
                self,
                "Sınır Aşıldı",
                f"En fazla {MAX_UN_ITEMS} kalem eklenebilir.",
            )
            return

        self.added_records[un_no] = record  # type: ignore[assignment]

        label = un_no
        if record is not None:
            label += f"  —  {record.display_name}"
            extras = []
            if record.labels:
                extras.append(", ".join(record.labels))
            if record.classification_code:
                extras.append(f"kod: {record.classification_code}")
            if record.compatibility_group:
                extras.append(f"uyum. grubu: {record.compatibility_group}")
            if extras:
                label += f"   [{' | '.join(extras)}]"
        else:
            label += "  —  (veritabanında bulunamadı)"

        item = QListWidgetItem(label)
        item.setData(Qt.ItemDataRole.UserRole, un_no)
        self.added_list.addItem(item)

    def _action_remove_selected(self) -> None:
        for item in self.added_list.selectedItems():
            un_no = item.data(Qt.ItemDataRole.UserRole)
            self.added_records.pop(un_no, None)
            self.added_list.takeItem(self.added_list.row(item))

    def _action_clear_list(self) -> None:
        self.added_records.clear()
        self.added_list.clear()
        self.results_model.set_results([])
        self.last_results = []
        self.last_missing = []
        self.results_summary_label.setText("")
        self.detail_panel.clear()

    # ======================================================================
    # Eylemler: Kontrol çalıştırma
    # ======================================================================
    def _action_run_check(self) -> None:
        if self.checker is None:
            QMessageBox.information(
                self, "Veritabanı Yok", "Önce bir veritabanı yükleyin (Dosya > Veritabanı Yükle)."
            )
            return

        un_list = list(self.added_records.keys())
        if len(un_list) < 2:
            QMessageBox.information(
                self, "Yetersiz Kalem", "Kontrol için en az 2 ürün eklemelisiniz."
            )
            return

        self._set_status("Kontrol ediliyor...")
        try:
            results, missing = self.checker.check_all(un_list)
        except ADRError as exc:
            logger.exception("Kontrol sırasında hata oluştu")
            QMessageBox.critical(self, "Hata", str(exc))
            self._set_status("Hata oluştu.")
            return

        self.last_results = results
        self.last_missing = missing
        self.results_model.set_results(results)
        self._select_first_result_row()
        self._update_results_summary()
        self._refresh_dashboard()

        if missing:
            QMessageBox.warning(
                self,
                "Bazı Kalemler Bulunamadı",
                "Şu UN numaraları veritabanında bulunamadığı için kontrol "
                "dışında tutuldu:\n" + ", ".join(missing),
            )

        self._set_status(f"{len(results)} kombinasyon kontrol edildi.")
        self._navigate_to(1)

    def _update_results_summary(self) -> None:
        counts: dict[str, int] = {}
        for r in self.last_results:
            counts[r.status] = counts.get(r.status, 0) + 1

        parts = [
            f"{STATUS_LABELS.get(status, status)}: {count}"
            for status, count in counts.items()
        ]
        summary = " | ".join(parts) if parts else "Sonuç yok."
        self.results_summary_label.setText(f"<b>Özet:</b> {summary}")
        self.reports_status_label.setText(
            f"Son kontrol: {len(self.last_results)} kombinasyon. {summary}"
        )

    def _on_result_selection_changed(self, selected, deselected) -> None:
        indexes = self.results_table.selectionModel().selectedRows()
        if not indexes:
            self.detail_panel.clear()
            return
        result = self.results_model.result_at(indexes[0].row())
        self.detail_panel.set_result(result, self.database)

    def _select_first_result_row(self) -> None:
        """İlk satırı otomatik seçer; böylece ayrıntı paneli ek bir tıklama
        olmadan anında ilk sonucu gösterir."""

        if self.results_model.rowCount() > 0:
            self.results_table.selectRow(0)
        else:
            self.detail_panel.clear()

    # ======================================================================
    # Eylemler: Dışa aktarım
    # ======================================================================
    def _action_export_excel(self) -> None:
        if not self.last_results:
            QMessageBox.information(self, "Sonuç Yok", "Önce bir kontrol çalıştırın.")
            return

        path, _ = QFileDialog.getSaveFileName(
            self, "Excel Olarak Kaydet", "adr_kontrol_raporu.xlsx", "Excel Dosyası (*.xlsx)"
        )
        if not path:
            return

        try:
            export_results_to_excel(self.last_results, path)
        except ADRError as exc:
            QMessageBox.critical(self, "Hata", str(exc))
            return

        self._set_status(f"Excel raporu kaydedildi: {path}")
        QMessageBox.information(self, "Başarılı", f"Excel raporu kaydedildi:\n{path}")

    def _action_export_pdf(self) -> None:
        if not self.last_results:
            QMessageBox.information(self, "Sonuç Yok", "Önce bir kontrol çalıştırın.")
            return

        path, _ = QFileDialog.getSaveFileName(
            self, "PDF Olarak Kaydet", "adr_kontrol_raporu.pdf", "PDF Dosyası (*.pdf)"
        )
        if not path:
            return

        try:
            export_results_to_pdf(
                self.last_results,
                path,
                prepared_by=self.report_author_input.text().strip(),
                company_name=self.report_company_input.text().strip(),
            )
        except ADRError as exc:
            QMessageBox.critical(self, "Hata", str(exc))
            return

        self._set_status(f"PDF raporu kaydedildi: {path}")
        QMessageBox.information(self, "Başarılı", f"PDF raporu kaydedildi:\n{path}")

    # ======================================================================
    # Eylemler: Proje kaydet/yükle
    # ======================================================================
    def _action_save_project(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Projeyi Kaydet", "proje.adrproj", SUPPORTED_PROJECT_FILE_FILTER
        )
        if not path:
            return

        try:
            save_project(
                path,
                list(self.added_records.keys()),
                self.last_results,
                database_path=str(self.database_path) if self.database_path else None,
                rule_file_path=str(self.rule_file_path),
            )
        except ADRError as exc:
            QMessageBox.critical(self, "Hata", str(exc))
            return

        self._set_status(f"Proje kaydedildi: {path}")

    def _action_open_project(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Proje Aç", "", SUPPORTED_PROJECT_FILE_FILTER
        )
        if not path:
            return

        try:
            data = load_project(path)
        except ADRError as exc:
            QMessageBox.critical(self, "Hata", str(exc))
            return

        if data["database_path"] and Path(data["database_path"]).exists():
            self._load_database(Path(data["database_path"]))

        if data["rule_file_path"]:
            rule_path = Path(data["rule_file_path"])
            if rule_path.exists() and rule_path != self.rule_file_path:
                self._load_rule_engine(rule_path)

        self._action_clear_list()
        for un_no in data["un_list"]:
            record = self.database.try_get_record(un_no) if self.database else None
            self._add_to_list(un_no, record)

        self.last_results = data["results"]
        self.results_model.set_results(self.last_results)
        self._select_first_result_row()
        self._update_results_summary()
        self._set_status(f"Proje açıldı: {path}")
        self._navigate_to(1)

    # ======================================================================
    # Eylemler: Kural dosyası / tema / yardım
    # ======================================================================
    def _action_change_rule_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Segregasyon Kural Dosyası Seç", "", "CSV Dosyası (*.csv)"
        )
        if path:
            self._load_rule_engine(Path(path))
            self._set_status(f"Kural dosyası değiştirildi: {path}")

    def _toggle_dark_theme(self, enabled: bool) -> None:
        self._dark_theme_enabled = enabled
        from PyQt6.QtWidgets import QApplication

        QApplication.instance().setStyleSheet(load_dark_stylesheet() if enabled else "")
        self.results_model.set_dark_mode(enabled)

    def _action_show_help(self) -> None:
        HelpDialog(self).exec()

    def _action_show_about(self) -> None:
        AboutDialog(self).exec()

    # ======================================================================
    # Yardımcılar
    # ======================================================================
    def _refresh_dashboard(self) -> None:
        if self.database is None:
            self.dashboard_db_label.setText(
                "<b>Veritabanı:</b> Henüz yüklenmedi. "
                "Dosya &gt; Veritabanı Yükle ile başlayın, ya da örnek veriyi deneyin."
            )
            self.check_db_label.setText("<b>Veritabanı:</b> Yüklenmedi")
        else:
            name = self.database_path.name if self.database_path else "?"
            self.dashboard_db_label.setText(
                f"<b>Veritabanı:</b> {name} — {self.database.total_records()} kayıt yüklü."
            )

        self.dashboard_items_label.setText(
            f"<b>Listeye eklenen ürün sayısı:</b> {len(self.added_records)}"
        )

        if self.last_results:
            self._update_results_summary()
            self.dashboard_summary_label.setText(
                f"<b>Son kontrol:</b> {len(self.last_results)} kombinasyon değerlendirildi."
            )
        else:
            self.dashboard_summary_label.setText(
                "<b>Son kontrol:</b> Henüz bir kontrol çalıştırılmadı."
            )

    def _set_status(self, message: str) -> None:
        self.statusBar().showMessage(message, 8000)
        logger.info(message)
