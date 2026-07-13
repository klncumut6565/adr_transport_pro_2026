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


class TestKimyasalVeritabaniCanliArama:
    """Düzeltme: Kimyasal Veritabanı sayfası da Ürün Ekle ile aynı hataya
    sahipti — varsayılan olarak tüm Tablo A'yı (ilk 200 satır) listeliyordu.
    Umut'un tercihiyle aynı desene (streamlit-searchbox + detay kartı)
    geçirildi."""

    def test_baslangicta_tablo_gorunmuyor(self):
        if not PG_DSN:
            pytest.skip("ADR_PG_TEST_DSN_APP tanımlı değil")
        from streamlit.testing.v1 import AppTest
        t = AppTest.from_file("sayfalar/kimyasal_veritabani.py", default_timeout=40)
        t.secrets["db"] = {"dsn": PG_DSN}
        t.session_state["user"] = {"username": "u", "tenant_id": 1,
                                   "role": "admin", "full_name": "U"}
        t.run()
        assert not t.exception
        assert len(t.dataframe) == 0, \
            "sayfa hâlâ varsayılan olarak bir tablo gösteriyor"
        assert not any(ti.label.startswith("Ara (") for ti in t.text_input), \
            "eski text_input tabanlı arama hâlâ duruyor"


class TestSurucuFormuVeGizlilik:
    """Düzeltme: SRC5 belgesi artık sürücü form kaydında ZORUNLU DEĞİL
    (yalnızca Ad Soyad zorunlu). Ayrıca Firmalar/Sürücüler/Araçlar
    sayfalarında 'Yeni Ekle' formu tıklanmadıkça hiç render OLMAMALI."""

    def test_form_varsayilan_olarak_kapali(self):
        if not PG_DSN:
            pytest.skip("ADR_PG_TEST_DSN_APP tanımlı değil")
        from streamlit.testing.v1 import AppTest
        for sayfa in ("sayfalar/suruculer.py", "sayfalar/firmalar.py",
                     "sayfalar/arac.py"):
            t = AppTest.from_file(sayfa, default_timeout=30)
            t.secrets["db"] = {"dsn": PG_DSN}
            t.session_state["user"] = {"username": "u", "tenant_id": 1,
                                       "role": "admin", "full_name": "U"}
            t.run()
            assert not t.exception, f"{sayfa}: {[str(e.value) for e in t.exception]}"
            assert len(t.text_input) <= 1, \
                f"{sayfa}: form varsayılan olarak açık görünüyor (yer kaplıyor)"

    def test_src5_olmadan_surucu_kaydedilebilir(self):
        if not PG_DSN:
            pytest.skip("ADR_PG_TEST_DSN_APP tanımlı değil")
        import uuid
        from streamlit.testing.v1 import AppTest
        from webcore.pg import PgDatabaseManager

        benzersiz_tc = uuid.uuid4().hex[:11]
        t = AppTest.from_file("sayfalar/suruculer.py", default_timeout=30)
        t.secrets["db"] = {"dsn": PG_DSN}
        t.session_state["user"] = {"username": "u", "tenant_id": 1,
                                   "role": "admin", "full_name": "U"}
        t.run()
        yeni_btn = [b for b in t.button if "Yeni Sürücü" in b.label]
        assert yeni_btn
        yeni_btn[0].click().run()
        # form açıldı, Ad Soyad + benzersiz TC doldur, SRC5'i BOŞ bırak
        ad_alani = [ti for ti in t.text_input if ti.label == "Ad Soyad"][0]
        ad_alani.set_value("SRC5SIZ TEST SÜRÜCÜ")
        tc_alani = [ti for ti in t.text_input if ti.label == "TC No"][0]
        tc_alani.set_value(benzersiz_tc)
        kaydet_btn = [b for b in t.button if "Kaydet" in b.label][0]
        try:
            kaydet_btn.click().run()
            assert not t.exception
            assert not any("SRC5 belgesi zorunlu" in str(e.value) for e in t.error), \
                "SRC5 hâlâ zorunlu tutuluyor"
            assert any("eklendi" in str(s.value).lower() for s in t.success), \
                "sürücü SRC5 olmadan kaydedilemedi"
        finally:
            PgDatabaseManager(PG_DSN).execute_update(
                "DELETE FROM drivers WHERE tc_no = ?", (benzersiz_tc,))


