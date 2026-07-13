"""Ayarlar — Faz 2c/3c: firma bilgileri (evrak anteti), logo, veri içe aktarma.

Yalnız 'admin' rolü erişir; diğer rollere bilgi mesajı gösterilir.
doc_company_* anahtarları taşıma evrakı şablonunun (webcore/transport_doc)
okuduğu ayarlarla birebir aynıdır.
"""
import base64
import tempfile
from pathlib import Path

import streamlit as st
from webcore.errors import turkce_hata_metni

from sayfalar._ortak import db, kullanici

st.title("⚙️ Ayarlar")

if kullanici().get("role") != "admin":
    st.info("Bu sayfa yalnızca yönetici (admin) rolüne açıktır.")
    st.stop()

d = db()

# ── Firma bilgileri (evrak anteti) ────────────────────────────────────
st.subheader("🏢 Firma Bilgileri (evrak antetinde görünür)")
with st.form("firma_bilgileri"):
    c1, c2 = st.columns(2)
    ad = c1.text_input("Firma adı", value=d.get_setting("doc_company_name") or "")
    tel = c2.text_input("Telefon", value=d.get_setting("doc_company_phone") or "")
    adres = st.text_input("Adres", value=d.get_setting("doc_company_address") or "")
    c3, c4 = st.columns(2)
    eposta = c3.text_input("E-posta", value=d.get_setting("doc_company_email") or "")
    site = c4.text_input("Web sitesi", value=d.get_setting("doc_company_website") or "")
    qr = st.checkbox("Evrakta doğrulama karekodu göster",
                     value=(d.get_setting("doc_show_qr") == "1"))
    if st.form_submit_button("💾 Firma bilgilerini kaydet", type="primary"):
        d.set_setting("doc_company_name", ad)
        d.set_setting("doc_company_phone", tel)
        d.set_setting("doc_company_address", adres)
        d.set_setting("doc_company_email", eposta)
        d.set_setting("doc_company_website", site)
        d.set_setting("doc_show_qr", "1" if qr else "0")
        d.set_setting("firma_adi", ad)  # emniyet planı raporu da kullanıyor
        st.success("Firma bilgileri kaydedildi.")

st.divider()

# ── Antet logosu ──────────────────────────────────────────────────────
st.subheader("🖼 Antet Logosu (PDF filigranı)")
mevcut = d.get_company_logo_b64()
col_l, col_r = st.columns([1, 2])
with col_l:
    if mevcut:
        try:
            st.image(base64.b64decode(mevcut), caption="Mevcut logo", width=180)
        except Exception:
            st.warning("Kayıtlı logo görüntülenemedi.")
        if st.button("🗑 Logoyu kaldır"):
            d.set_company_logo_b64("")
            st.rerun()
    else:
        st.caption("Kayıtlı logo yok — evraklar filigransız üretilir "
                   "(onaysızlarda TASLAK damgası yine basılır).")
with col_r:
    yukleme = st.file_uploader("PNG/JPG logo yükle (önerilen: şeffaf PNG)",
                               type=["png", "jpg", "jpeg"])
    if yukleme is not None:
        veri = yukleme.getvalue()
        if len(veri) > 2_000_000:
            st.error("Dosya 2 MB'den büyük; daha küçük bir logo yükleyin.")
        else:
            d.set_company_logo_b64(base64.b64encode(veri).decode())
            st.success("Logo kaydedildi.")
            st.rerun()

st.divider()

# ── ADR Tablo A içe aktarma ───────────────────────────────────────────
st.subheader("📥 ADR Tablo A İçe Aktarma")
st.caption(f"Tablo A uygulamayla birlikte **gömülü** gelir ve tüm firmalar "
           f"için ortaktır (herkes aynı resmi veriyi görür) — normal "
           f"kullanımda burayı hiç açmanıza gerek yoktur. Şu an "
           f"**{d.count_chemicals()}** kayıt yüklü. Bu bölüm yalnızca ADR "
           f"yönetmeliği güncellendiğinde yeni Tablo A dosyasıyla elle "
           f"güncelleme yapmak içindir.")
xlsx = st.file_uploader("ADR_A_TABLOSU.xlsx dosyasını seçin", type=["xlsx"],
                        key="tabloa")
if xlsx is not None and st.button("🚀 İçe aktarmayı başlat", type="primary"):
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
        f.write(xlsx.getvalue())
        yol = f.name
    try:
        with st.spinner("Tablo A içe aktarılıyor (birkaç saniye sürebilir)..."):
            n = d.import_table_a_excel(yol)
        st.success(f"{n} kayıt içe aktarıldı. Toplam: {d.count_chemicals()}")
    except Exception as exc:
        st.error(f"İçe aktarma hatası: {turkce_hata_metni(exc)}")
    finally:
        Path(yol).unlink(missing_ok=True)

with st.expander("⚠️ Tehlikeli bölge: kimyasal tablosunu boşalt"):
    st.warning("Bu işlem TÜM firmalar için ortak olan Tablo A kayıtlarını "
               "siler (yalnız bu firmaya özel değil). Sevkiyat ürünleri "
               "etkilenmez (kopya alanlar üründe saklıdır).")
    onay = st.text_input("Onay için 'SİL' yazın")
    if st.button("Kimyasal tablosunu boşalt", disabled=(onay != "SİL")):
        d.execute_update("DELETE FROM chemicals")
        st.success("Tablo boşaltıldı.")
        st.rerun()


st.divider()

# ── Firma Envanteri içe aktarma (ASUTEK vb. formatlar) ────────────────
st.subheader("📥 Firma Kimyasal Envanteri İçe Aktarma")
st.caption("Başlık satırı 'UN NUMARASI' hücresinden otomatik bulunur; "
           "eksik EQ kodları Tablo A'dan tamamlanır.")
env = st.file_uploader("Envanter Excel dosyasını seçin", type=["xlsx"],
                       key="envanter")
if env is not None and st.button("🚀 Envanteri içe aktar", type="primary",
                                 key="envanter_btn"):
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
        f.write(env.getvalue())
        yol = f.name
    try:
        with st.spinner("Envanter içe aktarılıyor..."):
            n = d.import_company_inventory_excel(yol)
        st.success(f"{n} envanter kaydı içe aktarıldı.")
    except Exception as exc:
        st.error(f"İçe aktarma hatası: {turkce_hata_metni(exc)}")
    finally:
        Path(yol).unlink(missing_ok=True)
