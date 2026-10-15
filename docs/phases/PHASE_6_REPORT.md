# Aşama 6 teslim kaydı

15 Ekim 2026. AW-9 yerel model deneyi uygulanmıştır; build,174 analitik test,
11 gerçek pinned kaynak doğrulaması geçti. Yeni kodun geniş CI kapısı ve
browser son QA progress yayın kartından okunur; yalnız bu metinden CI sonucu
varsayılmaz.

| Önce | Sonra |
|---|---|
| ML yalnız kaynak araştırması | Arayüzden gerçek sınıflama/regresyon eğitimi ve karşılaştırması |
| Influencer yalnız aday listesinde | Cell63 ön işleme ve66 log-hata gövdeleri runtime adapterında |
| Rastgele bir accuracy sayısı riski | Baseline, eğitim CV seçimi, ayrılmış holdout ve sınıf destekleri |
| Split/preprocess belirsiz | Random/group/time, train-only schema/dönüşüm, fold-içi SMOTE |
| Çalışma kaydı yok | Owner-scoped kart, recipe, split indeksleri/hash, source/runtime fingerprint |

Gerçek açık benchmark, seed47, rastgele80/20 (ürün geneline başarı oranı değil):

| Veri | Eğitim / test | Seçilen | Başlangıç | Bağımsız test |
|---|---:|---|---:|---:|
| Wine /13 özellik/3 sınıf | 142 /36 | LogisticRegression | macro-F1 .186667 | macro-F1 .971781; balanced accuracy .976190 |
| Diabetes /10 özellik | 353 /89 | Ridge | MAE61.370787 | MAE43.902866; RMSE55.077264; R².421890 |

Tam kartlar `docs/evidence/phase6/wine-card.json`, `diabetes-card.json`.
CSV kaynakları/checksum/attribution `analysis/data/ML_PROVENANCE.json`.
Sklearn bundled gerçek benchmark ölçümleridir; üretilmiş müşteri verisi diye
sunulmaz. Wine Aeberhard/Forina UCI CC BY4.0; Diabetes sklearn kopyası ve
Efron et al. kaynak atfı metadata'da. Tüm dataset'leri aynı lisansla etiketlemeyin.

18 ML testi: holdout hiçbir fit'e girmiyor, bilinmeyen kategori transformunda
schema/scaler değişmiyor, aynı feature vektörü partitionlar arasında reddediliyor,
eşit tarihlerin ve grupların ayrımı korunuyor, SMOTE uygunluğu/contract retleri,
her iki gerçek veri ve tekrar üretilebilir kart. Preparation14 + ML18 + önceki142=174.

Sınırlar: kart saklanır, fitted model veya ham CSV saklanmaz. Serving,
OOF stacking, model registry/deploy, otomatik as-of feature join, eşzamanlı
grup+zaman split, kalibrasyon ve tahmin aralığı tamamlanmış sayılmaz. Tekrarlı
aynı holdout deneyi insan seçimiyle iyimserleşebilir; UI ve kart açıkça söyler.
Tüm semantik leakage otomatik saptanmıyor. SNIPS/LSTM ayrıca ihtiyaç/ölçüm
olmadan ürüne zorla eklenmez. HF credit/gerçek pilot/production/large-scale
kapıları bu teslimle otomatik kapanmaz.

## 16 Ekim görsel teslim ve kabul

Gemini web oturumunda3 ek özgün 1024px JPEG üretildi, mevcut2 raster/4 SVG
korundu. Data preparation girişinde alignment instrument, model girişinde
calibration arcs, ilişkiler girişinde glass constellation kullanılır. Gerçek
metrikler üstüne dekoratif chart bindirilmez. `assets/PROVENANCE.md` source
chat/turn kaydı, ASSET_MANIFEST hash ve scanner exact binary listesi içerir.
Mobil390px document375/dialog343/brokenImages0; Esc kapatma ve JSON indirme
önceki/son browser turunda doğrulandı. Native dosya düğmesi yerine tüm kutu
tıklanabilir; görünür klavye odağı korunur. Yeni tablo metni12px, başlık/altyazı
kontrastı iyileştirildi. Yeni ekranlar05/06/07/08 altındadır.

Geniş GitHub CI e94819a beş job yeşil:473 core pass/4 skip,841 root Python
pass/17 skip,173 analytics pass. Son skew fixture sonrası yerel174 pass; son
görsel dalının CI sonucu progress yayın kartında. Test skipleri başarı sayılmaz.