class TestSayfaGecisindeFormKapaniyor:
    """GERÇEK KÖK SEBEP: 'Yeni Ekle' formunun açık/kapalı durumu
    st.session_state'te tutulur — bu OTURUM boyunca kalıcıdır. Form
    açılıp kaydedilmeden/iptal edilmeden BAŞKA bir sayfaya geçilirse,
    sayfaya geri dönüldüğünde form hâlâ AÇIK görünüp yer kaplıyordu
    ('Sürücüler menüsünde hâlâ gözüküyor' şikâyetinin asıl sebebi —
    önceki tur yalnızca 'ilk ziyarette varsayılan kapalı' durumunu test
    etmişti, 'başka sayfadan dönüşte kapanma' senaryosunu değil).
    sayfalar._ortak.sayfaya_taze_girildi() ile düzeltildi."""

    def test_form_acikken_baska_sayfaya_gidip_geri_donunce_kapanir(self):
        if not PG_DSN:
            pytest.skip("ADR_PG_TEST_DSN_APP tanımlı değil")
        from streamlit.testing.v1 import AppTest

        def al(ss, k, v=None):
            try:
                return ss[k]
            except Exception:
                return v

        t1 = AppTest.from_file("sayfalar/suruculer.py", default_timeout=30)
        t1.secrets["db"] = {"dsn": PG_DSN}
        t1.session_state["user"] = {"username": "u", "tenant_id": 1,
                                    "role": "admin", "full_name": "U"}
        t1.run()
        btn = [b for b in t1.button if "Yeni Sürücü" in b.label][0]
        btn.click().run()
        assert al(t1.session_state, "surucu_form_ac") is True, \
            "buton tıklamasıyla form açılmalı"

        durum = dict(t1.session_state.filtered_state)
        t2 = AppTest.from_file("sayfalar/firmalar.py", default_timeout=30)
        t2.secrets["db"] = {"dsn": PG_DSN}
        for k, v in durum.items():
            t2.session_state[k] = v
        t2.run()  # başka sayfaya "geçiş"

        durum2 = dict(t2.session_state.filtered_state)
        t3 = AppTest.from_file("sayfalar/suruculer.py", default_timeout=30)
        t3.secrets["db"] = {"dsn": PG_DSN}
        for k, v in durum2.items():
            t3.session_state[k] = v
        t3.run()  # Sürücüler'e geri dönüş
        assert al(t3.session_state, "surucu_form_ac") is False, \
            "sayfaya geri dönünce form hâlâ açık görünüyor (yer kaplıyor)"
        assert len(t3.text_input) <= 1, \
            "form kapalı olmasına rağmen alanları hâlâ render ediliyor"

    def test_ayni_sayfada_kalindiginda_form_acik_kalir(self):
        """Regresyonu önlemek için ters kontrol: KULLANICI AYNI sayfada
        kalıp form içinde bir alanla etkileşime girerse (ör. metin
        yazması) form KAPANMAMALI — yalnızca sayfa DEĞİŞİNCE kapanmalı."""
        if not PG_DSN:
            pytest.skip("ADR_PG_TEST_DSN_APP tanımlı değil")
        from streamlit.testing.v1 import AppTest

        def al(ss, k, v=None):
            try:
                return ss[k]
            except Exception:
                return v

        t = AppTest.from_file("sayfalar/suruculer.py", default_timeout=30)
        t.secrets["db"] = {"dsn": PG_DSN}
        t.session_state["user"] = {"username": "u", "tenant_id": 1,
                                   "role": "admin", "full_name": "U"}
        t.run()
        btn = [b for b in t.button if "Yeni Sürücü" in b.label][0]
        btn.click().run()
        assert al(t.session_state, "surucu_form_ac") is True

        # AYNI sayfada bir alanla etkileşim (ikinci bir rerun, farklı sayfa DEĞİL)
        ad_alani = [ti for ti in t.text_input if ti.label == "Ad Soyad"][0]
        ad_alani.set_value("DEVAM EDEN GİRİŞ").run()
        assert al(t.session_state, "surucu_form_ac") is True, \
            "aynı sayfada kalırken form yanlışlıkla kapandı"


