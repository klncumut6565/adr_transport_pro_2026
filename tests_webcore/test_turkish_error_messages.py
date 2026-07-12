"""webcore.errors — Türkçe hata mesajı çevirisi testleri (Faz 4).

Masaüstü tests/test_turkish_error_messages.py'nin webcore karşılığı.
Orijinali, ana_program.py'yi importlib.util ile dinamik yükleyip PyQt6
gerektiriyordu; burada doğrudan taşınmış webcore.errors.turkce_hata_metni
test ediliyor (PyQt6 bağımlılığı yok).

Kullanıcının tespiti: uygulama hata mesajlarında ham İngilizce istisna
metinleri (str(exc)) kullanıcıya gösteriliyordu. Kullanıcı arayüzünde
gösterilen HER mesajın Türkçe olması gerekiyor; ham İngilizce metin en
fazla log dosyasına yazılabilir, kullanıcıya asla gösterilmemelidir.
"""
import pytest

from webcore.errors import turkce_hata_metni


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
        msg = turkce_hata_metni(exc)
        assert expected_fragment in msg

    def test_unknown_exception_gets_generic_turkish_message(self):
        msg = turkce_hata_metni(RuntimeError("some obscure internal detail"))
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
            msg = turkce_hata_metni(e)
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
            msg = turkce_hata_metni(exc)
            for marker in english_markers:
                assert marker not in msg, f"{marker!r} sizdi: {msg}"

    def test_no_raw_str_exc_in_web_pages(self):
        """Web sayfalarında st.error(f"...{exc}") gibi ham istisna sızıntısı
        KALMAMALI — hepsi turkce_hata_metni üzerinden gitmeli. Bu, gelecekte
        yeni bir hata gösterimi eklenirken aynı hatanın (masaüstünde bir kez
        yaşanmış) tekrarlanmasını önler."""
        import pathlib
        sayfalar_dir = pathlib.Path(__file__).resolve().parent.parent / "sayfalar"
        yasakli_desenler = ['{exc}")', "{exc}'", '{e}")', "{e}'"]
        ihlaller = []
        for py_file in sayfalar_dir.glob("*.py"):
            src = py_file.read_text(encoding="utf-8")
            for satir_no, satir in enumerate(src.splitlines(), start=1):
                if "st.error" in satir or "st.warning" in satir:
                    for desen in yasakli_desenler:
                        if desen in satir and "turkce_hata_metni" not in satir:
                            ihlaller.append(f"{py_file.name}:{satir_no}: {satir.strip()}")
        assert not ihlaller, "Ham istisna metni kullanıcıya sızıyor:\n" + "\n".join(ihlaller)
