# Context Layer / Analytics — tek giriş ve devir rehberi

## ŞİMDİ OKU — 15 Ekim 2026

**Durum: AŞAMA 1–3 YEREL KABUL TAMAM. AŞAMA 4 YEREL PAKETİ TAMAM; CANLI LLAMA / ÜRETİM DIŞ KAPILARI AÇIK.** Bu dosya önceki çelişen günlükleri temizleyen güncel durumdur. Tarihsel “uygulanıyor / son browser bekliyor” notlarını güncel durum sanma. Mevcut çalışmayı baştan yazma.

**Tek uygulama kökü:** `/Users/selmanyilmaz/Projects/context-layer`. Yayın hedefi `mesely/DataAnalyticsToolv2`, dal `feat/analytics-workspace-phase4`; PR üzerinden review. Son Git sonucu bu dosyanın yayın kartındadır. Production deploy/main merge yapılmadı. Başlangıç HEAD `0aaac741fd36d0e5b4f0c182d1b8b05c87884c17`.

**Çalışan uygulama:** http://127.0.0.1:8123/app/ — `selman` / `analiz-demo`. İkinci kimlik `alper` / aynı parola; `viewer` aynı parolayla yetkisiz rol testidir. Bunlar yalnız yerel fixture hesaplarıdır. Yeni başlangıç: repo kökünden `./deploy/phase1/start.sh`.

