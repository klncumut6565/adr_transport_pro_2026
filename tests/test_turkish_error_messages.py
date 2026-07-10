"""Ana program — Türkçe hata mesajı çevirisi testleri.

Kullanıcının tespiti: uygulama hata mesajlarında ham İngilizce istisna
metinleri (str(exc)) kullanıcıya gösteriliyordu. Kullanıcı arayüzünde
gösterilen HER mesajın Türkçe olması gerekiyor; ham İngilizce metin en
fazla log dosyasına yazılabilir, kullanıcıya asla gösterilmemelidir.
"""
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import importlib.util
_spec = importlib.util.spec_from_file_location(
    "anaprog", str(ROOT / "adr_transport_pro_2026.py"))
M = importlib.util.module_from_spec(_spec)
sys.modules["anaprog"] = M
_spec.loader.exec_module(M)


class TestTurkishErrorTranslation:
    @pytest.mark.parametrize("exc,expected_fragment", [
        (FileNotFoundError(2, "No such file", "test.xlsx"), "Dosya bulunamadı"),
        (PermissionError("Permission denied"), "erişim izni"),
        (ValueError("invalid literal for int()"), "geçersiz"),
        (KeyError("un_number"), "alan bulunamadı"),
        (IndexError("list index out of range"), "listesinde"),
        (ImportError("No module named 'foo'"), "kütüphane kurulu değil"),
        (IsADirectoryError("[Errno 21] Is a directory"), "klasör"),
    ])
    def test_known_exception_types_translated(self, exc, expected_fragment):
        msg = M._turkce_hata_metni(exc)
        assert expected_fragment in msg

    def test_unknown_exception_gets_generic_turkish_message(self):
        msg = M._turkce_hata_metni(RuntimeError("some obscure internal detail"))
        assert "Beklenmeyen bir hata" in msg
        assert "RuntimeError" in msg
        # Ham İngilizce ayrıntı kullanıcı mesajına sızmamalı
        assert "obscure internal detail" not in msg

    def test_sqlite_error_translated(self):
        import sqlite3
        try:
            con = sqlite3.connect(":memory:")
            con.execute("SELECT * FROM tablo_olmayan")
        except sqlite3.Error as e:
            msg = M._turkce_hata_metni(e)
            assert "veritabanı" in msg.lower()
            assert "no such table" not in msg.lower()

    def test_no_raw_english_leaks_for_common_cases(self):
        """Genel bir tarama: yaygın İngilizce istisna anahtar kelimeleri
        çeviri sonucunda görünmemeli."""
        english_markers = ["Errno", "Traceback", "NoneType", "object has no attribute"]
        cases = [
            FileNotFoundError(2, "No such file or directory", "x.xlsx"),
            ValueError("invalid literal for int() with base 10: 'abc'"),
            AttributeError("'NoneType' object has no attribute 'foo'"),
        ]
        for exc in cases:
            msg = M._turkce_hata_metni(exc)
            for marker in english_markers:
                assert marker not in msg, f"{marker!r} sizdi: {msg}"

    def test_all_critical_dialogs_use_helper_not_raw_str(self):
        """Kod tabanında QMessageBox.critical'a doğrudan str(exc)/str(e)
        geçen bir çağrı KALMAMALI — hepsi _turkce_hata_metni üzerinden
        gitmeli. Bu, gelecekte yeni bir hata gösterimi eklenirken aynı
        hatanın tekrarlanmasını önler."""
        src = open(ROOT / "adr_transport_pro_2026.py", encoding="utf-8").read()
        assert 'QMessageBox.critical(self, "Hata", str(exc))' not in src
        assert 'QMessageBox.critical(self,"Hata",str(e))' not in src
