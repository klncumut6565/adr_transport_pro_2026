"""Masaüstü — Tablo A içe aktarımında 66 satırlık varyant kaybı.

Umut'un tespiti: Taşıma Evrakı sayfasının Taşınan Ürünler arama
kısmında UN numarasına göre arandığında yalnızca TEK seçenek
çıkıyordu — oysa örneğin UN1202 için 3, UN1950 için 12 seçenek
çıkması gerekiyordu.

Kök sebep: _upsert_chemical()'ın "bu kayıt zaten var mı" kontrolü
yalnızca (UN, sınıflandırma kodu, paketleme grubu) üçlüsüne
bakıyordu. Ama resmi Tablo A'da bu üçlü AYNI olup yalnızca özel
hüküm ile ayrışan GERÇEKTEN FARKLI satırlar var (ör. UN1133 F1 PG
II: 640C/640D varyantları) — bu satırlar birbirinin üzerine
yazılıyordu. Aynı sınıf hata web tarafında zaten düzeltilmişti
(webcore/db.py, tam satır imzası ile) ama masaüstüne hiç geri
taşınmamıştı. import_table_a_excel() artık web ile birebir aynı
tam-satır-imzası mantığını kullanıyor; ayrıca chemicals tablosundaki
kısıtlayıcı UNIQUE(un_number, classification_code, packing_group)
kısıtı da göçle kaldırıldı (aksi hâlde Python mantığı doğru olsa
bile veritabanı seviyesinde INSERT reddedilirdi).
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


@pytest.fixture()
def db():
    yol = os.path.join(tempfile.mkdtemp(), "test.db")
    return M.DatabaseManager(yol)


class TestTabloAVaryantKaybi:
    def test_toplam_kayit_sayisi_2939(self, db):
        n = db.import_table_a_excel(str(ROOT / "ADR_A_TABLOSU.xlsx"))
        assert db.count_chemicals() == 2939, (
            f"beklenen 2939, gelen {db.count_chemicals()} — "
            "640C/640D tarzı varyantlar hâlâ kayboluyor olabilir")

    def test_un1202_uc_varyasyon_doner(self, db):
        db.import_table_a_excel(str(ROOT / "ADR_A_TABLOSU.xlsx"))
        sonuc = db.search_chemicals("1202")
        assert len(sonuc) == 3, (
            f"UN1202 için 3 varyasyon beklenirdi, {len(sonuc)} geldi "
            "(Umut'un bildirdiği hata)")

    def test_un1950_on_iki_varyasyon_doner(self, db):
        db.import_table_a_excel(str(ROOT / "ADR_A_TABLOSU.xlsx"))
        sonuc = db.search_chemicals("1950")
        assert len(sonuc) == 12, (
            f"UN1950 için 12 varyasyon beklenirdi, {len(sonuc)} geldi")

    def test_yeniden_yukleme_idempotent(self, db):
        """Tablo A'yı iki kez yüklemek kopya oluşturmamalı."""
        n1 = db.import_table_a_excel(str(ROOT / "ADR_A_TABLOSU.xlsx"))
        n2 = db.import_table_a_excel(str(ROOT / "ADR_A_TABLOSU.xlsx"))
        assert n1 == 2939
        assert n2 == 0, "yeniden içe aktarma kopya satır oluşturuyor"
        assert db.count_chemicals() == 2939

    def test_chemicals_tablosunda_kisitlayici_unique_yok(self, db):
        """Şema göçünün gerçekten çalıştığının doğrudan kanıtı: tabloda
        artık (un, sınıflandırma, PG) üzerinde bir UNIQUE kısıtı OLMAMALI
        — aksi hâlde Python mantığı doğru olsa bile INSERT reddedilir."""
        db.import_table_a_excel(str(ROOT / "ADR_A_TABLOSU.xlsx"))
        conn = db._get_conn() if hasattr(db, "_get_conn") else db.conn
        cur = conn.cursor()
        sql = cur.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='chemicals'"
        ).fetchone()[0]
        assert "UNIQUE(un_number, classification_code, packing_group)" not in sql
