# Aşama 4 — yerel uygulama ve GitHub teslimi

15 Ekim 2026. **Yerel uygulama paketi tamam; canlı Llama ve üretim dış kabul kapıları açık.** Kod `/Users/selmanyilmaz/Projects/context-layer`; uygulama http://127.0.0.1:8123/app/ ; `selman` / `analiz-demo`. Aşama 1–3 tamamlanan özellikleri korunur. Kullanıcının Gemini ve GitHub push yetkisi bu aşamada eklendi. Ürün sözleşmesi specs/analyst-workspace-phase4.md.

## Önce / sonra

| Alan | Aşama 3 | Aşama 4 yerel paketi |
|---|---|---|
| LLM | Provider adapte, çağrılmıyor | Gerçek adviSU transport'a HF desteği; kullanıcı seçimiyle strict Llama intent/scope planı; schema ve yerel claim kontrolü |
| Canlı model sonucu | Yapılandırılmamış | Gerçek API çağrısı HTTP402 kredi gereksinimi; açık fallback, hiçbir sahte model cevabı yok |
| İşlem kontrolü | Run/expert process-local; catalog/import dışında | Bütün worker yollarında ortak actor/global admission, aynı DB'de core süreçleri arasında advisory permits, disconnect kill |
| Tekrar üretim | v3 sonuç/veri digest | v4 aynı kanıt + hesap kaynak/bağımlılık fingerprint; eski kayıtlar korunur |
| Yaşam döngüsü | Kaydet/aç/rerun | Owner-scoped, audit'li arşiv/geri yükleme; kaynak veri veya kanıt silinmez |
| Ürün dili | Sloganlar, geliştirme/aşama etiketleri, kota benzeri metre | Satış özeti gibi doğrudan görevler, gerçek işlem durumu, metadata bağlamında örnek veri açıklaması |
| Görsel kimlik | Genel marka/line ikonlar | Gemini'den iki özgün 1024px artwork ve dört navigation SVG; tutarlı navy/cobalt/neutral dil |
| Sunum | Altyapı README | Gerçek ekranlı ürün README, kaynak kredileri, kurulum, yetenekler ve açık sınırlar |

## Llama gerçekte nasıl çalışıyor?

`analysis/adapted/providers.py` actual adviSU transport/retry/deadline/sanitization üzerine huggingface spec/settings; `analysis/llm.py` strict iki anahtarlı plan. Model soru + sabit semantic policy alır. Satırlar, sonuçlar, dataset başlığı veya credential modele gönderilmez. UI'da seçilmeden çağrı yok. Yerel policy reddi veya açık filtre değişikliği provider'a gitmez. Model SQL/Python ve serbest olgusal metin çalıştıramaz; yalnız mevcut hesap yönlendirmesi. Sayılar yerelde hesaplanıp beyan edilmiş claim'lere çözülür.

Gerçek router model listesi HTTP200; Llama 3.3 70B mevcut. Gerçek chat completion HTTP402; yanıt credit/payment gerektiriyor. Token geçerliliğinin her yetkisini veya model yanıt kalitesini model listesiyle kanıtlamıyoruz. Başarılı canlı yanıt/usage/cost ölçülmedi. UI bunu gösterir ve standart sonucu korur. Yerel anahtar mode0600 ignored dosyada, Git/browser/evidence dışında; değer raporda yok. 50 mock plan-contract fixture canlı model accuracy benchmark'ı değildir.

## Doğrulama

- **142 analitik Python testi geçti**, phase4-python.log. HF MockTransport, schema/extra-key/code reddi, refused soru provider'a gitmeme, seçimsiz çağrı yok, HTTP402 fallback/connection state, scope değişikliğinde açıklama, Türkçe sayılar, fingerprint ve önceki bağımsız analitik oracles.
- **45 ilgili core/CSV testi / 5 dosya geçti**, phase4-core.log. Workbench14 + CSV2 + KB13 + auth12 + property4. Arşiv ownership/CSRF/kanıt koruma/restore, dışarıdan tutulmuş PG permit altında catalog/run/import 429 ve permit sonrası toparlanma, gerçek image MIME, eski SQL/temporal güvenlik kontrolleri.
- Core/web build, web noEmit TypeScript ve diff whitespace geçti. Son dört navigation SVG build'e dahildir. CI analytics işi, public fixture hazırlama ve core bağımlılık kurulumuyla genişletildi; uzak CI sonucu ayrıca izlenir, henüz geçmiş gibi sayılmaz.
- NUL guard kaynaklarda korunur; gerçek JPEG ekran/marka görselleri named exceptions + SHA manifest ile kabul edilir. Bu kararı öngören eski scanner sözleşmesi AW-7 ile somutlaştırıldı. Asset güvenlik/NUL kapısı **15 test geçti**, phase4-assets.log. Ekran görüntüleri gerçek JPEG biçimiyle yayımlandı; önceki sohbet bağlantıları için eski .png adları yalnız ignored yerel alias olarak korunur.
- Gerçek browser: UCI özeti, country yanıtı, 24/150 network seçim, Mayıs/Haziran/Temmuz dönemleri, arşiv/restore, boş kitaplık artwork, 1280×900 desktop ve 390×844 mobil, dört görevli mobil menü, command search INPUT odağı, kırık img=0 ve yatay overflow yok. Ekranlar phase4 altında; dosyalar açılıp incelendi. Screenshot capture'daki scroll/fixed-sidebar ara hataları yeniden çekilerek düzeltildi.
- QA'nın yeni `Perakende satış özeti` kaydı restore edilip görünür bırakıldı. Önceki kendi oluşturduğumuz `Aşama 1 — doğrulanmış demo` fixture bulgusu arşivlendi; geri alınabilir. İlgisiz kayıt/veri silinmedi.

