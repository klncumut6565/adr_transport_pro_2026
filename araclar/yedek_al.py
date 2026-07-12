"""Supabase/PostgreSQL yedeği — Faz 6 (ücretsiz planda otomatik yedek yok).

Kullanım:
    python araclar/yedek_al.py --dsn "postgresql://..." [--cikti yedekler/]

Tüm tabloları (kimlik tabloları dahil) zaman damgalı tek bir .zip içinde
CSV olarak dışa aktarır. Geri yükleme migrate aracıyla değil, gerekirse
CSV'lerin Supabase Table Editor'den içe aktarılmasıyla veya psql \\copy ile
yapılır; asıl amaç FELAKET KURTARMA kopyasıdır. Düzenli kullanım önerisi:
haftada bir çalıştırıp zip'i bulut diskinize koyun.

Not: pg_dump kuruluysa en kapsamlı yedek şudur (şema+veri+kısıtlar):
    pg_dump "DSN" --no-owner --format=custom -f yedek.dump
Bu araç, pg_dump kurulumu gerektirmeyen taşınabilir alternatiftir.
"""

from __future__ import annotations

import argparse
import csv
import io
import sys
import zipfile
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

TABLOLAR = ["tenants", "web_users", "companies", "drivers", "vehicles",
            "chemicals", "packaging_types", "company_products",
            "shipments", "shipment_items", "settings", "audit_logs"]


def yedekle(dsn: str, cikti_dizini: str = "yedekler", log=print) -> str:
    import psycopg
    from psycopg.rows import dict_row

    Path(cikti_dizini).mkdir(parents=True, exist_ok=True)
    damga = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_yolu = str(Path(cikti_dizini) / f"adr_yedek_{damga}.zip")

    conn = psycopg.connect(dsn, row_factory=dict_row)
    toplam = 0
    with zipfile.ZipFile(zip_yolu, "w", zipfile.ZIP_DEFLATED) as z:
        for t in TABLOLAR:
            try:
                with conn.cursor() as cur:
                    cur.execute(f"SELECT * FROM {t} ORDER BY 1")
                    rows = cur.fetchall()
            except psycopg.errors.UndefinedTable:
                conn.rollback()
                log(f"[{t}] tablo yok, atlandı")
                continue
            buf = io.StringIO()
            if rows:
                w = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
                w.writeheader()
                w.writerows(rows)
            z.writestr(f"{t}.csv", buf.getvalue())
            toplam += len(rows)
            log(f"[{t}] {len(rows)} satır")
        z.writestr("YEDEK_BILGI.txt",
                   f"ADR Transport Pro 2026 yedeği\nTarih: {damga}\n"
                   f"Toplam satır: {toplam}\nTablolar: {', '.join(TABLOLAR)}\n")
    conn.close()
    log(f"\nYedek yazıldı: {zip_yolu} (toplam {toplam} satır)")
    return zip_yolu


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dsn", required=True)
    ap.add_argument("--cikti", default="yedekler")
    a = ap.parse_args()
    yedekle(a.dsn, a.cikti)
