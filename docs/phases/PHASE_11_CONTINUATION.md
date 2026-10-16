# A11 devam teslimi — doğruluk, kabul ve devir

16 Ekim 2026. Güncel spec: `specs/analyst-workspace-phase11.md` son doğruluk eki. Bu rapor önceki çalışmayı koruyan devam oturumunu anlatır; üretim veya tüm T01–T26 işlerinin tamamlandığı iddiası değildir. Devralma giriş noktası `progress.md` üstteki **GPT-6.1 Sol → Opus 5.5 Handoff** kartıdır.

## Doğrulanmış başlangıç

Repo `/Users/selmanyilmaz/Projects/context-layer`, dal `feat/analytics-workspace-phase4`, temiz HEAD `98f06003a3cb6101546c269fa1b813818aea6f23`. Publish remote `mesely/DataAnalyticsToolv2`, açık PR #1. GitHub başı `c96a29411ac7a29ca82f4a4f0ac2c4d769b990d2`: son üç yerel commit yalnız doküman/kanıttı ve gönderilmemişti. Önceki CI **38887656628**, c96a294 üzerinde beş job success. Son çalışma 228 değil **254 analytics testi** raporlamıştı; browser receipt yoktu. Uygulama/IdP/PG zaten ayaktaydı; kopya süreç başlatılmadı. Docker fixture yerelde kullanılamadığı için full core tekrar zorlanmadı.

## Bulunan ve kapatılan açıklar

| Öncelik | Önce | Şimdi | Kanıt |
|---|---|---|---|
| P1 | `gross=2140500` pence için £214.05 veya negatif £21,405 geçebiliyordu; küçük tam sayılar atlanıyordu | İşaretli Decimal büyüklüğü, desteklenen EN/TR ayraç sözdizimi ve açık birimler; bütün tam sayılar kontrol edilir; USD/EUR ve yüzde/count karışması reddedilir | `analysis/tests/test_narrative.py`; 14 vaka offline eval |
| P1 | Ülke filtre değeri dış `analysis_context` XML'ine yazılıyordu | Tarihler + `country_filter_applied` boole'ı; ülke etiketi yalnız yerelde | Filtreli demo HTTP kontrolü + XML testi |
| P1 | Parquet sütun isimleri SQL tanımına kaçışsız giriyordu; alan kontrolü fetchall sonrasındaydı | Çift tırnaklı identifier escaping; yalnız upload yoluna erişim; extension kapalı, 64MB DuckDB bütçesi, 1 thread, spill kapalı; 4.096 karakter ve 8MB açılmış metin kontrolü Python materialization öncesi | Tırnak içeren meşru sütun adı, sıkıştırılmış 8MB aşımı, nested type testleri; HTTP Parquet import |
| P2 | Geçerli pozitif geçmişin sonu sıfıra düşünce Holt negatif tahmin, negatif radius ve ters bant üretebiliyordu | Bütün adaylar geliştirme/final/dilim/ileri tahminde sıfır altından kırpılır. Relative geliştirme sıfırında kullanılamaz; ileride sıfırda çöken bant açık uyarıdır | Seed5 60 haftalık regresyon; bağımsız yeniden inceleme |
| P2 | Eksik kâr kanıtı yalnız fact tipinde reddediliyordu | Fact ve calculation reddedilir; eksik bilgi limitation olarak yazılır | Aynı tutarlı para değerini kâr diye sunan hesap testi |
| P2 | Windows-1252 fallback Türkçe dosyayı yanlış okuyabilir; metin kontrolü yetersizdi | UTF-8/1252/1254 seçimi, yerel ilk-satır önizleme, non-UTF8 onay kapısı; eski async dosya okuması yenisini ezemez | Gerçek cp1254 CSV: Çýðlýk→Çığlık; onaysız profile/import engeli |
| P2 | Tarih seçicisi mobilde küçük native kontrol olarak kalıyordu | Hazırlama select ve seçenek etiketleri en az44px; encoding textarea dar ekrana uyar | Gerçek DOM 44×290px ve ekran görüntüsü |

`narrative.py`, `forecast.py`, `preparation.py`, `decisions.py`, `Preparation.tsx`, `DecisionStudio.tsx`, `workbench.css` değişti. Spec ve DECISIONS değişiklikleri koddan önce yazıldı. Kaynak projeler yeniden port edilmedi; mevcut adaptasyonlar korundu.

## Tahmin — MEASURED

