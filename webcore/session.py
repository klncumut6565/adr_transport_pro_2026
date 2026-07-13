"""Streamlit oturum kaynakları: DB ve Auth. app.py'den ayrı tutulur ki
sayfalar bunu import ederken app.py'nin tamamı (ve main() çağrısı)
yeniden çalışmasın (Faz 2'deki çift-render hatasının kaynağıydı).

KRİTİK DÜZELTME: get_db()/get_auth() ÖNCEDEN @st.cache_resource ile
tanımlıydı — bu, argümansız olduğu için TEK bir global singleton üretir;
uygulamaya aynı anda giren TÜM kullanıcılar AYNI psycopg Connection
nesnesini PAYLAŞIYORDU. Streamlit Cloud, farklı kullanıcı oturumlarının
script'lerini AYRI İŞ PARÇACIKLARINDA eşzamanlı çalıştırabildiği için, iki
kullanıcı tam aynı anda sorgu attığında tek bağlantı üzerinde çakışan
transaction'lar oluşuyordu (psycopg.transaction.OutOfOrderTransactionNesting
— iki iş parçacığının SET LOCAL transaction'ları iç içe geçip sırası
bozuluyordu). Önceki (SET LOCAL öncesi) tasarımda bu hata SESSİZCE veri
karışıklığına yol açabilirdi; transaction sarmalayıcısı bunu en azından
GÖRÜNÜR bir hataya çevirdi.

Çözüm: her Streamlit OTURUMUNA (her tarayıcı sekmesi/kullanıcı) kendi özel
bağlantısı — st.session_state ile (st.cache_resource DEĞİL). Bu hem
performans (Supabase pooler zaten çoklu bağlantıyı verimli yönetir) hem
de GÜVENLİK açısından daha sağlam: artık kiracı izolasyonu yalnızca RLS'e
değil, oturumlar arası TAMAMEN AYRI Python nesnelerine de dayanıyor.
"""
from __future__ import annotations

import streamlit as st

from webcore.pg import PgDatabaseManager
from webcore.auth import AuthManager


def get_db() -> PgDatabaseManager:
    if "_db_instance" not in st.session_state:
        st.session_state["_db_instance"] = PgDatabaseManager(st.secrets["db"]["dsn"])
    return st.session_state["_db_instance"]


def get_auth() -> AuthManager:
    if "_auth_instance" not in st.session_state:
        st.session_state["_auth_instance"] = AuthManager(get_db())
    return st.session_state["_auth_instance"]
