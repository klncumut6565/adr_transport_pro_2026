-- TEK SEFERLİK MİGRASYON — Supabase SQL Editor'de bir kez çalıştır.
--
-- Sebep: chemicals tablosundaki UNIQUE(un_number, classification_code,
-- packing_group) kısıtı yanlıştı. Resmi ADR Tablo A'da bu üçlü AYNI olup
-- yalnızca özel hüküm (6. sütun) ile ayrışan gerçekten farklı satırlar var
-- (örn. UN1133 F1 PG II: 640C ve 640D varyantları). Bu kısıt yüzünden
-- 2939 geçerli Tablo A satırından yalnızca 2873'ü veritabanında kalıyordu,
-- 66 satır sessizce üzerine yazılarak kayboluyordu.
--
-- webcore/db.py ve supabase_kurulum.sql (yeni kurulumlar için) zaten
-- güncellendi. Bu betik SADECE mevcut/canlı Supabase veritabanını
-- düzeltmek için gerekli — bir kez çalıştırıp bir daha çalıştırmana
-- gerek yok.

DO $$
DECLARE
    kisit_adi text;
BEGIN
    SELECT tc.constraint_name INTO kisit_adi
    FROM information_schema.table_constraints tc
    WHERE tc.table_name = 'chemicals'
      AND tc.constraint_type = 'UNIQUE'
      AND tc.constraint_name IN (
          SELECT constraint_name
          FROM information_schema.constraint_column_usage
          WHERE table_name = 'chemicals'
          GROUP BY constraint_name
          HAVING array_agg(column_name ORDER BY column_name)
                 = ARRAY['classification_code', 'packing_group', 'un_number']
      )
    LIMIT 1;

    IF kisit_adi IS NOT NULL THEN
        EXECUTE format('ALTER TABLE chemicals DROP CONSTRAINT %I', kisit_adi);
        RAISE NOTICE 'Kısıt kaldırıldı: %', kisit_adi;
    ELSE
        RAISE NOTICE 'Kaldırılacak bir kısıt bulunamadı (zaten yok veya isim farklı).';
    END IF;
END $$;

-- Doğrulama: bu sorgu artık chemicals için hiçbir UNIQUE kısıt DÖNMEMELİ
-- (id PRIMARY KEY hariç):
SELECT constraint_name, constraint_type
FROM information_schema.table_constraints
WHERE table_name = 'chemicals';

-- Bu adımdan sonra: Ayarlar sayfasından "Kimyasal tablosunu boşalt" ile
-- mevcut (eksik) Tablo A verisini temizleyip ADR_A_TABLOSU.xlsx'i tekrar
-- içe aktar — artık tam 2939 kayıt gelecek.
