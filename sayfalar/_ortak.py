"""Sayfaların ortak yardımcıları."""
import streamlit as st


def db():
    from app import _db
    return _db()


def kullanici():
    return st.session_state.get("user", {})