**GitHub teslimi:** [PR #1](https://github.com/mesely/DataAnalyticsToolv2/pull/1) · [Ürün README ve ekranlar](https://github.com/mesely/DataAnalyticsToolv2/tree/feat/analytics-workspace-phase4).

**İlk devam hareketi:** `docs/phases/PHASE_4_REPORT.md` ve `NEXT_BACKLOG.md` oku. HF gerçek completion HTTP402 credit/payment gerektiriyor; yeni token isteme/anahtar arama/hesaba ödeme yapma. Bağlantı kodu ve offline kontratlar hazır; başarılı canlı 50+ görev eval kredili hesapla açık. Üretim tenant/RLS/retention, 5M/50M/HTTP yük ve gerçek UX pilotu ayrı açık kapılar. Yeni Aşama5 genel veri/ML veya Aşama6 BI/pilot işine kullanıcı yönlendirmesine göre geç; bitmiş özellikleri yeniden yazma.

## Kullanıcının amacı ve yetki

Alper'in DataAnalyticsTool / Context Layer projesini Selman'ın adviSU ve PoliEco kodlarını gerçekten adapte ederek güçlü, kolay kullanılan, LLM'e hazır bütüncül analytics ürününe dönüştürmek. Sadece esinlenmek yeterli değil. Kaynak commit/dosya/sembol → hedef → değişiklik → runtime kullanımı → test kanıtı kaydedilir. Her kaynak zorla ürüne sokulmaz; LSTM ancak ölçülmüş fayda varsa.

Kullanıcı başlangıçta analiz/kodsuz hazırlık istedi; sonraki açık talebi yerel geliştirmeyi, aşamaları uygulamayı, çalıştırmayı, test verisi/rehberini ve önce/sonra karşılaştırmasını yetkilendirdi. Kalite korunarak sonraki aşamalara devam edilebilir. Rutin yerel kararlar için tekrar soru gerekmez. Son kullanıcı mesajı ayrıca sağladığı HF token ile Llama entegrasyonu/gerçek sınırlı probe, oturumu açık Gemini ile özgün asset ve GitHub push yetkisini verdi. HF ödeme/paket değişikliği, gerçek müşteri bağlantısı ve production yayın yapılmadı; kapsam olmadan varsayılmaz. Token değeri bu dosyada/Git içinde bulunmaz.

UI/UX merkezi gereksinim: Hick–Hyman doğrultusunda dört ana görev ve kademeli uzman araçları; Fitts doğrultusunda ulaşılabilir hedefler/yakın eylemler; tutarlı boşluk/renk/tipografi/ikon, klavye ve görünür focus/durum/hata. Bunlar tasarım kararlarıdır; görevli kullanıcı ölçümü ve tam WCAG denetimi olmadan başarı oranı/sertifika iddia edilmez. Aşama4: Gemini web oturumundan iki özgün artwork + dört navigation SVG kullanıldı; utility kontrollerin tanıdık çizgi ikonları korundu. Asset gerekirse işlevsel anlam ve erişilebilirlik korunur.

## Beş kaynak — bağlantılar ve sabit sürümler

| Kaynak | GitHub | İncelenen commit |
|---|---|---|
| Alper / temel ürün | https://github.com/AlperCamli/DataAnalyticsTool.git | `0aaac741fd36d0e5b4f0c182d1b8b05c87884c17` |
| adviSU | https://github.com/mesely/adviSU.git | `e1e224134a3ce9a52c758c35ce517b1d42c9b75a` |
| PoliEcoTRNetSci | https://github.com/mesely/PoliEcoTRNetSci.git | `c1705e76a9e2c36ddda36c95d03bd733cf52a17a` |
| SNIPS / intent-LSTM | https://github.com/mesely/NLP-Intent-Detection-with-SNIPS-Dataset.git | `74deda2b6f6d188e590045c4f922d6491881726c` |
| Influencer / ML | https://github.com/mesely/Influencer-Category-and-Like-Prediction-Stacking-SMOTE-RF.git | `b217890ec18c35180c7ac7bc3a8dcd28a6c1794e` |

Araştırma arşivi `/Users/selmanyilmaz/Desktop/guncel_cvler/analytics_tool_review`: `repos/` kaynak checkout'lar; `reports/ANALYSIS.md`, `reports/TODO.md`, `reports/CODE_REUSE_MAP.md`, `reports/PROGRESS_PRE_PHASE1.md` tarihsel başlangıç analizi, T01–T26 ve eski kayıtlar. Bazı eski Desktop dosya okumaları takıldığı için aynı HEAD'den yeni full clone alındı. Güncel geliştirmeyi eski checkout'a taşımayın. Bu progress'in aynası `/Users/selmanyilmaz/Desktop/guncel_cvler/progress.md`; kanonik dosya yeni repo içindedir.

## Tamamlanan aşamalar ve kanıt girişleri

| Aşama | Gerçek teslim | Sözleşme ve rapor |
|---|---|---|
| 1 / yerel analist ürünü | Genel bakış, hesap/filtre/kalite/kanıt, sınırlı yerel açıklama, co-purchase ve similarity ağı, owner-scoped bulgu kaydet/aç/yeniden çalıştır, CSV import, sentetik ve gerçek veri, mobil tasarım | `docs/phases/PHASE_1.md`, `PHASE_1_REPORT.md` |
| 2 / uzman araçları | Alper sqlval kullanan read-only SQL, güvenli CSV/XLSX, gerçek adviSU BM25 bağlam arama, iki owner run karşılaştırması, genişletilmiş digest | `docs/phases/PHASE_2.md`, `PHASE_2_REPORT.md` |
| 3 / zaman ve ağ | Önce/odak/sonra dönemler, sabit ürün evreninde ağ/Jaccard, HHI/affinity, seed'li invoice bootstrap, kapsam/varsayımlar, graph çakışma giderme, numeric claim kontrolü ve UX güvenlik düzeltmeleri | `docs/phases/PHASE_3.md`, `PHASE_3_REPORT.md` |
| 4 / yerel paket tamam, dış kabul açık | HF strict intent planner + gerçek402 fallback; bütün worker admission/PG permits/cancel; v4 fingerprint; owner archive/restore; özgün Gemini tasarımı ve ürün README | `docs/phases/PHASE_4.md`, `PHASE_4_REPORT.md`, `NEXT_BACKLOG.md` |

Aşama 3'ün sözleşmeyle seçilmiş kapsamı betimleyici zaman/ağ analizidir; model eğitimi zorla eklenmedi. “Aşama 3 tamam” demek “SNIPS/Influencer modelleri eğitildi” demek değildir. T01–T26'nın tamamı veya bütün kaynakların entegrasyonu kapanmış sayılmaz.

Başlangıç uzman değerlendirmesi **60,78≈61/100**; Aşama 1 **73**, Aşama 2 **yaklaşık 76**, Aşama 3 **77,74≈78**. Aynı ağırlıklar ve kriter tablosu PHASE_3_REPORT içinde. Bunlar geçici uzman puanları; deneysel UX/pazar benchmark'ı değil. 92 hedef, elde edilmiş sonuç değil. Sonraki katkı tahminleri NEXT_BACKLOG tablosunda büyükten küçüğe; puanlar toplamsal garanti değildir.

## Gerçek yeniden kullanım — ne çalışıyor, ne henüz çalışmıyor

Tam kayıt `docs/phases/REUSE_LEDGER.md`, kaynak SHA/commit/semboller `analysis/SOURCE_LEDGER.json`.

- **Alper:** Fastify/Postgres/OIDC/CSRF/rol/audit/migration/SPA altyapısı ve `sqlval.validate_statement` gerçekten kullanılır. Eski yönetim ekranı korunur. Yeni motor public veya owner-uploaded materyalize veriyi hesaplar; canlı execute_sql token yolunu bypass etmez. Generator deterministik ve LLM'siz kalır. Ürün ek kararı `docs/phases/PRODUCT_EXTENSION.md`, HLR/specs ve DECISIONS içinde.
- **adviSU runtime:** `analysis/adapted/guardrails.py`, `confidence.py`, `language.py`; `_BM25` → `lexical.py` + `analysis/context.py`; `rows_to_csv/rows_to_xlsx` → `exports.py`; `content_hash_text/source_id_for` → `identity.py`; LocaleContext → frontend. UsageMeter ratio uyarlaması Aşama4 sadeleştirmesinde gerçek request status ile değiştirildi; ratio artık runtime reuse sayılmaz. Domain ayarları akademik sistemden analytics'e uyarlandı; sadece benzer isimli yeniden yazım değildir.
- **adviSU adapte/testli ama canlı değil:** `providers.py` gerçek transport/retry/deadline/circuit/stream sanitizer gövdeleri, MockTransport testleri. HF ProviderSpec/Settings ve `analysis/llm.py` gerçek çağrıya bağlandı. Kullanıcı seçerse strict intent/scope planı alınır; model SQL/Python/olgusal prose çalıştırmaz. Gerçek HF çağrısı HTTP402; başarılı model yanıtı yok. UI açık hata ile hesaplanmış standart cevabı korur. API yapılandırılmış olma durumu ile başarılı connection ayrıdır. `claim_coverage.py` lexical modülü taşındı ama runtime kullanılmıyor; sayı doğruluğu kontrolü diye sunulmaz. `identity.py` bytes/cache yardımcıları da henüz runtime kullanılmıyor.
- **PoliEco runtime:** `adapted/networks.py` zscore_frame/build_sparse_signed_graph; `adapted/temporal.py` stage_months/owner_concentration_hhi/build_party_affinity/negative_edge_share gövdeleri. Siyasi adlandırmalara verilen ürün/ülke eşlemesi kayıtlı; ideoloji/IO/global RNG taşınmadı. İki kutuplu gatekeeper kodu adapte fakat generic ürün skorunda kullanılmıyor.
- **Yeni hedef kod:** `analysis/claims.py` beyan edilmiş metric/dimension/unit/rank sayılarını artifact'a çözer ve adviSU confidence'a verir; serbest LLM metin entailment verifier değildir. `layout.py` collision-spaced yerleşim ve pozitif bağlardan cohesion; `temporal.py` invoice bootstrap ve sabit ürün evreni yeni uygulama kodudur.
- **SNIPS ve Influencer:** `docs/phases/ML_REUSE_RESEARCH.md` + `ML_SOURCE_INVENTORY.json` tam dosya/hücre/fonksiyon/hash incelemesi. SNIPS tokenizer'ın train+valid+test'e fit edilmesi ve padded last state; Influencer SMOTE-before-CV, validation'a fit_transform ve gelecek bilgi sızıntısı riskleri kaynakla bulunup düzeltme yolu yazıldı. Henüz eğitim/runtime adaptasyonu yok. Model paketi train-only preprocessing/group-time split/untouched holdout olmadan kapanmaz.
- Ek adviSU conversation_memory/response_formatter/source_indexer/file_lifecycle/retrieval_policy ve PoliEco robustness adayları `EXTRA_REUSE_RESEARCH.md/.json`, `ML_REUSE_RESEARCH.md` ve NEXT_BACKLOG içinde. Araştırılan aday, çalışır özellik olarak sayılmaz.

`analysis/verify_sources.py` pinned upstream hash'lerini read-only doğrular; 10 dosya eşleşti. **`analysis/port_sources.py` adaptasyonları overwrite edebilir; körlemesine tekrar çalıştırma.** Kaynak commit lisans/attribution notlarını ve hedef testlerini koru.

## Teknik yol haritası — önce bu dosyalara bak

| Konu | Repo köküne göre dosyalar |
|---|---|
| Veri hazırlama | `analysis/prepare.py`, `analysis/data/demo_retail.csv`, `analysis/data/demo_oracle.json`, `analysis/.local/` ignored DuckDB/metadata |
| Hesap / provenance / soru | `analysis/worker.py`, `claims.py`, `context.py`, `layout.py`, `temporal.py`, `sql_lab.py` (`compare_results` burada) (hepsi analysis/ altında) |
| Adaptörler / kaynak kanıtı | `analysis/adapted/`, `analysis/SOURCE_LEDGER.json`, `verify_sources.py` |
| API / kimlik | `core/src/workbench.ts`, `server.ts`, `spa.ts`; `core/migrations/0017_analyst_workspace.sql`, `0018_workbench_queries.sql` |
| UI | `core/web/src/workbench/Workbench.tsx`, `ExpertTools.tsx`, `TemporalView.tsx`, `Locale.tsx`, `UsageMeter.tsx`, `types.ts`, `csv.ts`, `workbench.css` |
| Uygulama entegrasyonu | `core/web/src/App.tsx`, `app.css`, `core/web/build.mjs`; `core/src/devidp.ts` optional bindHost sadece fixture'da loopback |
| Test | `analysis/tests/`, `core/test/workbench.test.ts`, `workbench-csv.test.ts`; mevcut auth/KB/property regresyonu |
| Çalıştırma | `deploy/phase1/start.sh`, `start.mjs`; sabit sürümler `analysis/requirements.txt` + root constraints |
| Ürün/test/devam | `docs/phases/TEST_GUIDE.md`, `UX_DECISIONS.md`, `PHASE_1–4*.md`, `NEXT_BACKLOG.md`; `specs/analyst-workspace-phase1–3.md` |

Not: Yukarıdaki kompakt tabloda bazı Python dosyaları aynı `analysis/` kökünü paylaşır; gerçek tam yolları rg --files ile kontrol et. Frontend build çıktıları generated/ignored'dır; kaynağı değiştirip build et.

## Veri sözleşmesi — sayıları uydurma

**Sentetik demo:** seed 47, 542 ham / 540 geçerli satır, 180 sipariş, 1.639 adet, 2.140.500 pence = £21.405,00, AOV £118,92; France £7.031,10 / 60 sipariş. Oracle pandas/worker'dan bağımsız stdlib Decimal ve basket hesaplarıyla doğrulanır. Demo gerçek şirket verisi diye sunulmaz.

**Gerçek açık veri:** UCI Online Retail, Daqing Chen, DOI10.24432/C5BW33, CC BY4.0, https://archive.ics.uci.edu/dataset/352/online+retail . 2010-12-01–2011-12-09 tarihsel veri; 541.909 ham / 530.104 dahil satır. Toplam **£10.666.684,54 / 19.960 sipariş / 5.588.376 adet / 3.922 ürün kodu**. Kaynak zip hash'i metadata içinde. Pozitif quantity/price ve geçerli tarih/invoice/product; iptal/iade dışlanır. Duplicate 5.268 satır korunur, raporlanır. Kalite flag sayıları örtüşebilir; toplam dışlanan 11.805 satır. Ham müşteri id hashlenir; preview/SQL view'a verilmez.

Brüt satış satır seviyesinde GBP kuruşuna yuvarlanır; net gelir veya kâr değildir. Kargo/hizmet/Manual satırları korunur ve kullanıcıya kapsam notu gösterilir. Fiziksel ürün/hizmet sınıflandırması henüz yapılmadı. İlk/son ay kısmi olabilir; dönem coverage metadata ve filtre tarih uçlarına dayanır, aradaki her gün tam kaydedildi demek değildir.

CSV içe aktarma mevcut retail schema/GBP/UTF-8 ile sınırlı: 2 MB / 10.000 satır, birim fiyat en fazla dört ondalık basamak; fazlası sessizce yuvarlanmadan reddedilir. Formül metinleri boşluk/BOM/control dahil güvenli dışa aktarılır; numeric Excel hücreleri numeric kalır. SQL en fazla 500 satır / 30 kolon; standart CSV önizleme ilk 30 satırdır.

## Analitik ve güvenlik sınırları

- Dört ana görevde aynı OIDC/CSRF/session ve analyst/ops rolleri; dataset/run/query için owner scope. Bütün worker yollarında actor1/global3 ortak admission + aynı DB için cross-process PostgreSQL advisory permits; disconnect worker kill. Dağıtık job queue/SLA değildir. Owner run archive/restore auditlidir; source/result silmez. Dataset/query retention ve tenant RLS açık.
- Salt okunur SQL: Alper validator + AST/functions izin listesi; müşteri id/dış dosya/ağ/catalog/join/recursive erişimi reddedilir. DuckDB read_only + external access off, memory 128 MB, 1 thread, no spill, 5 saniye interrupt. Bütün Python process'i için OS hard memory limiti değildir. Worker timeout 45 saniye / output 5 MB.
- Ana graph top 24 ürün / en güçlü 150 kenar; derece/betweenness yalnız görünür subgraph'ta unweighted. Cohesion toplulukları yalnız pozitif bağlardan. Similarity ülke satış profiline dayanır; tek ülke kaldığında kenar üretilmez. Co-purchase aynı invoice içinde DISTINCT ürün; nedensellik değildir.
- Dönem graph aynı en fazla 24 ürün evrenini üç pencerenin birleşiminden seçer; 276 çift sınırı. Jaccard empty union'da null. AOV iid invoice bootstrap seed 47 / 200 tekrar, n 20–50.000; dışındaysa neden gösterilir. Cluster/time uncertainty veya etki testi değildir.
- Recipe `retail-analysis-v4`, metric `retail-v1`. v1 summary, v2 daha geniş sonuç, v3 yerleşim/signed community, v4 hesap source/dependency fingerprint + plan identity; eski kayıtlar overwrite edilmez. Yeni digest summary/series/rankings/preview/graph/answer ve build/planı kapsar; telemetry zaman/token değerleri digest dışında. Fingerprint analiz Python kaynakları + listed root dependency inputs + core route kodudur; OS/container/driver attestation değildir. Custom SQL sabit sıra için ORDER BY ister.
- Net/profit/why/predict desteklenmez; ağ/zaman sorusu ilgili araca yönlenir. Policy-refused prompt title/rerun recipe'ye yazılmaz; bu genel DLP garantisi değildir. LLM soru bazında kapalı başlar; seçimle soru+sabit policy HF'e gider, veri satırı/sonucu gitmez. Anahtar environment veya mode0600 ignored `analysis/.local/hf-provider.json` içindedir; değeri okuma/ekrana/loga/Git'e yazma. Gerçek inference402 çözülmeden live model başarısı iddia etme.
- Üretim IdP/tenant RLS/retention ve dağıtık kuyruk/load test eksik. Yerel demo güvenliğini production sertifikası diye sunma. İngilizce bazı veri/metot metinleri ve dev login ekranı polish bekler.

## Runtime ve tekrar çalıştırma

Bağımsız `.venv` repo içindedir; symlink değildir. Native Homebrew PostgreSQL16 127.0.0.1:5549, data `analysis/.local/postgres`, DB `contextlayer_phase1`, timezone UTC. Fixture DB parolası `phase1-local-only`. Global brew service açılmadı. Core 8123 / IdP 8188 yalnız loopback. Docker bu app için gerekli değil; daemon yanıt vermediği için başka projelerin konteynerlerini restart etme.

Repo Node >=22 ister; doğrulanan bundled runtime Node 24, dizini `/Users/selmanyilmaz/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin`. Başlatıcı gerekli sürümü/DB/veri/build'i hazırlar. Sağlıklı servis varsa tekrar başlatmaz. Core restart dev IdP key'lerini değiştirir; tekrar giriş gerekebilir. Python worker dosyası her istekte okunur; frontend değişikliği build+reload ister.

```
cd /Users/selmanyilmaz/Projects/context-layer
./deploy/phase1/start.sh
```

Yeni ortamda Python kurulumu gerekiyorsa (mevcut .venv'i gereksiz yere yeniden kurma):

```
.venv/bin/python -m pip install -c constraints.txt -e '.[dev]' -r analysis/requirements.txt
```

Test komutları ve 10 dakikalık gerçek kullanıcı turu `docs/phases/TEST_GUIDE.md` içinde. Yeni test eklersen rapordaki sayıyı gerçek logdan güncelle; yalnız paket yüklenmesini test başarısı sayma.

## Son doğrulama — kalıcı loglar ve açık hata

- **142 analitik Python testi geçti**, `docs/evidence/verification/phase4-python.log`. Bunlara 50 offline plan-contract fixture dahildir; canlı model accuracy değildir.
- **45 ilgili core/CSV testi / 5 dosya geçti**, `phase4-core.log`: workbench14, csv2, KB Health13, auth12, property4. Son brand route/core doğrulaması da bu release kapısında. Gerçek auth/CSRF/owner/SQL/export/compare/temporal/rol revocation/prompt persistence kontrolleri.
- Core/web build, web TypeScript noEmit, diff whitespace geçti. Son Gemini navigation SVG/request-state değişimi sonrası build/typecheck tekrar geçti. Boyut phase4-build.log içinde; production p95 benchmark'ı değil.
- 10 pinned upstream dosya SHA doğrulaması geçti; `source-verification.log`.
- Geniş Python **856 pass / 17 skip**, Aşama 1 tarihsel baseline logu `phase1-full-python.log`; sonraki değişiklikler için bütün repo tekrar koşulmuş demek değil.
- Geniş core ilk koşu 438 pass / 19 skip / 8 fail + 2 setup errors. UTC dashboard-extract7, lisans/KB13 ve normatif coalescing property4 düzeltilip tekrar geçti. Queue production kodu değişmedi. **Kalan Docker bağımlı sync-drill, sync-run ve mcp-execute snapshot-advance testleri doğrulanamadı**: daemon yanıt vermiyor, ephemeral snapshot/PR/timeouts. Ayrıntı PHASE_1_REPORT. Bütün suite yeşil diye raporlama; daemon sağlıklı olduğunda bu kapıyı yeniden çalıştır.
- Gerçek browser: login, demo/UCI, filtre, kaydet/aç/yeniden çalıştır, CSV import, SQL/BM25/compare, JSON ve Excel indirip yeniden okuma, Cmd-K otomatik focus, Esc, 390px belge genişliği, 24 node/150 edge tablo alternatifi, zaman analizi. Tam WCAG/pilot değil.
- İncelenmiş son ekranlar `docs/evidence/phase4/02-overview.jpeg`, `03-analysis.jpeg`, `04-network.jpeg`, `05-temporal.jpeg`, `06-mobile.jpeg`, `07-findings.jpeg`, `08-library-empty.jpeg`, `overview-delivery.jpeg` (hepsi phase4 altında). Önceki Aşama3 kanıtı `docs/evidence/workspace-overview.jpeg`, `phase3/uci-temporal-final.png`, `phase3/mobile-final.png`. `phase3/uci-temporal.png` ara QA; final diye kullanma. Önceki ekranlar araştırma arşivinde evidence/phase1–3.

## Sonraki ajana birkaç örnek

**“progress.md'yi oku ve Aşama 2'yi yap.”** Aşama 2 zaten yerel kabul tamam. PHASE_2_REPORT ve mevcut SQL/arama/export/compare testlerini oku; ilk eksik/doğrulanamayan kapıyı bildir, aynı özelliği baştan yazma. Kullanıcı iyileştirme istiyorsa yeni dar kapsam/test kanıtı ekle.

**“Aşama 4'e devam et.”** Önce PHASE_4_REPORT açık kapılarını kontrol et. Admission/cancel/fingerprint/run archive zaten uygulandı; yeniden yapma. Gerçek HTTP402 kredi kapısı açık; model kalitesi değil fixture kontratları test edildi. Production IdP/tenant/RLS, dataset/query retention, HTTP/cancel stress/5M/50M ve UX pilotu kalan işlerdir. Eksik dış koşulu varsayma; bağımsız teknik paketi testleyip gerçek sonucu raporla.

**“Influencer kodunu kullan.”** ML_REUSE_RESEARCH ve envanterde gerçek notebook/hücreyi bul; target/decision time/group-time split/holdout'u önce yaz. SMOTE/scaler yalnız train fold'a fit edilir; güncel/gelecek aggregate ve test üstünde model seçimi aktarılmaz. Modülü test+model card ile kapat, sadece import edilmiş kodu runtime başarı sayma.

**“Nerede kaldık / bir önceki aşamayı göster.”** Yerel URL, doğrulanmış üç aşama ve PHASE_3_REPORT karşılaştırmasını ver. 78 uzman puanını measured industry win diye sunma. Test sayısını logdan al; hedef puanı mevcut sonuçla karıştırma.

LLM planı aynı değilse replay digest değişebilir; temperature0 plan determinism garantisi değildir. Donmuş plan replay modu/live eval açık.

## Aşama 4 uygulama giriş haritası ve yayın kartı

- `analysis/llm.py`: config/status, static policy, strict plan validation, safe telemetry ve failure fallback. HF token server-side; çalışma config'i ignored0600, sadece izin ve varlık kontrolü yap. `analysis/adapted/providers.py` HF adaptasyonu, `worker.py` use_llm opt-in/claim/digest; `fingerprint.py` kaynak listesi.
- `core/src/workbench.ts`: AsyncLocalStorage cancel signal, PG subject/global advisory permits, catalog/import dahil shared admission, /runs/:id/archive. Migration `0019_workbench_lifecycle.sql`; eskileri değiştirme.
- `core/web/src/workbench/assets/`: iki Gemini JPEG + dört geometry-only SVG, PROVENANCE.md. `core/web/build.mjs` hash'li file loader, `core/src/spa.ts` dar static asset route. `UsageMeter.tsx` artık quota değil request status. Giriş fixture ekranı da sadeleştirildi.
- `analysis/tests/test_phase4.py`, `core/test/workbench.test.ts`, `tests/test_brand_assets.py`, `tests/test_nul_scan.py` A4 test girişleri. `tools/nul_scan.py` yalnız exact PNG/JPEG exceptions; yeni screenshot ekleyince manifest/exceptions güncelle. `.github/workflows/tests.yml` offline analytics ve core fixture hazırlama ekli; secret/paid inference CI'ya girmez.
- `docs/evidence/ASSET_MANIFEST.json` gerçek screenshot/artwork hash'leri; `docs/evidence/verification/phase4-*` actual test/build/load/provider receipts. `analysis.benchmark` 0.53M full-graph subprocess için 1/3 concurrency, 12'şer gözlem, hata0; küçük örnek gözlemi, HTTP/production/memory ölçümü değil.
- Yeni `Perakende satış özeti` QA kaydı görünür/restore durumda; önceki kendi Aşama1 demo fixture bulgusu arşivde, geri alınabilir. İlgisiz kayıt silinmedi. Varsayılan dataset UCI; örnek veri Perakende örneği, source modalında sentetik olduğunu korur.
- Git hedefi **https://github.com/mesely/DataAnalyticsToolv2**, branch **feat/analytics-workspace-phase4**. `origin` AlperCamli read-only korunur; `publish` meselyv2 remote. Repo normu PR review; main merge veya production deploy otomatik yapılmaz. Son yayın sonucu aşağıdaki kartta güncellenir.

**Yayın kartı:** GitHub push başarılı; PR https://github.com/mesely/DataAnalyticsToolv2/pull/1 açık. README/ekranlar dalda: https://github.com/mesely/DataAnalyticsToolv2/tree/feat/analytics-workspace-phase4 . Main merge/production deploy yapılmadı. Secret scan geçti; token ignored0600. Uzak CI çalışıyor, sonucu geçmiş sayma. Yerel 142 analitik +45 core/CSV +15 asset/NUL kapısı geçti. CI'da .venv olmadığı için CORE_ANALYSIS_PYTHON=python açıkça ayarlandı.

## SON ANKOR — devam etmeden önce

**Aşama 1–3 tamam. Aşama 4 yerel uygulaması tamam; canlı Llama402/üretim dış kabul açık.** Kod `/Users/selmanyilmaz/Projects/context-layer`; URL http://127.0.0.1:8123/app/ ; `selman` / `analiz-demo`. İlk sonraki iş PHASE_4_REPORT açık kapıları ve NEXT_BACKLOG. Yeni Aşama5 genel veri/ML, Aşama6 BI/pilot henüz başlamadı. Kaynak bağlantıları/commitler üst tabloda; token değeri hiçbir devir/yayın dosyasına girmez. Üst/son kartı ve gerçek test/PR durumunu birlikte güncelle.
