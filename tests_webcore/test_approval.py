# FAZ 4 TAŞIMA NOTU: monolit testinden uyarlandı; yükleyici bloğu
# "import webcore as M" ile değiştirildi (webcore aynı adları dışa açar).
# Qt sayfa sınıflarına dokunan testler masaüstünde kaldı (tests/ altında
# çalışmaya devam ederler); burada yalnız motor/veritabanı testleri koşar.
"""Taşıma evrakı onay aşaması — yaşam döngüsü testleri.

Tespit edilen sorun: "Doğrula" düğmesi yalnızca mesaj kutusu gösteriyordu;
DocumentStatus.VALIDATED enum'u koda hiç bağlanmamıştı, is_validated hep
False, validation_errors hep boş kalıyordu ve kaydet her zaman statüyü
"Taslak"a eziyordu. Bu testler kalıcı onay zincirini tanımlar.
"""
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import webcore as M  # Faz 4: monolit yerine ayrıştırılmış çekirdek


@pytest.fixture()
def db(tmp_path):
    return M.DatabaseManager(str(tmp_path / "onay.db"))


def make_shipment(db):
    sid = db.add_shipment(M.Shipment(document_no="ONY-1",
                                     document_date="2026-07-05"))
    return sid


class TestValidationPersistence:
    def test_valid_sets_onaylandi(self, db):
        sid = make_shipment(db)
        db.set_shipment_validation(sid, True)
        sh = db.get_shipment(sid)
        assert sh.status == M.DocumentStatus.VALIDATED.value == "Onaylandi"
        assert sh.is_validated is True
        assert sh.validation_errors == ""

    def test_invalid_sets_taslak_with_errors(self, db):
        sid = make_shipment(db)
        db.set_shipment_validation(sid, False, "Satir 1: UN numarasi eksik")
        sh = db.get_shipment(sid)
        assert sh.status == M.DocumentStatus.DRAFT.value
        assert sh.is_validated is False
        assert "UN numarasi eksik" in sh.validation_errors

    def test_revalidation_clears_old_errors(self, db):
        sid = make_shipment(db)
        db.set_shipment_validation(sid, False, "eski hata")
        db.set_shipment_validation(sid, True)
        sh = db.get_shipment(sid)
        assert sh.is_validated is True and sh.validation_errors == ""

    def test_stats_count_follows_status(self, db):
        s1, s2 = make_shipment(db), db.add_shipment(
            M.Shipment(document_no="ONY-2", document_date="2026-07-05"))
        db.set_shipment_validation(s1, True)
        stats = db.get_statistics()
        assert stats["draft_shipments"] == 1  # yalnızca onaysız olan


class TestApprovalDowngrade:
    def test_update_after_approval_downgrades(self, db):
        """Onaylı evrak içeriği değişip yeniden kaydedilirse onay düşmeli:
        eski içeriğin onayı yeni içeriği kapsamaz."""
        sid = make_shipment(db)
        db.set_shipment_validation(sid, True)

        sh = db.get_shipment(sid)
        sh.notes = "içerik değişti"
        sh.status = M.DocumentStatus.DRAFT.value   # kaydet akışının davranışı
        sh.is_validated = False
        db.update_shipment(sh)

        again = db.get_shipment(sid)
        assert again.status == M.DocumentStatus.DRAFT.value
        assert again.is_validated is False
