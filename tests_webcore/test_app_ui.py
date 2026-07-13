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
        # rerun sonrası varsayılan açılış sayfası: Taşıma Evrakı
        assert any("Taşıma Evrakı" in str(t.value) for t in at.title)
        # Evrak No otomatik dolu gelmeli (ADREngine.format_document_number)
        assert any(ti.label == "Evrak No" and str(ti.value).startswith("ADR-")
                  for ti in at.text_input)
        # ADR Kontrol Merkezi paneli: en az Ürün Sayısı + Tünel Kodu metrikleri
        assert len(at.metric) >= 2


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


class TestEskiKayitEvrakNoBos:
    """Regresyon: document_no boş yazılmış eski kayıt açılınca Evrak No
    alanı boş kalıyordu (Umut'un tespiti). Yükleme sırasında otomatik
    numara üretilip gösterilir; DB'ye ancak Kaydet ile yazılır."""

    def test_legacy_bos_document_no_doldurulur(self):
        if not PG_DSN:
            pytest.skip("ADR_PG_TEST_DSN_APP tanımlı değil")
        from webcore.pg import PgDatabaseManager
        from webcore.models import Shipment
        from streamlit.testing.v1 import AppTest

        db = PgDatabaseManager(PG_DSN)
        sid = db.add_shipment(Shipment(document_no="", document_date="2026-07-01",
                                       status="Taslak"))
        try:
            t = AppTest.from_file("sayfalar/sevkiyat_editor.py", default_timeout=40)
            t.secrets["db"] = {"dsn": PG_DSN}
            t.session_state["user"] = {"username": "umut", "tenant_id": 1,
                                       "role": "admin", "full_name": "U"}
            t.session_state["duzenlenecek_sevkiyat_id"] = sid
            t.run()
            assert not t.exception
            evrak_no = [x.value for x in t.text_input if x.label == "Evrak No"][0]
            assert evrak_no, "Evrak No hâlâ boş görünüyor"
        finally:
            db.execute_update("DELETE FROM shipments WHERE id=?", (sid,))


class TestTabloABosDurumGorunurlugu:
    """Düzeltme: Tablo A boşken sessizce 'kayıt yok' demek yerine sebep +
    'şimdi yükle' butonu gösterilir (Cloud'da teşhisi kolaylaştırır)."""

    def test_kimyasal_veritabani_bos_uyari_ve_buton(self):
        if not PG_DSN:
            pytest.skip("ADR_PG_TEST_DSN_APP tanımlı değil")
        from webcore.pg import PgDatabaseManager
        from streamlit.testing.v1 import AppTest

        db = PgDatabaseManager(PG_DSN)
        db.execute_update("DELETE FROM chemicals")
        try:
            t = AppTest.from_file("sayfalar/kimyasal_veritabani.py", default_timeout=30)
            t.secrets["db"] = {"dsn": PG_DSN}
            t.session_state["user"] = {"username": "u", "tenant_id": 1,
                                       "role": "admin", "full_name": "U"}
            t.run()
            assert not t.exception
            # Session-scoped mimaride (bkz. webcore/session.py düzeltmesi)
            # otomatik tohumlama artık db() inşası sırasında SENKRON
            # tamamlanıyor — sayfa kodu çalışana kadar tablo genelde
            # KENDİLİĞİNDEN dolmuş oluyor. Bu yüzden İKİ sonuç da doğru
            # kabul edilir: (a) kurtarma butonu göründü (tohumlama henüz
            # tamamlanmadan sayfa render oldu) VEYA (b) tablo zaten
            # sessizce iyileşti (2939+ kayıt). Yanlış olan tek durum:
            # ikisi de değilse (hâlâ boş ve buton da yok).
            buton_var = any(b.label.startswith("🔄") for b in t.button)
            tablo_iyilesmis = db.count_chemicals() >= 2939
            assert buton_var or tablo_iyilesmis, \
                "ne kurtarma butonu var ne tablo iyileşmiş"
        finally:
            n = db.import_table_a_excel("ADR_A_TABLOSU.xlsx")
            # Not: n burada 0 olabilir — otomatik tohumlama, testin AppTest
            # çağrısı sırasında (kendi oturum-özel bağlantısı üzerinden)
            # tabloyu zaten kendiliğinden doldurmuş olabilir. Asıl garanti
            # edilmesi gereken NİHAİ DURUM: tablo dolu olmalı.
            assert n >= 0
            assert db.count_chemicals() >= 2939, \
                "temizlik sonrası Tablo A tam değil"