class TestKalemDuzenleme:
    """Düzeltme: Taşınan Ürünler listesindeki kalemler yalnızca
    silinebiliyordu, düzenlenemiyordu (Umut'un talebi). ✏️ Düzenle
    butonu eklendi — ambalaj türü/adedi, net miktar, birim, LQ/EQ
    yerinde güncellenebiliyor (kimyasal/UN/sınıf değiştirilemez,
    o değişecekse silip doğru kimyasalla yeniden eklenir)."""

    def test_kalem_yerinde_guncellenir(self):
        if not PG_DSN:
            pytest.skip("ADR_PG_TEST_DSN_APP tanımlı değil")
        from streamlit.testing.v1 import AppTest

        def al(ss, k, v=None):
            try:
                return ss[k]
            except Exception:
                return v

        t = AppTest.from_file("sayfalar/sevkiyat_editor.py", default_timeout=40)
        t.secrets["db"] = {"dsn": PG_DSN}
        t.session_state["user"] = {"username": "umut", "tenant_id": 1,
                                   "role": "admin", "full_name": "U"}
        t.run()
        t.session_state["editor_kalemler"] = [dict(
            id=None, shipment_id=None, chemical_id=1, un_number="1203",
            proper_name="BENZİN", class_code="3", packing_group="II",
            packaging_type="Varil", packaging_count=4, net_quantity=200.0,
            gross_quantity=200.0, unit="lt", is_lq=False, is_eq=False,
            lq_max_per_package=0.0, eq_max_per_package=0.0, notes="",
            tunnel_code="D/E", segregation_group="", classification_code="F1",
            transport_category="2", special_provisions="")]
        t.run()
        assert not t.exception

        duz_btn = [b for b in t.button if b.key == "kalem_duz_0"]
        assert duz_btn, "Düzenle butonu bulunamadı"
        duz_btn[0].click().run()
        assert al(t.session_state, "kalem_duzenle_i") == 0

        [ni for ni in t.number_input if ni.key == "duz_paket_adet_0"][0].set_value(9)
        [ni for ni in t.number_input if ni.key == "duz_net_miktar_0"][0].set_value(450.0)
        [cb for cb in t.checkbox if cb.key == "duz_lq_0"][0].set_value(True)
        [b for b in t.button if b.key == "duz_kaydet_0"][0].click().run()

        assert not t.exception
        kalem = al(t.session_state, "editor_kalemler")[0]
        assert kalem["packaging_count"] == 9
        assert kalem["net_quantity"] == 450.0
        assert kalem["is_lq"] is True
        assert kalem["un_number"] == "1203", "kimyasal/UN değişmemeli"
        assert al(t.session_state, "kalem_duzenle_i") is None, \
            "kayıt sonrası düzenleme modu kapanmalı"

    def test_vazgec_degisiklik_yapmaz(self):
        if not PG_DSN:
            pytest.skip("ADR_PG_TEST_DSN_APP tanımlı değil")
        from streamlit.testing.v1 import AppTest

        def al(ss, k, v=None):
            try:
                return ss[k]
            except Exception:
                return v

        t = AppTest.from_file("sayfalar/sevkiyat_editor.py", default_timeout=40)
        t.secrets["db"] = {"dsn": PG_DSN}
        t.session_state["user"] = {"username": "umut", "tenant_id": 1,
                                   "role": "admin", "full_name": "U"}
        t.run()
        t.session_state["editor_kalemler"] = [dict(
            id=None, shipment_id=None, chemical_id=1, un_number="1203",
            proper_name="BENZİN", class_code="3", packing_group="II",
            packaging_type="Varil", packaging_count=4, net_quantity=200.0,
            gross_quantity=200.0, unit="lt", is_lq=False, is_eq=False,
            lq_max_per_package=0.0, eq_max_per_package=0.0, notes="",
            tunnel_code="D/E", segregation_group="", classification_code="F1",
            transport_category="2", special_provisions="")]
        t.run()
        [b for b in t.button if b.key == "kalem_duz_0"][0].click().run()
        [ni for ni in t.number_input if ni.key == "duz_paket_adet_0"][0].set_value(99)
        [b for b in t.button if b.key == "duz_vazgec_0"][0].click().run()

        kalem = al(t.session_state, "editor_kalemler")[0]
        assert kalem["packaging_count"] == 4, "Vazgeç'e rağmen değişiklik uygulanmış"
        assert al(t.session_state, "kalem_duzenle_i") is None




