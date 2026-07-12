"""Sayfaların ortak yardımcıları."""
import streamlit as st

from webcore.session import get_db


def db():
    return get_db()


def kullanici():
    return st.session_state.get("user", {})