UCI 52 tam hafta; ilk8 sonrası **34 geliştirme**, **10 final** origin. Yöntem **mean8**, ölçek **absolute** (geliştirme coverage eşitliğinde öncelikli). Final veri aday/ölçek seçiminde kullanılmaz; final rolling origin bir sonraki origin'de geçmiş olur.

| Ölçüm | Değer |
|---|---:|
| Geliştirme seçilen MAE / naif | £30.445 / £33.201 |
| Final seçilen MAE / naif | £47.206,66 / £59.858,67 |
| Final RMSE / MASE / bias | £61.456,97 / 1,4218 / +£47.206,66 |
| Final MAE iyileşmesi vs naif | %21,14 |
| Nominal %90 bandı — geliştirme rolling kapsamı | 22/26 = %84,615 |
| Nominal %90 bandı — final kapsamı | 7/10 = %70 |
| %90 ortalama genişlik — geliştirme / final | £124.948,63 / £130.997,26 |
| Nominal %80 bandı — geliştirme / final | 19/26 = %73,077 / %70 |
| Sonraki tarihsel hafta noktası | 2011-12-05 · £308.417,06 |
| Gösterilen aralık | £242.918,43–£373.915,69 |

`calibrated=false`. Geliştirme coverage ölçeği seçmekte kullanıldığı için bağımsız kalibrasyon testi değildir. Final az sayıda noktalı betimleyici kontroldür. Final %90 coverage <%80 olunca UI/report tanısı eklenir; bu sonuçla tuning yapılmaz. Daha geniş bandın daha iyi sayılması önlenmek üzere width raporlanır; seçim kuralı hâlâ coverage uzaklığıdır, optimum interval-score iddiası yoktur. ≥104 haftalık mevsimsel gerçek veri doğrulaması ve ay dilimleri açık. UK/NL/EIRE aynı final origin'lerde teşhistir; genelleme ya da nedensel sonuç değildir.

Kanıt: `docs/evidence/verification/phase11-forecast-uci.json` (gerçek browser JSON indirmesinden, code fingerprint bağlı); eski `phase10/forecast-v3-uci.json` tarihsel olarak korunur.

## Alım ve analist sınırı

CSV/Parquet perakende GBP/fatura-kalemi sözleşmesine bağlıdır. CSV source hash, sunucuya giden UTF-8 metnindir; orijinal non-UTF8 byte hash'i olduğu iddia edilmez. Encoding seçimi yerel karardır; para/tarih dönüşümleri recipe/receipt içinde açıkça bağlıdır. Parquet 2MB **decoded dosya bytes** (base64 transport daha büyük), 10k satır,60 sütun,4096 karakter/alan,8MB toplam açılmış metin; primitive sütunlar. Nested/blob otomatik flatten edilmez. DuckDB bütçesi OS process/RSS hard isolation değildir.

Yerel anlatı daima vardır. Model metni yerel hesapların yerine geçmez. Geçerli ID ve eşit sayı, cümlenin anlamını kanıtlamaz; UI/Markdown bunu söyler. Semantik entailment ve aday-eylem metni eşleşmesi açık iş. Yerel final-origin ve business-validation sayılarına gerçek referans eklendi. Dayanak skoru olasılık değildir; iş doğrulaması0.

Offline **14 narrate** vakasında scripted ideal/adversarial kabul doğruluğu1,00, yerel renderer öz-tutarlılığı1,00; gerçek model başarısı değildir. Canlı HF bu oturumda **NOT RUN**; son gerçek probun HTTP402 kaydı korunur, canlı accuracy **BLOCKED/null**. Yeni kredi/hesap/endpoint değişikliği yapılmadı.

## Kabul ve testler