class TestSurucuADRAlanlariTamKaldirildi:
    """Düzeltme (2. tur, tam kaldırma): Umut ilk turda yalnızca form
    alanının kaldırılıp verinin korunmasını istemişti; netleştirdi —
    bu alanlar sürücüyle hiç ilgisi olmayan, komple silinmesi gereken
    alanlarmış. adr_certificate_no/adr_certificate_expiry artık Driver
    modelinde YOK, formda YOK, mevzuat motorunda YOK, sürücü listesinde
    YOK."""

    def test_form_adr_alanlari_gostermiyor(self):
        if not PG_DSN:
            pytest.skip("ADR_PG_TEST_DSN_APP tanımlı değil")
        from streamlit.testing.v1 import AppTest
        t = AppTest.from_file("sayfalar/suruculer.py", default_timeout=30)
        t.secrets["db"] = {"dsn": PG_DSN}
        t.session_state["user"] = {"username": "u", "tenant_id": 1,
                                   "role": "admin", "full_name": "U"}
        t.run()
        btn = [b for b in t.button if "Yeni Sürücü" in b.label][0]
        btn.click().run()
        assert not any("ADR Belge" in ti.label or "ADR Bitiş" in ti.label
                       for ti in t.text_input), "ADR alanları hâlâ formda"

    def test_driver_modelinde_alan_yok(self):
        from webcore.models import Driver
        assert not hasattr(Driver(), "adr_certificate_no")
        assert not hasattr(Driver(), "adr_certificate_expiry")

    def test_surucu_ekle_ve_liste_calisir(self):
        """Alan tamamen kalktıktan sonra ekleme/listeleme akışı sorunsuz
        çalışmaya devam etmeli."""
        if not PG_DSN:
            pytest.skip("ADR_PG_TEST_DSN tanımlı değil")
        from webcore.pg import PgDatabaseManager
        from webcore.models import Driver

        db = PgDatabaseManager(PG_DSN)
        db.execute_update("DELETE FROM drivers WHERE tc_no = '55555555552'")
        try:
            did = db.add_driver(Driver(full_name="TAM KALDIRMA TESTİ",
                                       tc_no="55555555552", src5_no="SRC5-X"))
            surucu = db.get_driver(did)
            assert surucu.full_name == "TAM KALDIRMA TESTİ"
            assert surucu.src5_no == "SRC5-X"
            liste = db.get_drivers(active_only=False)
            assert any(s.id == did for s in liste)
        finally:
            db.execute_update("DELETE FROM drivers WHERE tc_no = '55555555552'")


