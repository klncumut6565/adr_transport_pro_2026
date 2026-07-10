"""
ADR Transport Pro 2026 — Acil Admin Sıfırlama Aracı
====================================================
Bu scripti adr_transport_pro_2026.py ile AYNI klasöre koyun ve çalıştırın.

Yapacakları:
  1. Admin hesabının kilidini açar (failed_logins = 0, locked_until = NULL)
  2. Admin şifresini sıfırlar → admin123
  3. Tüm aktif oturumları kapatır

Kullanım:
    python admin_sifre_sifirla.py
"""

import sqlite3
import hashlib
import os
import base64
import hmac
from pathlib import Path

# ── Şifre hashleme (ana kodla aynı sabitler) ─────────────────────────────────
_LICENSE_SALT = b"ADR_PRO_2026_GIZLI_SALT_DEGISTIR"

def _hash_password(password: str, salt: bytes = None):
    try:
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
        if salt is None:
            salt = os.urandom(32)
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt + _LICENSE_SALT,
            iterations=390_000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode("utf-8")))
        return salt, key.decode("utf-8")
    except ImportError:
        # cryptography yoksa basit SHA256 kullan
        if salt is None:
            salt = os.urandom(32)
        h = hashlib.pbkdf2_hmac("sha256", password.encode(), salt + _LICENSE_SALT, 390_000)
        return salt, base64.urlsafe_b64encode(h).decode("utf-8")

# ── Veritabanı yolunu bul ─────────────────────────────────────────────────────
DB_PATH = Path.home() / ".adr_transport_pro" / "adr_database.db"

print("=" * 55)
print("  ADR Transport Pro — Acil Admin Sıfırlama Aracı")
print("=" * 55)

if not DB_PATH.exists():
    print(f"\n❌ Veritabanı bulunamadı: {DB_PATH}")
    print("   Programı en az bir kez çalıştırdıktan sonra bu aracı kullanın.")
    input("\nÇıkmak için Enter'a basın...")
    exit(1)

print(f"\n✅ Veritabanı bulundu: {DB_PATH}")

conn = sqlite3.connect(str(DB_PATH))
conn.row_factory = sqlite3.Row

# Mevcut kullanıcıları listele
users = conn.execute("SELECT username, role, failed_logins, locked_until, is_active FROM users").fetchall()
print(f"\nMevcut kullanıcılar ({len(users)} adet):")
print(f"  {'Kullanıcı':<15} {'Rol':<10} {'Hatalı Giriş':<14} {'Kilitli':<10} {'Aktif'}")
print("  " + "-" * 60)
for u in users:
    kilitli = u["locked_until"] or "Hayır"
    print(f"  {u['username']:<15} {u['role']:<10} {u['failed_logins']:<14} {kilitli:<10} {'Evet' if u['is_active'] else 'Hayır'}")

print()
print("Ne yapmak istiyorsunuz?")
print("  1) Admin kilidini aç + şifreyi 'admin123' olarak sıfırla")
print("  2) Tüm kullanıcıların kilidini aç (şifrelere dokunma)")
print("  3) Belirli bir kullanıcının kilidini aç")
print("  4) Çıkış")
print()

secim = input("Seçiminiz (1/2/3/4): ").strip()

if secim == "1":
    yeni_sifre = "admin123"
    salt, hsh = _hash_password(yeni_sifre)
    conn.execute(
        "UPDATE users SET password_salt=?, password_hash=?, failed_logins=0, locked_until=NULL, is_active=1 WHERE username='admin'",
        (salt, hsh)
    )
    conn.execute(
        "UPDATE user_sessions SET is_active=0, logout_at=datetime('now','localtime') WHERE is_active=1"
    )
    conn.commit()
    print("\n✅ Admin hesabı sıfırlandı!")
    print("   Kullanıcı adı : admin")
    print("   Yeni şifre    : admin123")
    print("   Tüm oturumlar kapatıldı.")

elif secim == "2":
    conn.execute("UPDATE users SET failed_logins=0, locked_until=NULL")
    conn.execute(
        "UPDATE user_sessions SET is_active=0, logout_at=datetime('now','localtime') WHERE is_active=1"
    )
    conn.commit()
    print("\n✅ Tüm kullanıcıların kilidi açıldı, oturumlar kapatıldı.")

elif secim == "3":
    k_adi = input("Kullanıcı adı: ").strip()
    r = conn.execute("SELECT id FROM users WHERE username=?", (k_adi,)).fetchone()
    if not r:
        print(f"\n❌ '{k_adi}' kullanıcısı bulunamadı.")
    else:
        conn.execute(
            "UPDATE users SET failed_logins=0, locked_until=NULL, is_active=1 WHERE username=?",
            (k_adi,)
        )
        conn.commit()
        print(f"\n✅ '{k_adi}' kullanıcısının kilidi açıldı.")

elif secim == "4":
    print("Çıkılıyor...")
else:
    print("Geçersiz seçim.")

conn.close()
print()
input("Çıkmak için Enter'a basın...")