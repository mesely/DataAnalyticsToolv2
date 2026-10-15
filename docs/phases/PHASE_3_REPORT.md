# Aşama 3 — zaman, ağ ve son kalite geçişi

15 Ekim 2026. **Durum: Aşama 3 yerel kabul tamam.** Kod ve runtime: `/Users/selmanyilmaz/Projects/context-layer`. Uygulama http://127.0.0.1:8123/app/ . Kullanıcı `selman` / `analiz-demo`.

## Önce / sonra

| Alan | Aşama 2 | Aşama 3 |
|---|---|---|
| Zaman | Tek filtre veya iki kayıt farkı | Önce / odak ay / sonra, 1–3 aylık pencereler, tarih kapsamı |
| Ağ değişimi | Tek görünür ağ | Aynı ürün evreninde kenar sayısı, Jaccard, yeni/kaybolan bağlar ve en büyük ağırlık farkları |
| İstatistik | Nokta değerler | Ürün/fatura kalemi satış HHI, negatif profil ağırlığı payı; AOV invoice bootstrap aralığı ve açık varsayımlar |
| Görsel okunabilirlik | UCI'de güçlü kenarlar düğümleri sıkıştırabiliyordu | Ağırlıkları değiştirmeyen collision-spaced yerleşim, kısa etiket / tam tooltip, topluluk numarası ve kenar tablosu |
| Signed graph anlamı | Aynı mutlak ağırlıkla genel topluluk | Cohesion yalnız pozitif bağlardan; derece/betweenness tüm görünür bağlarda; tek ülkede benzerlik kenarı üretilmez |
| Açıklama doğruluğu | Yerel şablon ve kaynak confidence | Beyan edilen sayılar dimension/unit/rank ile artifact'a çözülür; net/profit/why/predict reddi, ağ/zaman sorusunda doğru araca yönlendirme |
| UX / güvenlik | Ayrı yerel işlem durumları | Ortak hesap durumu, komut alanına otomatik odak, boşluk/BOM sonrası CSV formül savunması, policy-refused prompt'u başlık/recipe'ye yazmama |
| Kaynak araştırması | İlk adaptasyonlar | İlave dört PoliEco fonksiyonu runtime'da; SNIPS/Influencer tam dosya/hücre/sembol envanteri ve leakage düzeltme planı |

## Gerçek sayısal kanıt

Demo, odak 2025-02, pencere 1, eşik 2:

| Dönem | Brüt satış GBP | Sipariş | Kenar | Tarih kapsamı |
|---|---:|---:|---:|---|
| Önce / Ocak |7.054,30|60|26|31/31 gün|
| Odak / Şubat |7.295,60|60|27|28/28 gün|
| Sonra / Mart |7.055,10|60|26|27/31 gün; kısmi|

Önce/sonra aynı 8 ürün: 2 yeni, 2 kaybolan, 24 ortak kenar; Jaccard 0,857143. Kaynak CSV bağımsız stdlib/Decimal/basket oracle ile eşleşir. İndirilen JSON tekrar okunarak dönemler, coverage ve digest doğrulandı.

Gerçek UCI, odak 2011-06, pencere 1, eşik 2: Mayıs £770.536,02/1.681 sipariş/224 kenar; Haziran£761.739,90/1.533/248; Temmuz£719.221,19/1.475/241. Aynı 24 ürün: 27 yeni, 10 kaybolan, yaklaşık %85,26 örtüşme. Bunlar güncel ticaret verisi değil, UCI'nin 2010–2011 tarihsel verisidir. Kargo, hizmet ve Manual gibi pozitif fatura kalemleri korunur; fiziksel ürün kategorileri ayrıca ayrıştırılmadı. Kapsam notu kullanıcıya görünür.

AOV aralığı seed 47 / 200 tekrarlı invoice percentile bootstrap; en az 20, en fazla 50.000 sipariş. İid varsayımı müşteri/zaman bağımlılığını kapsamaz; tahmin, nedensellik veya etki testi değildir. Tarih kapsamı metadata uçlarına dayanır; aradaki her günün eksiksizliğini kanıtlamaz.

## Otomatik doğrulama

- **76 analitik testi geçti**, `/tmp/context-phase3-python.log`. Önceki aşamaları da kapsar. Bağımsız toplam/HHI/invoice/edge oracles, bootstrap seed/limit/null, UCI, filtre/invalid input, signed cohesion, tek ülke benzerlik reddi, düğüm aralığı, kapsam/digest ve sayısal claim bozma testleri.
- **42 ilgili core/CSV testi geçti / 5 dosya**, `/tmp/context-phase3-core-release.log`: workbench11, preview CSV2, KB Health13, auth12, property4. Auth/CSRF/owner/export/compare/temporal/revocation ve reddedilen prompt'un saklanmaması kontrol edilir.
- Core/web build ve web TypeScript geçti; diff whitespace kontrolü temiz. Minified JS yaklaşık 684 KB. Yük/p95 veya üretim benchmark'ı değildir.
- Kaynak doğrulama: **10 pinned upstream dosyanın SHA'sı eşleşti**, `/tmp/context-source-verification.log`. Adapte edilen hedefler overwrite edilmedi.
- Geniş Python856/17 sonucu önceki Aşama 1 kanıtıdır. Geniş core ilk koşusunun Docker'a bağlı kalan üç dosyası PHASE_1_REPORT içinde açık; bütün repo yeşil denmez.

