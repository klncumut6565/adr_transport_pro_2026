"""Masaüstü — eski sahte uyumsuzluk kontrolünün kaldırılması.

Web portu denetiminde bulunan bir hata: generate_adr_report() İÇİNDE
sabit, hayali bir sözlüğe dayanan (GERÇEK bir ADR referansı olmayan)
check_compatibility() çağrılıyordu; bu, hem canlı panelin metin
önizlemesinde (_update_preview) hem YAZDIRILAN belgede
(_build_print_html) gösteriliyordu. Aynı hata masaüstünde de vardı
(web'e satırı satırına taşındığı için) ve burada da düzeltildi:
_gercek_karisik_yukleme_kontrolu() adında yeni bir yardımcı, GERÇEK
motoru (AnaDbChemicalAdapter + MixChecker, zaten mevcuttu) her iki
gösterim noktasında da devreye sokuyor.
"""
import os
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import importlib.util
_spec = importlib.util.spec_from_file_location(
    "anaprog", str(ROOT / "adr_transport_pro_2026.py"))
M = importlib.util.module_from_spec(_spec)
sys.modules["anaprog"] = M
_spec.loader.exec_module(M)


@pytest.fixture(scope="module")
def db():
    yol = os.path.join(tempfile.mkdtemp(), "test.db")
    d = M.DatabaseManager(yol)
    d.import_table_a_excel(str(ROOT / "ADR_A_TABLOSU.xlsx"))
    return d


def _mk(**o):
    f = M.ShipmentItem.__dataclass_fields__
    return M.ShipmentItem(**{k: v for k, v in o.items() if k in f})


class TestEskiSahteKontrolKaldirildi:
    def test_generate_adr_report_sahte_mesaj_uretmiyor(self):
        items = [
            _mk(un_number="0081", proper_name="PATLAYICI", class_code="1",
               transport_category="1", net_quantity=30, unit="kg",
               tunnel_code="B", classification_code="1.1D"),
            _mk(un_number="1978", proper_name="PROPAN", class_code="2",
               transport_category="1", net_quantity=500, unit="kg",
               tunnel_code="B/D", classification_code="2A"),
        ]
        rapor = M.ADREngine.generate_adr_report(items, driver=None, vehicle=None)
        hata_metinleri = [m for _, m in rapor.errors]
        assert not any("UYUMSUZ:" in m for m in hata_metinleri)
        assert rapor.compatibility_errors == []

    def test_check_compatibility_metodu_hala_var_dormant(self):
        """Silinmedi — yalnızca otomatik çağrısı kaldırıldı."""
        assert hasattr(M.ADREngine, "check_compatibility")

    def test_gercek_motor_dogru_adr_referansi_uretir(self, db):
        items = [
            _mk(un_number="0081", proper_name="PATLAYICI", class_code="1",
               classification_code="1.1D", packing_group=""),
            _mk(un_number="1978", proper_name="PROPAN", class_code="2",
               classification_code="2A", packing_group=""),
        ]
        sonuc = M._gercek_karisik_yukleme_kontrolu(db, items)
        assert sonuc, "gerçek motor sonuç üretemedi"
        assert any("7.5.2.1" in s for s in sonuc)
        assert not any("UYUMSUZ:" in s for s in sonuc)

    def test_uyumlu_ciftte_bos_liste_doner(self, db):
        items = [
            _mk(un_number="1830", proper_name="SÜLFÜRİK ASİT", class_code="8",
               classification_code="C1", packing_group="II"),
            _mk(un_number="1824", proper_name="SODYUM HİDROKSİT", class_code="8",
               classification_code="C5", packing_group="II"),
        ]
        sonuc = M._gercek_karisik_yukleme_kontrolu(db, items)
        assert sonuc == []

    def test_tek_urunde_cokme_yerine_bos_liste(self, db):
        items = [_mk(un_number="1203", proper_name="BENZİN", class_code="3")]
        sonuc = M._gercek_karisik_yukleme_kontrolu(db, items)
        assert sonuc == []

    def test_hatali_veritabaninda_cokme_yerine_bos_liste(self):
        """db None/bozuk olsa bile yardımcı fonksiyon ÇÖKMEMELİ — evrak
        üretimini asla engellememeli."""
        items = [
            _mk(un_number="0081", proper_name="X", class_code="1"),
            _mk(un_number="1978", proper_name="Y", class_code="2"),
        ]
        sonuc = M._gercek_karisik_yukleme_kontrolu(None, items)
        assert sonuc == []