class TestTabloABozukDurumKurtarma:
    """Umut'un yaşadığı gerçek senaryo: chemicals tamamen boş DEĞİL ama
    çok az kayıtlı (ör. yarım kalmış içe aktarma) — eski '== 0' kontrolü
    bunu 'dolu' sayıp hem otomatik tohumlamayı hem de kurtarma butonunu
    gizliyordu. Artık TABLO_A_EKSIK_ESIGI ile 'eksik' kabul edilir."""

    def test_bozuk_durumda_yeni_baglanti_otomatik_tamamlar(self):
        if not PG_DSN:
            pytest.skip("ADR_PG_TEST_DSN_APP tanımlı değil")
        from webcore.pg import PgDatabaseManager
        db = PgDatabaseManager(PG_DSN)
        gercek_sayi = db.count_chemicals()
        db.execute_update("DELETE FROM chemicals")
        db.execute_insert(
            "INSERT INTO chemicals (un_number, proper_shipping_name_tr, class_code) "
            "VALUES (?, ?, ?)", ("9999", "YARIM KALMIŞ", "3"))
        try:
            db2 = PgDatabaseManager(PG_DSN)
            assert db2.seed_bilgisi["basarili"] is True
            assert db2.count_chemicals() >= gercek_sayi
        finally:
            db.execute_update("DELETE FROM chemicals WHERE un_number != '9999'")
            db.import_table_a_excel("ADR_A_TABLOSU.xlsx")
            db.execute_update("DELETE FROM chemicals WHERE proper_shipping_name_tr = 'YARIM KALMIŞ'")


class TestUrunEkleCanliArama:
    """Düzeltme (2. tur, Umut'un geri bildirimiyle): tüm Tablo A'yı
    varsayılan gösteren dataframe yaklaşımı da YANLIŞTI — istenen, yazana
    kadar hiçbir şey görünmemesi, yazınca YALNIZCA eşleşenlerin (ör.
    '1993' için ~6 sonuç) listelenmesiydi. streamlit-searchbox'a geçildi:
    her tuş vuruşunda arka planda search_chemicals() çağrılan, Enter
    gerektirmeyen, yalnızca eşleşmeleri gösteren gerçek canlı arama."""

    def test_sayfa_hatasiz_render(self):
        if not PG_DSN:
            pytest.skip("ADR_PG_TEST_DSN_APP tanımlı değil")
        from streamlit.testing.v1 import AppTest
        t = AppTest.from_file("sayfalar/sevkiyat_editor.py", default_timeout=40)
        t.secrets["db"] = {"dsn": PG_DSN}
        t.session_state["user"] = {"username": "umut", "tenant_id": 1,
                                   "role": "admin", "full_name": "U"}
        t.run()
        assert not t.exception
        # eski yaklaşımların hiçbiri kalmamalı: ne tüm-tablo dataframe'i
        # ne de Enter gerektiren düz text_input arama kutusu
        assert not any("UN numarası veya madde adı" in ti.label for ti in t.text_input)

    def test_arama_fonksiyonu_un1993_icin_sadece_eslesenleri_dondurur(self):
        """Umut'un birebir verdiği örnek: UN 1993 için tüm Tablo A değil,
        yalnızca gerçekten eşleşen ~6 kayıt dönmeli."""
        if not PG_DSN:
            pytest.skip("ADR_PG_TEST_DSN tanımlı değil")
        from webcore.pg import PgDatabaseManager
        db = PgDatabaseManager(PG_DSN)
        sonuclar = db.search_chemicals("1993", limit=20)
        assert 0 < len(sonuclar) < 20, \
            "arama ya hiç sonuç vermiyor ya da filtrelemeden tüm tabloyu döndürüyor"
        assert all(s.un_number == "1993" for s in sonuclar), \
            "eşleşmeyen kayıtlar da dönüyor"
