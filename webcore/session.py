"""Streamlit oturum kaynakları: DB ve Auth. app.py'den ayrı tutulur ki
sayfalar bunu import ederken app.py'nin tamamı (ve main() çağrısı)
yeniden çalışmasın (Faz 2'deki çift-render hatasının kaynağıydı)."""
from __future__ import annotations

import streamlit as st

from webcore.pg import PgDatabaseManager
from webcore.auth import AuthManager


@st.cache_resource
def get_db() -> PgDatabaseManager:
    return PgDatabaseManager(st.secrets["db"]["dsn"])


@st.cache_resource
def get_auth() -> AuthManager:
    return AuthManager(get_db())