## Tarayıcı kabulü

Komut araması açıldığında `document.activeElement` İşlem ara INPUT olarak doğrulandı; Zaman sorgusu ilgili aracı açıyor. Yerel demo ve UCI dönem hesapları, gerçek JSON/Excel indirme ve dosya tekrar okuma, 390px düzen, graph ve tablo alternatifleri incelendi. Son ekranlar `docs/evidence/phase3/` altında; önceki aşamalar ve ara QA görselleri araştırma arşivindeki evidence/phase1–3 altında. Son incelenmiş kanıtlar: `docs/evidence/workspace-overview.jpeg`, `docs/evidence/phase3/uci-temporal-final.jpeg`, `docs/evidence/phase3/mobile-final.jpeg`. `uci-temporal.png` ara QA görüntüsüdür; final yerleşim kanıtı değildir. Ana ağ tablosunda 150 kenar ve 24 seçilebilir düğüm doğrulandı. Son genel bakışta kısmi ilk/son ay uyarısı görünür; gerçek UCI toplamı £10.666.684,54 / 19.960 sipariş olarak tekrar kontrol edildi.

Recipe v3 görünür graph yerleşimi / signed community değişikliklerini ayırır. Eski v1/v2 kayıtları yeniden yazılmadı; güncel sonuç için yeniden çalıştırın. Numeric claim kontrolü beyan edilen yerel şablon sayıları içindir; serbest LLM metin entailment doğrulaması tamamlanmış değildir.

## Muhafazakâr yeniden puanlama

Aynı eski uzman ölçeği ve ağırlıklar: **77,74 ≈78/100** (başlangıç60,78; Aşama1:73; Aşama2:yaklaşık76). Bu deneysel etki büyüklüğü veya rakip sıralaması değil; kapsam ve görülen kanıta dayalı geçici uzman yargısıdır. Kullanıcı çalışması yok; belirsizlik birkaç puandır.

| Kriter | Ağırlık | Başlangıç | Şimdi | 90+ için kalan |
|---|---:|---:|---:|---|
| Veri bağlantıları/hazırlama |12|76|80|Retail dışı şema ve dönüşüm recipe |
| Semantik/lineage/tutarlılık |12|80|86|Genel metric compiler, grain ve ürün/hizmet eşleme |
| Analitik/istatistik/ML |12|45|76|Genel EDA, cluster/time uncertainty, gerçek ML holdout |
| LLM/yanıt doğruluğu |10|58|64|Gerçek sağlayıcı, plan/citation/claim eval |
| İş ağı analizi |8|25|84|Temporal robustness ve ölçek benchmark |
| Analist/UI akışı |12|50|84|Görevli kullanıcı testi ve erişilebilirlik matrisi |
| Güvenlik/yönetişim |12|78|81|Prod IdP/tenant/RLS/retention ve threat model |
| Test/tekrar üretim |10|78|87|Docker regresyon kapısı, release/code fingerprint |
| Performans/maliyet/işletim |6|45|60|Hedef yük p95, sistem resource limitleri, model maliyeti |
| Farklılaşma/pazar |6|50|58|Pilot kullanıcı, tekrar kullanım ve rakip görev deneyi |
| **Toplam** |100|**60,78**|**77,74**|Hedef92 elde edilmiş sonuç değil |

## Sonraki iş

NEXT_BACKLOG.md beklenen katkıya göre sıralı. Gerçek LLM bağlantısı, üretim hazırlığı, kullanıcı testi ve sızıntısız ML ayrı kapılar. SNIPS ve Influencer kaynakları araştırıldı; model eğitimi veya runtime entegrasyonu yapılmış gibi sayılmadı. Kullanıcı “Aşama4” dediğinde önce progress.md giriş kartını, sonra PHASE_4.md'yi okuyun.

## Son veri ve teslim kontrolleri

- CSV fiyatı en fazla dört ondalık basamak kabul eder; daha hassas değer sessizce yuvarlanmaz. JSON-escaped 1,2 MB gerçek worker import regresyonu geçti; eylemin CSV sınırı hâlâ 2 MB / 10.000 satırdır.
- Sıralamalarda eşit değer için sabit anahtar, önizlemede sabit satır sırası kullanılır. Sayısal claim testleri boyut/birim/sıra değiştirilmiş iddiaları reddeder.
- Kalıcı test ve build log kopyaları `docs/evidence/verification/` içinde. Eski geniş regresyon sonucu ile yeni dar release koşusu birbirinden ayrıdır.
- Yerel uygulama HTTP 200; browser üzerinden gerçek hesap ve ekran görünümü doğrulandı. Üretim yayını, gerçek provider çağrısı, kullanıcı pilotu ve model eğitimi bu teslimin tamamlanmış işleri değildir. Aşama 4 sözleşmesi hazır, uygulanmasına başlanmadı.