- Analytics **270 passed**; son anlatı metni/eval değişikliğinden sonra ilgili31 test ayrıca geçti. Forecast düzeltmesi bağımsız yeniden incelemede forecast+decisions51 testi geçti.
- Asset/NUL **48 passed**; NUL taraması836 tracked dosyada temiz (doküman ekleri sonrası final sayısı artabilir). Web build ve ayrı web tsc geçti.
- Gerçek HTTP **21/21**, üretici repoda `analysis.verify_workspace`; OIDC/CSRF/PG/owner isolation, UCI karar+filtre gizliliği, CSV/Parquet preview/import ve bozuk/stale/both-source retleri. Receipt `phase11-http-qa-continuation.json`, kod HEAD1b9d66c, kaynak fingerprint `a6f2dff3e356c9ee73f3a7ef5f34ea9f89fe05d9205114e3ea0b6ab9401fa83f` (46 dosya). Sonraki2b3f957 yalnız form hit-target CSS/encoding class değişikliği; API kaynağı aynı.
- Gerçek browser **16/16 PASS**, üretici CUA etkileşimleri: login, landing, dataset seçimi, scenario/6 tip, kanıta geçiş, forecast/dilim, aynı hash ile reopen, JSON/MD/XML indirme, CSV/encoding guard/Unicode/ID, Parquet, temalar,390px,Cmd-K/Tab/Enter/Escape,44px. Son frontend SHA'ları ve görüntü hash'leri `phase11-browser-qa.json` içinde. Viewport sıfırlandı; app UCI overview'da açık bırakıldı.
- Full core yerelde **BLOCKED (Docker fixture)**; GitHub **38897028637 / 4107eb7** tüm5job success: core474 passed/4 skipped, root874/17, analytics270. Receipt `phase11-ci.json`. Son receipt/devir doküman commitinin exact HEAD/CI kaydı PR açıklaması/Checks içinde; uygulama kodu aynı. Tam WCAG/screen reader, gerçek telefon, kullanıcı pilotu, browser LCP/CLS ve click-to-visible süre **NOT MEASURED**.

## Performans — dar gözlem

`analysis.evaluate_decisions --samples 3 --concurrency 1`,6 gerçek worker subprocess isteği,0 hata. Forecast p50 **148,10ms**, örnek p95/max **413,63ms**; decisions p50 **1759,09ms**, p95/max **1841,67ms**. `phase11-performance-continuation.json` commit1b9d66c ve fingerprint bağlıdır. HTTP kabulüyle örtüşen sistem yükü vardı; hız kazanımı karşılaştırması veya SLA değildir. HTTP/OIDC/PG/browser/HF dahil değildir. Önceki9/hücre benchmark ayrı korunur; farklı örnekler birleştirilmez.

## Olumsuz sonuçlar ve kalanlar

Ters bant, hatalı sayısal kabul ve filtre etiketi sızıntısı önce üretildi, sonra regresyonlarla kapatıldı; saklanmadı. Final coverage iyileşmedi. Offline formatter cache yoktu, resmi npm paketinden küçük kurulum yapıldı. İlk JPEG screenshot uzantısı `.jpg` named-image testinin kabul ettiği listede değildi: dosyalar `.jpeg` yapıldı; genel binary istisnası genişletilmedi. İlk final-warning testindeki tek seviye sıçraması, naive'ın sonraki haftalarda uyum sağlaması nedeniyle warning eşiğini aşmadı; gerçek sıralı çoklu sıçrama fixture'ıyla oracle düzeltildi. DuckDB allowed_paths başlangıç config'inde set edilemedi; connection açıldıktan sonra bound setting, ardından external disable+configuration lock ile çalışan yol test edildi. Bir ingestion reviewer otomatik araç engeliyle tamamlanamadı; meşru tırnaklı başlık ve expansion sınırı ana ajan tarafından bağımsız doğrulandı. Forecast/narrative reviewer sonuçları ana ajan tarafından yeniden üretildi.

P0: bulunan açık kusur kalmadı. P1: canlı model ölçümü dış erişim/kredi kapısında; serbest anlatının anlamsal doğruluk garantisi yok; üretim tenant/RLS/retention/hard resource gates açık. P2: final undercoverage, ≥2 sezon/ay dilimleri, filtreli DuckDB→pandas başlangıcı, İngilizce diagnostic mesajlarının TR UI'da yerelleştirilmesi, tam erişilebilirlik/kullanıcı ölçümü. P3: ileri arama/OOF/conversation/BI/SNIPS önceki backlog'da; ölçülmüş ihtiyaç olmadan eklenmez.

Disk başlangıç~2GiB, dip350MiB. Yalnız Chrome JS/WASM bytecode cache içindeki2saatten eski, `lsof` ile açık olmadığı doğrulanan1180 hash-adlı blob silindi:172,3MiB logical bytes geri kazanıldı, `df`527MiB boş gösterdi. Cookie/history/session/cache index, runtime, DB ve unique data korunur. Bu durum yeni büyük install/dataset/model işlerini sınırlayan ortam riskidir. Veri, token, .git, session ve mevcut kanıt korunur.