class TestKontrolMerkeziMasaustuEslesme:
    """Düzeltme: web'deki ADR Kontrol Merkezi paneli, masaüstünün
    kullandığı TEK gerçek kaynak fonksiyona (generate_adr_report)
    bağlandı. Önceden parça parça (calculate_1136_points +
    calculate_tunnel_restriction + validate_shipment) çağrılıyordu; bu
    yüzden 'Yazılı Talimat' ve 'Muafiyet' göstergeleri hiç yoktu, info
    seviyeli mesajlar da sessizce kayboluyordu."""

    def test_yazili_talimat_ve_muafiyet_gorunur(self):
        if not PG_DSN:
            pytest.skip("ADR_PG_TEST_DSN_APP tanımlı değil")
        from streamlit.testing.v1 import AppTest
        t = AppTest.from_file("sayfalar/sevkiyat_editor.py", default_timeout=40)
        t.secrets["db"] = {"dsn": PG_DSN}
        t.session_state["user"] = {"username": "umut", "tenant_id": 1,
                                   "role": "admin", "full_name": "U"}
        t.run()
        # Sınıf 1 (patlayıcı) -> yazılı talimat zorunlu senaryosu
        t.session_state["editor_kalemler"] = [dict(
            id=None, shipment_id=None, chemical_id=1, un_number="0081",
            proper_name="PATLAYICI", class_code="1", packing_group="",
            packaging_type="Kutu", packaging_count=5, net_quantity=30.0,
            gross_quantity=30.0, unit="kg", is_lq=False, is_eq=False,
            lq_max_per_package=0.0, eq_max_per_package=0.0, notes="",
            tunnel_code="B", segregation_group="", classification_code="1.1D",
            transport_category="1", special_provisions="")]
        t.run()
        assert not t.exception
        metin = " | ".join(str(x.value) for x in
                           (list(t.error) + list(t.success) + list(t.warning) + list(t.caption)))
        assert "Yazılı Talimat" in metin, "Yazılı Talimat göstergesi eksik"
        assert "Muafiyet" in metin, "Muafiyet göstergesi eksik"

    def test_info_mesajlari_kaybolmuyor(self):
        """SRC5 belgeli bir sürücü seçilince rapor.info listesindeki
        onay mesajı ('SRC5 belgesi: X' gibi) artık görünmeli."""
        if not PG_DSN:
            pytest.skip("ADR_PG_TEST_DSN_APP tanımlı değil")
        from webcore.pg import PgDatabaseManager
        from webcore.models import Driver
        from webcore.engines import ADREngine
        from webcore.models import ShipmentItem

        db = PgDatabaseManager(PG_DSN)
        d = Driver(full_name="Test", src5_no="SRC5-BILGI-TEST")
        f = ShipmentItem.__dataclass_fields__
        mk = lambda **o: ShipmentItem(**{k: v for k, v in o.items() if k in f})
        # Sınıf 1 (patlayıcı) -> driver_adr_required dalı tetiklenir ->
        # SRC5 kontrolü (ve info mesajı) bu dalın İÇİNDE hesaplanır.
        items = [mk(un_number="0081", proper_name="PATLAYICI", class_code="1",
                    transport_category="1", net_quantity=30, unit="kg",
                    tunnel_code="B")]
        rapor = ADREngine.generate_adr_report(items, driver=d)
        info_mesajlari = [m for _, m in rapor.info]
        assert any("SRC5" in m for m in info_mesajlari), \
            "SRC5 onay mesajı rapor.info'da yok — panel bunu göstermemeli demek değil"


class TestDBUlasilamadiUyarisiPasif:
    """Düzeltme (Umut'un talebi): 'Veritabanına şu an ulaşılamıyor'
    uyarısı PASİFE ALINDI (silinmedi — DB_ULASILAMADI_UYARISI_GOSTER
    bayrağı ile geri açılabilir). KRİTİK: bu bayrak yalnızca UYARI
    METNİNİ gizler; alttaki SELECT 1 ping'i HER ZAMAN çalışmaya devam
    eder (Faz 5/6 keep-alive mekanizmasının veritabanı ayağı — bozulmamalı)."""

    def test_db_erisilemezken_uyari_gosterilmiyor(self):
        from streamlit.testing.v1 import AppTest
        t = AppTest.from_file("app.py", default_timeout=30)
        t.secrets["db"] = {"dsn": "postgresql://yanlis:sifre@olmayan-host:5432/yok"}
        t.run()
        assert not t.exception
        assert len(t.warning) == 0, "uyarı pasife alınmasına rağmen görünüyor"
        assert any(ti.label == "Kullanıcı adı" for ti in t.text_input), \
            "giriş formu DB hatasına rağmen gösterilmeye devam etmeli"

    def test_bayrak_kapali_ve_kolayca_acilabilir(self):
        import app
        assert app.DB_ULASILAMADI_UYARISI_GOSTER is False
        # bayrağın varlığı, geri açmanın tek satırlık bir değişiklik
        # olduğunun (kod silinmediğinin) kanıtıdır.
