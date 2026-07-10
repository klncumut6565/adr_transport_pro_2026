"""
ADR Mix Checker Pro
====================

ADR 7.5.2 (Karışık yükleme yasağı) kapsamında, UN numarası / tehlike sınıfı /
etiket bilgisi bilinen tehlikeli madde kalemlerinin aynı araç veya konteyner
içinde birlikte taşınıp taşınamayacağını analiz eden masaüstü uygulama.

Bu paket, aynı projenin dağınık biçimde (main.py, database.py, checker.py,
rules.py, ... şeklinde tekrar tekrar üretilmiş 80'den fazla parça halinde)
yazılmış önceki sürümlerinin tek, tutarlı ve test edilebilir bir mimaride
yeniden düzenlenmiş hâlidir.

ÖNEMLİ HUKUKİ NOT:
Bu yazılım ADR Tablo 7.5.2.1'in basitleştirilmiş bir uygulamasıdır. Sınıf 1
(patlayıcı) maddeler arası uyumluluk grubu kontrolü (7.5.2.2), miktar bazlı
muafiyetler (örn. 1000 kg toplam kütle istisnası) ve tank taşımacılığına
özel kurallar gibi konular bu sürümün kapsamı dışındadır. Üretimde
kullanılmadan önce verilerin güncel ADR metni ile bir Tehlikeli Madde
Güvenlik Danışmanı (TMGD/DGSA) tarafından doğrulanması önerilir.
"""

__version__ = "2.4.1"
__app_name__ = "ADR Mix Checker Pro"
