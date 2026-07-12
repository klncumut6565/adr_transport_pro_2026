"""Karışık yükleme entegrasyonu — kalıcı regresyon testleri.

Bu dosyadaki her test, geliştirme sırasında GERÇEKTEN yakalanmış bir hatayı
ya da mevzuat açısından kritik bir davranışı sabitler. Yeni bir hata
bulunduğunda buraya test eklenir; hiçbir test silinmez.

Çalıştırma (proje kökünden):
    python -m pytest tests/ -v
"""
import pytest

from adr_mix_pro.validators import is_valid_un, normalize_un


# =========================================================================
# BUG-1: "UN1830" öneki tanınmıyordu
# =========================================================================
class TestUnNormalization:
    @pytest.mark.parametrize("raw,expected", [
        ("UN1830", "1830"),
        ("un1830", "1830"),
        ("UN 1830", "1830"),
        ("  UN1090  ", "1090"),
        ("1090.0", "1090"),      # Excel float okuması
        ("12", "0012"),          # dosya yüklemede bilinçli dolgu
        ("ABC", "ABC"),          # sayı değilse dokunma
    ])
    def test_normalize(self, raw, expected):
        assert normalize_un(raw) == expected

    def test_un_prefix_resolves_in_checker(self, checker):
        results, missing = checker.check_all(["1203", "UN1830"])
        assert missing == []
        assert len(results) == 1

    # BUG-2: elle girişte "12" sessizce 0012'ye tamamlanıp YANLIŞ ürünle
    # eşleşiyordu. is_valid_un ham girişte 4 hane şartını korumalı.
    @pytest.mark.parametrize("raw,valid", [
        ("1203", True), ("12", False), ("120", False),
        ("12034", False), ("12a3", False), ("", False),
    ])
    def test_manual_input_strictness(self, raw, valid):
        assert is_valid_un(raw) is valid


# =========================================================================
# BUG-3: Sınıf 7 etiketleri (7A/7B/7C) kural tablosunda yoktu -> UNKNOWN
# =========================================================================
class TestClass7Labels:
    @pytest.mark.parametrize("label", ["7", "7A", "7B", "7C", "7E"])
    def test_class7_labels_have_rules(self, rule_engine, label):
        verdict = rule_engine.check(label, "3")
        assert verdict.status != "UNKNOWN", f"{label} için kural tanımsız"

    def test_radioactive_pair_not_unknown(self, checker):
        results, _ = checker.check_all(["2915", "3105"])   # 7A + 5.2
        assert results[0].status == "OK"

    def test_7a_vs_7b(self, checker):
        results, _ = checker.check_all(["2915", "3332"])
        assert results[0].status != "UNKNOWN"


# =========================================================================
# BUG-4: Adaptör null/bozuk veride çöküyordu
# (JSON tabanlı eski adaptörün (main.py/mix_integration.py, artık iptal)
#  robustluk testleri; SQL tabanlı ana program adaptörü için karşılığı
#  tests/test_mixload_ana_program.py::TestAdapterRobustness içindedir.)
# =========================================================================


# =========================================================================
# BUG-5: CV28'de statü doğru ama açıklama genel "izin verilir" metniydi
# =========================================================================
class TestFoodCaution:
    def test_cv28_status_and_reason(self, checker):
        results, _ = checker.check_all(["2814", "1203"])
        r = results[0]
        assert r.status == "FOOD_CAUTION"
        assert "CV28" in r.reason or "gıda" in r.reason.lower()
        assert "CV28" in r.adr_reference

    def test_cv28_does_not_override_forbidden(self, checker, db):
        # CV28'li madde + Sınıf 1: yasak öncelikli kalmalı
        db._records_by_un["2814"].cv_codes = "CV28"
        results, _ = checker.check_all(["2814", "0335"])
        assert results[0].status == "NO"


# =========================================================================
# Mevzuat çekirdeği: Sınıf 1 davranışları
# =========================================================================
class TestExplosives:
    def test_class1_vs_other_forbidden(self, checker):
        results, _ = checker.check_all(["0335", "1203"])
        assert results[0].status == "NO"
        assert results[0].risk_score >= 90

    def test_14s_exception(self, checker):
        results, _ = checker.check_all(["0012", "1203", "1830"])
        by = {(r.un1, r.un2): r.status for r in results}
        assert by[("1203", "1830")] == "OK"
        assert by[("0012", "1203")] in ("OK", "EXPLOSIVE_SPECIAL")
        assert all(s != "NO" for s in by.values())

    def test_class1_groups_use_7522(self, checker):
        results, _ = checker.check_all(["0081", "0336", "0335"])
        assert all(r.status == "EXPLOSIVE_SPECIAL" for r in results)
        assert all("7.5.2.2" in r.adr_reference for r in results)

    def test_same_group_11d_pair(self, checker):
        results, _ = checker.check_all(["0081", "0209"])
        assert results[0].status != "NO"


# =========================================================================
# Girdi hijyeni ve sınır durumlar
# =========================================================================
class TestInputHygiene:
    def test_duplicates_removed(self, checker):
        results, _ = checker.check_all(["1203", "1203", "1203", "1830"])
        assert len(results) == 1

    def test_empty_and_garbage(self, checker):
        results, missing = checker.check_all(["", "  ", "ABC", "1203"])
        assert results == []
        assert "ABC" in missing

    def test_single_item_no_pairs(self, checker):
        results, missing = checker.check_all(["1203"])
        assert results == [] and missing == []

    def test_empty_list(self, checker):
        results, missing = checker.check_all([])
        assert results == [] and missing == []

    def test_unknown_uns_reported(self, checker):
        _, missing = checker.check_all(["1203", "8888", "0000"])
        assert set(missing) == {"8888", "0000"}

    def test_record_without_labels_is_unknown_not_crash(self, checker):
        results, _ = checker.check_all(["9999", "1203"])
        assert results[0].status == "UNKNOWN"
