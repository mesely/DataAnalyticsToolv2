# Aşama 5 teslim kaydı

15 Ekim 2026. AW-8 yerel uygulama ve tarayıcı turu tamam; bu paketin e94819a geniş CI koşusu beş job yeşil; son görsel dalının CI
sonucu en son progress yayın kartında. Aşama4'ün e94c520 koşusu beş job yeşil:
`docs/evidence/verification/phase4-github-ci.txt`. Yeni kodun CI'si bununla
karıştırılmaz.

| Önce | Sonra |
|---|---|
| Sabit retail başlığına uygun dosya gerekir | Herhangi bir CSV profili, explicit satış alanı eşlemesi |
| Import sonrası kalite görülür | Importtan önce aynı normalizer ile gerçek tutar/satır/kalite |
| Tekrar davranışı yalnız dokümanda | Varsayılan koruma; explicit temizleme, önizle/geri al |
| Aynı bytes farklı eşlemeyi ayıramaz | Owner + CSV + dönüşüm receipt kimliği |
| Dosya sorunları çoğu zaman parser ayrıntısı | Başlık/alan/satır/tarih/precision sınırında anlaşılır ret |

Kanıt: `analysis/tests/test_preparation.py` 14 test; tüm analitik paket bu aşama
ve ML ile174 test. Tarayıcı `docs/evidence/phase5/`: before, preview, mobile.
Örnek `analysis/data/preparation-example.csv`: 3 satır/2 sipariş £14.70;
dedup seçilince2 satır/2 sipariş £12.60. Gerçek import aynı £12.60 hesapladı.
390px mobilde document.scrollWidth375, dialog343; yatay taşma yok.

Sınırlar: CSV profili geneldir, dashboard dönüşümü retail/GBP/invoice_line.
Parquet, generic metric compiler ve keyfi dataset dashboard henüz yoktur.
Profil kolon değerlerini içermez; kaynak bytes kalıcı kaydedilmez. İçe aktarma
metadata'sında recipe/source hash/kalite receipt saklanır. Bu bir dış doğruluk
veya para birimi tespit sistemi değildir.

Son kod041982c / GitHub run38822570859: beş job başarıyla tamamlandı,
16 Ekim public web summary üzerinden doğrulandı. Receipt
`docs/evidence/verification/phase6-github-final.json`; detay sayılarını eski
run'dan yeni run'a taşıma. Ardından yalnız kanıt/devir dokümanı güncellendi.
