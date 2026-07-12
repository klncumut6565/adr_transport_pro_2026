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