## Kısa yerel performans gözlemi

530.104 satır, tam graph dahil analitik worker, HF kapalı. Her concurrency için 12 subprocess denemesi; warm OS cache, küçük örnek, bu makinede başka işler de olabilir. HTTP/login/DB roundtrip ve production load/RSS benchmark'ı değildir.

| Eşzamanlı worker | N | Medyan ms | Örnek p95 ms | Hata |
|---|---:|---:|---:|---:|
|1|12|882|1219|0|
|3|12|1086|1185|0|

Raw phase4-load.json ve tekrar komutu `python -m analysis.benchmark`. 5M/50M, hard OS resource limiti ve gerçek HTTP p95 açık. PG permit testleri farklı core süreçleri için lock primitive'ini sınar; bunlar dağıtık job queue/backpressure SLA sertifikası değil.

## Görsel kabul adımları

1. **Özet — iyi:** slogan/aşama etiketi kaldırıldı; gerçek metrik/tarih/kapsam görünür; 02-overview.jpeg.
2. **Analiz — iyi, canlı servis sınırlı:** sınırlı sonuç, Llama seçimi ve bağlam/kanıt; 03-analysis.jpeg; gerçek kredi hatası 09-provider-fallback.jpeg ara kozmetik sürümündendir.
3. **Ağ ve dönem — iyi:** ürün seçimi, merkeziyet kapsamı ve üç dönem sayıları; 04-network.jpeg / 05-temporal.jpeg.
4. **Mobil — iyi:** 390px, iki sütun KPI, dört görevli açılır menü; 06-mobile.jpeg. Tam ekran okuyucu/zoom/contrast matrisi henüz yok.
5. **Bulgular — iyi:** yeni kayıt archive/restore, 07-findings.jpeg; 08-library-empty.jpeg özgün artwork. Gerçek kullanıcı görev süresi ve memnuniyet ölçümü yapılmadı.

Tasarım temelinde 8px spacing, tek accent, tabular numbers ve açık hiyerarşi var. Hick/Fitts'e ilişkin ölçülmüş başarı yüzdesi veya WCAG sertifikası iddiası yok. İşlevsel utility ikonları tanıdık çizgi dilini korur; marka ve dört ana gezinme asset'i özgündür. Synthetic provenance Veri hakkında içinde korunur; örnek veri gerçek ticari veriymiş gibi sunulmaz.

## Açık kapılar / sonraki aşama

**Aşama 4 tümüyle üretime hazır veya canlı LLM eval tamamlandı diye kapatılamaz.** HF inference kredisi ve başarılı canlı 50+ görev eval; gerçek IdP/tenant/RLS/retention; dataset/query lifecycle; HTTP/cancel stress ve 5M/50M/memory; görevli UX pilotu; Docker'a bağlı eski sync-drill/sync-run/mcp-execute snapshot regresyonu açıktır. Docker daemon restart edilmedi. Geniş Python856/17 tarihsel Aşama1 kanıtıdır; tüm repo yeni geniş koşusu diye sayılmaz.

SNIPS/Influencer eğitimleri hâlâ araştırma aşamasında; Aşama5 genel veri+leakage-safe ML paketi, Aşama6 BI/üretim pilotu için NEXT_BACKLOG haritası var. Önceki uzman78/100 puanı ölçülmüş yeni pazar puanı gibi artırılmadı. Yeni score kullanıcı/live-model/üretim kanıtıyla değerlendirilmeli.

## Git teslimi

Yayın hedefi `mesely/DataAnalyticsToolv2`, dal `feat/analytics-workspace-phase4`. AlperCamli origin read-only, mesely hedefinde admin yetkisi doğrulandı. Branch push ve PR sonucu progress.md üst kartına ve son teslim notuna işlenir; main'e birleştirme veya production deploy otomatik yapılmaz. Uygulama örnek/public veri dışında gerçek müşteri sistemine bağlanmadı.

Canlı LLM planı aynı kalırsa hesap replay'i sabittir; temperature0 model planının bit düzeyinde deterministik olmasını garanti etmez. Yeni model planı veya kaynak fingerprint değişimi yeni digest üretir. Önceki artifact ve plan owner run kaydında korunur; donmuş planı ayrı replay modu olarak yürütme ve gerçek model eval kapısı açıktır. HF resmi protokol: https://huggingface.co/docs/inference-providers/index .
