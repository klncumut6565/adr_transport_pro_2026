"""ADR Transport Pro 2026 — Web (Streamlit) girişi. Faz 2 iskeleti.

Çalıştırma (yerel):   streamlit run app.py
Bağlantı dizesi:      .streamlit/secrets.toml → [db] dsn = "postgresql://..."
                      (Streamlit Cloud'da aynı anahtar Secrets ekranına yazılır)

Akış: giriş sayfası → AuthManager.login() → tenant_id →
PgDatabaseManager.set_tenant() → RLS tüm veriyi kiracıya kilitler →
st.navigation ile sayfalar.
"""

from __future__ import annotations

import streamlit as st

from webcore.session import get_db, get_auth

st.set_page_config(
    page_title="ADR Transport Pro 2026",
    page_icon="🚚",
    layout="wide",
)


def _login_page():
    st.title("🚚 ADR Transport Pro 2026")
    st.caption("Tehlikeli madde taşımacılığı yönetim sistemi")

    # Hafif veritabanı dokunuşu: giriş ekranının HER yüklenişi (keep-alive
    # ping'i dahil) Supabase'e SELECT 1 düşürür; böylece tek GitHub Actions
    # ping'i hem Streamlit uykusunu hem Supabase'in 7 gün duraklatma
    # sayacını birlikte sıfırlar. Veritabanı geçici olarak erişilemezse
    # giriş formu yine de gösterilir.
    try:
        get_db().execute_one("SELECT 1 AS ping")
    except Exception:
        st.warning("Veritabanına şu an ulaşılamıyor; giriş geçici olarak "
                   "başarısız olabilir.")

    with st.form("giris"):
        username = st.text_input("Kullanıcı adı")
        password = st.text_input("Parola", type="password")
        ok = st.form_submit_button("Giriş", type="primary",
                                   use_container_width=True)
    if ok:
        user = get_auth().login(username, password)
        if user is None:
            st.error("Giriş başarısız. Bilgileri kontrol edin; art arda "
                     "hatalı denemelerde hesap 15 dakika kilitlenir.")
            return
        st.session_state["user"] = user
        get_db().set_tenant(user["tenant_id"])
        st.rerun()


def _logout():
    st.session_state.pop("user", None)
    st.rerun()


def main():
    user = st.session_state.get("user")
    if not user:
        _login_page()
        return

    # Oturum yeniden bağlanırsa kiracıyı tazele (Streamlit rerun'ları arası)
    get_db().set_tenant(user["tenant_id"])

    pages = [
        st.Page("sayfalar/sevkiyat_editor.py",
                title="Taşıma Evrakı", icon="📝", url_path="sevkiyat-editor"),
        st.Page("sayfalar/gosterge_paneli.py",
                title="Gösterge Paneli", icon="📊", default=True),
        st.Page("sayfalar/kimyasal_veritabani.py",
                title="Kimyasal Veritabanı", icon="🧪"),
        st.Page("sayfalar/sevkiyatlar.py",
                title="Sevkiyatlar", icon="🚛"),
        st.Page("sayfalar/raporlar.py",
                title="Raporlar", icon="📈"),
        st.Page("sayfalar/karisik_yukleme.py",
                title="Karışık Yükleme", icon="🧯", url_path="karisik-yukleme"),
        st.Page("sayfalar/guvenlik_plani.py",
                title="Güvenlik Planı", icon="🛡", url_path="guvenlik-plani"),
        st.Page("sayfalar/firmalar.py",
                title="Firmalar", icon="🏢"),
        st.Page("sayfalar/suruculer.py",
                title="Sürücüler", icon="🧑‍✈️"),
        st.Page("sayfalar/arac.py",
                title="Araçlar", icon="🚚"),
    ]
    if user["role"] == "admin":
        pages.append(st.Page("sayfalar/ayarlar.py",
                             title="Ayarlar", icon="⚙️"))


    with st.sidebar:
        st.markdown(f"**{user.get('full_name') or user['username']}**  \n"
                    f"Rol: `{user['role']}`")
        if st.button("Çıkış", use_container_width=True):
            _logout()

    st.navigation(pages).run()


if __name__ == "__main__":
    main()
