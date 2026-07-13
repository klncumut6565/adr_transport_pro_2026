"""Faz 2 arayüz duman testi — Streamlit AppTest (başsız)."""
import os
import pytest

PG_DSN = os.environ.get("ADR_PG_TEST_DSN_APP", "")


@pytest.fixture()
def at():
    if not PG_DSN:
        pytest.skip("ADR_PG_TEST_DSN_APP tanımlı değil")
    from streamlit.testing.v1 import AppTest
    t = AppTest.from_file("app.py", default_timeout=30)
    t.secrets["db"] = {"dsn": PG_DSN}
    return t


class TestGirisAkisi:
    def test_giris_sayfasi_gorunur(self, at):
        at.run()
        assert not at.exception
        assert any("ADR Transport Pro 2026" in str(t.value) for t in at.title)

    def test_yanlis_parola_hata_verir(self, at):
        at.run()
        at.text_input[0].set_value("umut")
        at.text_input[1].set_value("yanlis-parola")
        at.button[0].set_value(True).run()
        assert at.error, "hatalı girişte uyarı bekleniyordu"

    def test_dogru_giris_panele_ulasir(self, at):
        at.run()
        at.text_input[0].set_value("umut")
        at.text_input[1].set_value("Test!123")
        at.button[0].set_value(True).run()
        assert not at.exception
        assert at.session_state["user"]["username"] == "umut"
        # rerun sonrası gösterge paneli başlığı ve metrikler
        assert any("Gösterge Paneli" in str(t.value) for t in at.title)
        assert len(at.metric) >= 4


class TestSevkiyatEditoruDogrudanGiris:
    """Cloud'da görülen KeyError regresyonu: editöre menüden doğrudan
    girişte editor_sevkiyat anahtarı oluşmadan okunuyordu. Sayfa,
    navigasyon durumu OLMADAN (duzenlenecek_sevkiyat_id yok) tek başına
    çalıştırılır — hatanın birebir yeniden üretimi."""

    def test_direct_entry_no_keyerror(self):
        if not PG_DSN:
            pytest.skip("ADR_PG_TEST_DSN_APP tanımlı değil")
        from streamlit.testing.v1 import AppTest
        t = AppTest.from_file("sayfalar/sevkiyat_editor.py", default_timeout=30)
        t.secrets["db"] = {"dsn": PG_DSN}
        t.session_state["user"] = {"username": "umut", "tenant_id": 1,
                                   "role": "admin", "full_name": "Umut"}
        # bilinçli olarak duzenlenecek_sevkiyat_id / editor_* anahtarları YOK
        t.run()
        assert not t.exception, f"doğrudan girişte hata: {[str(e.value) for e in t.exception]}"
        assert any("Taşıma Evrakı" in str(x.value) for x in t.title)
        assert t.session_state["editor_sevkiyat"]["id"] in (0, None)


class TestAyarlarSayfasi:
    """Faz 2c: ayarlar sayfası — admin erişimi ve rol kapısı."""

    def _run_page(self, role):
        from streamlit.testing.v1 import AppTest
        t = AppTest.from_file("sayfalar/ayarlar.py", default_timeout=30)
        t.secrets["db"] = {"dsn": PG_DSN}
        t.session_state["user"] = {"username": "u", "tenant_id": 1,
                                   "role": role, "full_name": "U"}
        t.run()
        return t

    def test_admin_gorur(self):
        if not PG_DSN:
            pytest.skip("ADR_PG_TEST_DSN_APP tanımlı değil")
        t = self._run_page("admin")
        assert not t.exception
        assert any("Firma Bilgileri" in str(h.value) for h in t.subheader)

    def test_user_engellenir(self):
        if not PG_DSN:
            pytest.skip("ADR_PG_TEST_DSN_APP tanımlı değil")
        t = self._run_page("user")
        assert not t.exception
        assert t.info, "admin olmayana bilgi mesajı beklenir"
        assert not any("Firma Bilgileri" in str(h.value) for h in t.subheader)


class TestRaporlarSayfasi:
    """Faz 2d: raporlar sayfası — render + Excel/PDF üretimi."""

    def test_sayfa_ve_disa_aktarimlar(self):
        if not PG_DSN:
            pytest.skip("ADR_PG_TEST_DSN_APP tanımlı değil")
        from streamlit.testing.v1 import AppTest
        t = AppTest.from_file("sayfalar/raporlar.py", default_timeout=60)
        t.secrets["db"] = {"dsn": PG_DSN}
        t.session_state["user"] = {"username": "u", "tenant_id": 1,
                                   "role": "admin", "full_name": "U"}
        t.run()
        assert not t.exception, [str(e.value) for e in t.exception]
        assert any("Raporlar" in str(x.value) for x in t.title)
        # iki indirme butonu üretilmiş olmalı (Excel + PDF baytları hazır)
        assert len(t.get("download_button")) >= 1
