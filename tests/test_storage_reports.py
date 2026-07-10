"""Proje kaydet/aç (.adrproj) ve PDF raporu — zorlamalı testler.

Depolama ve raporlama, sahada veri kaybının/bozulmasının en sık yaşandığı
katmanlardır; bu yüzden mutlu yol kadar bozuk dosya senaryoları da test
edilir.
"""
import json

import pytest

from adr_mix_pro.exceptions import ExportError, ProjectFileError
from adr_mix_pro.reports.pdf_export import export_results_to_pdf
from adr_mix_pro.storage.project_io import load_project, save_project


@pytest.fixture()
def sample_results(checker):
    results, _ = checker.check_all(["1203", "1830", "0335", "2814"])
    assert results, "fikstür boş sonuç üretti"
    return results


# =========================================================================
# Proje dosyası: kaydet -> aç gidiş-dönüşü kayıpsız olmalı
# =========================================================================
class TestProjectRoundtrip:
    def test_full_roundtrip(self, tmp_path, sample_results):
        p = tmp_path / "sevkiyat_ğüş.adrproj"
        un_list = ["1203", "1830", "0335", "2814"]
        save_project(p, un_list, sample_results,
                     database_path="adr_database.json",
                     rule_file_path="resources/data/segregation_rules.csv")

        data = load_project(p)
        assert data["un_list"] == un_list
        assert len(data["results"]) == len(sample_results)

        # Alan alan kayıpsızlık: load_project sonuçları yeniden
        # PairCheckResult nesnelerine çevirir — statü, risk, Türkçe
        # açıklamalar ve notlar kayıpsız dönmeli.
        orig = {(r.un1, r.un2): r for r in sample_results}
        for rd in data["results"]:
            o = orig[(rd.un1, rd.un2)]
            assert rd.status == o.status
            assert rd.risk_score == o.risk_score
            assert rd.reason == o.reason
            assert rd.notes == o.notes

    def test_empty_project(self, tmp_path):
        p = tmp_path / "bos.adrproj"
        save_project(p, [], [])
        data = load_project(p)
        assert data["un_list"] == [] and data["results"] == []

    def test_unicode_path_and_content(self, tmp_path, sample_results):
        p = tmp_path / "İstanbul – ğüşöç çalışması.adrproj"
        save_project(p, ["1203"], sample_results)
        raw = p.read_text(encoding="utf-8")
        # ensure_ascii=False: Türkçe karakterler dosyada okunur kalmalı
        assert "ı" in raw or "İ" in raw or "ü" in raw


# =========================================================================
# Proje dosyası: bozuk/kötü niyetli girdiler net hata vermeli, ÇÖKMEMELİ
# =========================================================================
class TestProjectCorruption:
    def test_nonexistent_file(self, tmp_path):
        with pytest.raises(ProjectFileError):
            load_project(tmp_path / "yok.adrproj")

    def test_invalid_json(self, tmp_path):
        p = tmp_path / "bozuk.adrproj"
        p.write_text("{bu json değil", encoding="utf-8")
        with pytest.raises(ProjectFileError):
            load_project(p)

    def test_binary_garbage(self, tmp_path):
        p = tmp_path / "cop.adrproj"
        p.write_bytes(b"\x00\xff\xfe PK\x03\x04 rastgele")
        with pytest.raises(ProjectFileError):
            load_project(p)

    def test_truncated_file(self, tmp_path, sample_results):
        p = tmp_path / "yarim.adrproj"
        save_project(p, ["1203"], sample_results)
        blob = p.read_bytes()
        p.write_bytes(blob[: len(blob) // 2])  # yarıda kesilmiş kayıt
        with pytest.raises(ProjectFileError):
            load_project(p)

    @pytest.mark.skipif(
        __import__("os").geteuid() == 0,
        reason="root dosya izinlerini bypass eder; bu test normal kullanıcıda anlamlı")
    def test_readonly_dir_save_error(self, tmp_path):
        ro = tmp_path / "salt_okunur"
        ro.mkdir()
        ro.chmod(0o500)
        try:
            with pytest.raises(ProjectFileError):
                save_project(ro / "x.adrproj", ["1203"], [])
        finally:
            ro.chmod(0o700)


# =========================================================================
# PDF raporu
# =========================================================================
class TestPdfExport:
    def test_pdf_written_and_valid(self, tmp_path, sample_results):
        out = tmp_path / "rapor.pdf"
        export_results_to_pdf(sample_results, out)
        blob = out.read_bytes()
        assert blob[:5] == b"%PDF-"
        assert blob.rstrip().endswith(b"%%EOF")
        assert len(blob) > 2000

    def test_turkish_fonts_bundled(self):
        """resources/fonts eksikse rapor sessizce Helvetica'ya düşer ve
        Türkçe karakterler bozulur — fontlar pakette OLMALI."""
        from adr_mix_pro.config import FONT_BOLD_PATH, FONT_REGULAR_PATH
        assert FONT_REGULAR_PATH.exists(), FONT_REGULAR_PATH
        assert FONT_BOLD_PATH.exists(), FONT_BOLD_PATH

        from adr_mix_pro.reports import pdf_export
        pdf_export._register_fonts()
        assert pdf_export.FONT_NAME == "DejaVuSans"

    def test_empty_results_clear_error(self, tmp_path):
        with pytest.raises(ExportError):
            export_results_to_pdf([], tmp_path / "bos.pdf")

    def test_large_report_multipage(self, tmp_path, db, rule_engine):
        from adr_mix_pro.core.checker import MixChecker
        from tests.conftest import make_record
        for i in range(40):
            db._records_by_un[f"{6000+i}"] = make_record(
                f"{6000+i}", f"UZUN İSİMLİ TEST MADDESİ ĞÜŞİÖÇ NO {i} "
                "— ÇÖZELTİ, ALEVLENEBİLİR, BAŞKA ŞEKİLDE SINIFLANDIRILMAMIŞ")
        ck = MixChecker(db, rule_engine)
        results, _ = ck.check_all([f"{6000+i}" for i in range(40)])  # 780 ikili
        out = tmp_path / "buyuk.pdf"
        export_results_to_pdf(results, out)
        assert out.stat().st_size > 20_000

    def test_invalid_target_dir(self, tmp_path, sample_results):
        with pytest.raises(ExportError):
            export_results_to_pdf(sample_results, tmp_path / "yok" / "r.pdf")
