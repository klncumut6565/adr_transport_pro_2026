"""Sayfaların ortak yardımcıları."""
import streamlit as st

from webcore.session import get_db


def db():
    return get_db()


def kullanici():
    return st.session_state.get("user", {})


# ── Önbellekli listeler (performans) ────────────────────────────────
# DÜZELTME: firmalar/sürücüler/araçlar listeleri, kullanıcı bir dropdown'da
# seçim yaptığı HER SEFERİNDE (Streamlit'in doğası gereği her widget
# etkileşimi TÜM sayfa script'ini yeniden çalıştırır) veritabanından
# TEKRAR çekiliyordu — oysa bu listeler yalnızca biri Firmalar/Sürücüler/
# Araçlar sayfasından bir kayıt ekleyip/düzenleyip/silene kadar DEĞİŞMEZ.
# "Firma seçtiğimde neden hâlâ ağa gidiliyor, hiç gitmemesi lazım" tespiti
# doğruydu. st.cache_data ile önbelleğe alındı: seçim değişince artık
# VERİTABANINA HİÇ GİDİLMİYOR, bellekten anında okunuyor.
#
# GÜVENLİK NOTU: st.cache_data varsayılan olarak TÜM oturumlar arasında
# paylaşılan bir önbellektir. tenant_id'yi (alt çizgisiz, yani önbellek
# anahtarına DAHİL edilen) bir parametre olarak vermek ZORUNLUDUR — aksi
# hâlde bir kiracının firma listesi başka bir kiracıya sızabilirdi. `_db`
# parametresi (baştaki alt çizgi) Streamlit'e bu argümanı ÖNBELLEK
# ANAHTARINA KATMA, sadece çağırmak için kullan der (DB nesnesi zaten
# hashlenebilir değil).
@st.cache_data(ttl=60, show_spinner=False)
def _firmalar_onbellek(_db, tenant_id: int):
    return _db.get_companies()


@st.cache_data(ttl=60, show_spinner=False)
def _suruculer_onbellek(_db, tenant_id: int, active_only: bool = True):
    return _db.get_drivers(active_only=active_only)


@st.cache_data(ttl=60, show_spinner=False)
def _araclar_onbellek(_db, tenant_id: int, active_only: bool = True):
    return _db.get_vehicles(active_only=active_only)


@st.cache_data(ttl=300, show_spinner=False)
def _tablo_a_sayisi_onbellek(_db):
    # chemicals GLOBAL'dir (kiracıya özel değil — bkz. webcore/pg.py notu),
    # bu yüzden tenant_id parametresi yok; gerçekten herkes için ortak.
    return _db.count_chemicals()


def firmalar_listesi():
    d = db()
    return _firmalar_onbellek(d, d.tenant_id)


def suruculer_listesi(active_only: bool = True):
    d = db()
    return _suruculer_onbellek(d, d.tenant_id, active_only)


def araclar_listesi(active_only: bool = True):
    d = db()
    return _araclar_onbellek(d, d.tenant_id, active_only)


def tablo_a_sayisi():
    return _tablo_a_sayisi_onbellek(db())


def onbellek_temizle():
    """Bir firma/sürücü/araç eklendiğinde, düzenlendiğinde veya
    silindiğinde ÇAĞRILMALI — aksi hâlde değişiklik en fazla 60 saniye
    (TTL) boyunca diğer sayfalarda görünmez kalır."""
    _firmalar_onbellek.clear()
    _suruculer_onbellek.clear()
    _araclar_onbellek.clear()


def tablo_a_onbellek_temizle():
    _tablo_a_sayisi_onbellek.clear()


def kimyasal_etiket(c) -> str:
    """Bir Chemical kaydini secim listelerinde AYIRT EDICI sekilde gosterir.

    Resmi ADR Tablo A'da ayni UN numarasi + ayni ad ile birden fazla satir
    olabilir; bunlar siniflandirma kodu, paketleme grubu veya ozellikle ozel
    hukum (orn. 640C / 640D) ile ayrisir. Sadece 'UN{no} - {ad}' gostermek
    boyle durumlarda BIREBIR AYNI GORUNEN, farkli LQ/EQ/tunel/kategori
    tasiyan secenekleri kullanicidan gizler -- yanlis varyantin secilmesine
    yol acabilir. Bu yuzden sinif/PG/ozel hukum burada ayirt edici olarak
    eklenir."""
    ad = c.proper_shipping_name_tr or c.proper_shipping_name_en or ""
    parcalar = [f"UN{c.un_number} — {ad}"]
    sinif_pg = " / ".join(filter(None, [
        c.class_code,
        c.classification_code,
        f"PG {c.packing_group}" if c.packing_group else "",
    ]))
    if sinif_pg:
        parcalar.append(f"[{sinif_pg}]")
    if c.special_provisions:
        parcalar.append(f"ÖH: {c.special_provisions[:40]}")
    return " ".join(parcalar)
