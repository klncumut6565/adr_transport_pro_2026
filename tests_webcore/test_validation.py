"""webcore.ADREngine — Doğrulama katmanı testleri (Faz 4).

Masaüstü tests/test_validation_ana_program.py'nin webcore karşılığı.
Evrak doğrulama, sahte "geçerli" sonucun en tehlikeli olduğu yerdir: sistem
"evrak hazır" derken zorunlu bir alan eksikse sorumluluk kullanıcıya kalır.
"""
from datetime import datetime, timedelta

import pytest

from webcore import ADREngine, ShipmentItem, Company, Driver, Vehicle


def good_item():
    return ShipmentItem(un_number="1203", proper_name="BENZİN", class_code="3",
                        net_quantity=100, packaging_count=2, unit="L",
                        packaging_type="Varil", transport_category="2")


# =========================================================================
# BUG: Gönderici/alıcı HİÇ seçilmemişse (None) doğrulama sessizce geçiyordu
# =========================================================================
class TestPartiesRequired:
    def test_missing_sender_is_error(self):
        r = ADREngine.validate_shipment([good_item()], sender=None,
                                        receiver=Company(name="Alıcı A.Ş."))
        assert any("onderici" in m for _, m in r.errors)
        assert r.is_valid is False

    def test_missing_receiver_is_error(self):
        r = ADREngine.validate_shipment([good_item()],
                                        sender=Company(name="Gönderen A.Ş."),
                                        receiver=None)
        assert any("lici" in m for _, m in r.errors)
        assert r.is_valid is False

    def test_both_present_ok(self):
        r = ADREngine.validate_shipment([good_item()],
                                        sender=Company(name="G A.Ş."),
                                        receiver=Company(name="A A.Ş."))
        assert not any("onderici" in m or "lici firma" in m for _, m in r.errors)


# =========================================================================
# BUG: Bozuk/boş tarihler sessizce geçiliyordu (SRC5, muayene, ADR uygunluk)
# =========================================================================
class TestSilentDates:
    def _base(self):
        return dict(items=[good_item()], sender=Company(name="G"),
                    receiver=Company(name="A"))

    def test_broken_src5_date_flagged(self):
        # 13. ay: hicbir formatta gecerli degil (31/12/2027 artik dogru okunur)
        d = Driver(full_name="X", src5_no="1234567890", src5_expiry="31/13/2027")
        r = ADREngine.validate_shipment(driver=d, **self._base())
        assert any("SRC5" in m and "okunamadi" in m
                   for lvl, m in r.errors + r.warnings)

    def test_broken_inspection_date_flagged(self):
        v = Vehicle(plate="34 ABC 123", inspection_expiry="bozuk")
        r = ADREngine.validate_shipment(vehicle=v, **self._base())
        assert any("muayene" in m.lower() and "okunamadi" in m
                   for lvl, m in r.errors + r.warnings)

    def test_empty_inspection_date_warns(self):
        v = Vehicle(plate="34 ABC 123", inspection_expiry="")
        r = ADREngine.validate_shipment(vehicle=v, **self._base())
        assert any("muayene" in m.lower() for lvl, m in r.warnings)

    def test_valid_dates_no_noise(self):
        future = (datetime.now() + timedelta(days=365)).strftime("%Y-%m-%d")
        d = Driver(full_name="X", src5_no="1234567890", src5_expiry=future)
        v = Vehicle(plate="34 ABC 123", inspection_expiry=future,
                    adr_compliance_expiry=future)
        r = ADREngine.validate_shipment(driver=d, vehicle=v, **self._base())
        assert not any("okunamadi" in m for _, m in r.errors + r.warnings)


# NOT: TestQuantityValidation / TestPlateValidation / TestEmailValidation
# sınıfları masaüstü tarafında da kaldırılmıştı (core/validation.py'deki
# InputValidator hiç kullanılmayan ölü koddu). Gerçekte kullanılan
# doğrulama mantığı (ADREngine.validate_shipment, parse_date_flexible)
# test kapsamında kalmaya devam ediyor.


# =========================================================================
# Esnek tarih ayrıştırma: Türk formatları anlaşılmalı, hesap doğru olmalı
# =========================================================================
class TestFlexibleDates:
    @pytest.mark.parametrize("raw", [
        "2027-12-31", "31.12.2027", "31/12/2027", "31-12-2027",
    ])
    def test_formats_parse_to_same_date(self, raw):
        d = ADREngine.parse_date_flexible(raw)
        assert d is not None and (d.year, d.month, d.day) == (2027, 12, 31)

    @pytest.mark.parametrize("raw", ["", None, "bozuk", "31/13/2027", "2027-13-40"])
    def test_garbage_returns_none(self, raw):
        assert ADREngine.parse_date_flexible(raw) is None

    def test_future_turkish_format_is_valid_not_expired(self):
        # 31/12/2027 GELECEKTE bir tarihtir: ne "okunamadı" ne "geçersiz"
        d = Driver(full_name="X", adr_certificate_no="TR-1",
                   adr_certificate_expiry="31/12/2027")
        report = ADREngine.generate_adr_report(
            [ShipmentItem(un_number="1203", proper_name="B", class_code="3",
                         net_quantity=2000, transport_category="3")],
            driver=d)
        msgs = [m for _, m in report.errors]
        assert not any("okunamadi" in m for m in msgs)
        assert not any("sertifikasi gecersiz" in m for m in msgs)

    def test_past_turkish_format_is_expired(self):
        d = Driver(full_name="X", adr_certificate_no="TR-1",
                   adr_certificate_expiry="15.03.2024")
        report = ADREngine.generate_adr_report(
            [ShipmentItem(un_number="1203", proper_name="B", class_code="3",
                         net_quantity=2000, transport_category="3")],
            driver=d)
        assert any("sertifikasi gecersiz" in m for _, m in report.errors)

    def test_ambiguity_note_day_first(self):
        # 05.07.2026 gibi iki yorumlu tarihlerde GG.AA.YYYY (Türk yorumu) esas
        d = ADREngine.parse_date_flexible("05.07.2026")
        assert (d.day, d.month) == (5, 7)
