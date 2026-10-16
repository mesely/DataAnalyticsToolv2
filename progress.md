# Context Layer / Analytics — tek giriş ve devir rehberi

## ŞİMDİ OKU — 16 Ekim 2026, öğleden sonra turu (AW-14, yeni ajan)

**Güncel kod: bu kartın altındaki commitler (e4f82af ve sonrası), publish dalına push edildi; CI sonucu aşağıdaki
satırda.** Başlangıç durumu doğrulandı: 59aa444 CI 5 job yeşil; 228 analitik test yerelde geçti; uygulama ayaktaydı;
disk 3,2 GB boş (98 %). Bu turda silinenler yalnız yeniden üretilebilir önbellekler: npm cache 151 MB, repo
`__pycache__` 3,7 MB, clang modül önbelleği 221 MB → 3,6 GB boş. Claude ShipIt güncelleme önbelleği (619 MB), Chrome
önbelleği (1 GB), CoreDevice/Simulator/Docker verileri bilerek silinmedi.

**Yapılanlar (spec `specs/analyst-workspace-phase11.md`, rapor `docs/phases/PHASE_11_REPORT.md`):**
1. Tahmin bandı v3 (`weekly-gross-v3`): absolute/relative ölçek yalnız geliştirme yuvarlanan kapsamasıyla seçilir,
   sonlu-örneklem conformal kuantil, `band_undercovers_development`; UCI %90 bandı geliştirmede 0,85 (eski 0,77),
   final 0,70 — **kalibre değil** etiketi korunur. Lider ülke dilimleri (UK/NL/EIRE) aynı final origin'lerde: üçünde
   de mean8 naifi geçti. UI "son dört" sabit metni dinamik oldu. Kanıt `docs/evidence/phase10/forecast-v3-uci.json`.
2. Tipli analist anlatısı (`analysis/narrative.py`, decision-narrative-v1): yerel renderer + doğrulanmış model
   anlatısı (bilinmeyen kimlik / desteklenmeyen sayı / atıfsız olgu / aday olmayan öneri / eksik kanıt hakkında olgu
   reddedilir; bir onarım; yerel korunur). DecisionStudio "Analist anlatısı" + kanıt paketi XML. Harness v2 narrate
   satırı; **gerçek model hâlâ BLOCKED (402)** — accuracy null.
3. Alım v2 (`csv-preparation-v2`): Parquet (DuckDB), `decimal_comma`, `date_format`, sütun teşhisleri, Windows-1252
   notu; her seçenek receipt'te. Rotalar `parquet_base64` kabul eder.
4. ML kartı `probabilistic` (log loss/Brier/ECE/AP) seçimden sonra; ModelStudio tablosu.
5. Worker başlangıcı: `analysis.prepare` pandas importu fonksiyon içine → import 0,9 s → 0,1 s; forecast p50 882 → 130 ms
   (`docs/evidence/verification/phase11-performance.json`). Decisions ~2,1 s (sonraki hedef).

**Testler:** analytics **254 passed**; NUL/asset 48; web tsc/build geçti. Core `workbench.test.ts` yerelde Docker
fixture nedeniyle koşmaz (CI'da koşar).

**Açık kalan (bu tur):** tarayıcı kabulü (DecisionStudio anlatı/dilim tablosu/dinamik final metni, hazırlama seçenekleri,
390 px, açık/koyu, reopen, indirme) — tarayıcı aracının güvenlik sınıflandırıcısı tur boyunca erişilemezdi; mock
üretilmedi; `phase11-browser-qa.json` yok. Sonraki ajan: önce gerçek tarayıcıyla kapat, sonra CI'yı doğrula
(`gh run list --repo mesely/DataAnalyticsToolv2`), sonra NEXT_BACKLOG sırası. Uygulamayı yeniden başlatmak için
mevcut `node deploy/phase1/start.mjs` sürecini durdurup `./deploy/phase1/start.sh` çalıştır (web/dist statik servis
edilir; TS rota değişikliği restart ister).

---

## ÖNCEKİ KART — 16 Ekim 2026, gece turu (yeni ajan)

**Güncel kod: bu kartın altındaki commit (forecast v2).** Önceki turun A7–10 devir dokümanları commit edilmemişti; 86e3a7f ile
commit/push edildi (PR #1, CI tetiklendi). Gerçek başlangıç durumu: HEAD fddc4f1 = son yeşil CI (5 job). 207 analitik test
yerelde geçti; 48 asset/NUL testi geçti; 12 pinned kaynak doğrulandı; web tsc/build geçti. **Core Node testleri yerelde
Docker olmadan 3 suite'te `source_unavailable` ile düşer (connector fixture `postgres:16` konteyneri ister); bu ortam
sınırıdır, CI'da koşar.** Uygulama `./deploy/phase1/start.sh` ile ayağa kalktı; PostgreSQL locale'siz kabuktan
"postmaster became multithreaded" ile başlayamıyordu → start.sh artık `LC_ALL/LANG=C` varsayar (gerçek düzeltme).

**Disk:** tur başında kap 290 MB boş (swap 5,6 GB kullanımda). Silinen yalnız yeniden üretilebilir önbellekler:
Codex Sparkle güncelleme önbelleği 1,6 GB, Xcode DerivedData 886 MB, SwiftPM 534 MB, pip 32 MB → ~2,3 GB; sonra 3,2 GB boş.
Kullanıcı verisi, simülatör cihazları, Chrome profili, iCloud, Gradle/pub önbellekleri silinmedi.

**Tahmin v2 (`weekly-gross-v2`, P1 düzeltmesi):** eski sürüm yalnız naive/mean4 ve son-4 holdout'tu; mean4 o pencerede
naiften kötüydü. Yeni protokol: kayıtlı adaylar (naive, seasonal_naive ≥104 hafta, drift, mean2/4/8, SES ×3, sönümlü
Holt ×2), seçim **yalnız geliştirme origin'lerinde**, final pencere son min(12,max(4,n//5)) origin seçimden sonra her aday
için hesaplanır; MAE/RMSE/WAPE/sMAPE/MASE/bias; teşhisler; %80/%90 ampirik bant + betimsel final kapsaması. UCI 52 hafta:
geliştirmede **mean8** seçildi; final (10 origin) MAE £47.207 / naif £59.859 (MASE 1,42 / 1,80, +%21); bant kapsaması 0,70
→ kalibre değil. Tablo PHASE_7_REPORT güncelleme bölümünde; kanıt `docs/evidence/phase10/forecast-v2-uci.json`.
UI: yöntem etiketleri, dinamik "N dönem", teşhis listesi (DecisionStudio). Testler: `analysis/tests/test_forecast.py` (9) +
güncellenen test_decisions → 216 analitik test. Eski mean4/naif son-4 sayıları tarihsel; iki protokol farklı pencere ölçer.

**LLM değerlendirme harness'i (P1):** `analysis/llm_eval` — 19 plan / 6 decide / 8 claims vakası, scripted
self-check + deterministik `local` baseline + gerçek `hf` probu (402 → **BLOCKED**, metrik yok). Rapor
`docs/phases/LLM_EVALUATION.md`, kanıt `docs/evidence/phase10/llm-eval.json`. Harness bir koruyucu açığı buldu ve
kapattı (API token / hidden rules çıkarma ifadeleri planner'a ulaşıyordu; `guardrails.py` + regresyon testi).
Yerel baseline davranış doğruluğu 13/19; gerçek model doğruluğu hâlâ **null**.

**Açık kalan (bu tur):** DecisionStudio tarayıcı kabulü (reopen/390px/tema/CmdK/Esc/indirme) tarayıcı araçlarının geçici
kesintisi nedeniyle henüz yapılmadı — mock üretme, gerçek ekranla kapat. LLM değerlendirme harness'i (golden set +
evaluator + rapor) sonraki P1 iş; HF 402 sürüyor, canlı accuracy **null**.

---

## ÖNCEKİ KART — 16 Ekim 2026 (A7–10 teslimi)

**Güncel kod: fddc4f1 (A7–10 tahmin/karar/tema ek paketleri).** A1–6 uygulanmış ürünün üzerine one-week forecast, kanıta bağlı karar stüdyosu, XML yöntem bağlamı, owner karar arşivi, gerçek adviSU özetleyici ve Gemini ikon/appearance sistemi eklendi. **Bu, eski geniş A7–10 backlog'un tamamının kapandığı anlamına gelmez.** Parquet/OOF/tenantRLS/retention/hard-isolation/5MHTTP/liveBI/genel conversation-reference/gerçek kullanıcı pilotu açık. Ayrıntı PHASE_7..10_REPORT ve NEXT_BACKLOG. 207 analytics test,48asset/NULtest, webbuild/tsc ve12 upstreamSHA yerelde geçti. Son GitHub CI ve final browser receipt aşağıdaki güncel kartta tutulur; önceki041982c durumunu güncel kod sonucu diye aktarma.

**Tek uygulama kökü:** `/Users/selmanyilmaz/Projects/context-layer`. Yayın hedefi `mesely/DataAnalyticsToolv2`, dal `feat/analytics-workspace-phase4`; PR üzerinden review. Son Git sonucu bu dosyanın yayın kartındadır. Production deploy/main merge yapılmadı. Başlangıç HEAD `0aaac741fd36d0e5b4f0c182d1b8b05c87884c17`.

**Çalışan uygulama:** http://127.0.0.1:8123/app/ — `selman` / `analiz-demo`. İkinci kimlik `alper` / aynı parola; `viewer` aynı parolayla yetkisiz rol testidir. Bunlar yalnız yerel fixture hesaplarıdır. Yeni başlangıç: repo kökünden `./deploy/phase1/start.sh`.

**GitHub teslimi:** [PR #1](https://github.com/mesely/DataAnalyticsToolv2/pull/1) · [Ürün README ve ekranlar](https://github.com/mesely/DataAnalyticsToolv2/tree/feat/analytics-workspace-phase4).

**İlk devam hareketi:** bu üst kart → `docs/phases/PHASE_10_REPORT.md` → `NEXT_BACKLOG.md` → son CI/browser receipt. A7–10 specs AW-10–13 olarak önce yazıldı. Şu turda kalan kabul: son kod CI, yeni decision-dialog aynı kayıt reopen reset/mobil/keyboard/appearance, metadata/README görsel linkleri ve final secret/manifest/NUL kontrolü. Eksik kapıyı tamamla; çalışan ekranları baştan yazma. HF hem yeni tokenlı gerçek planner probe'da hem UCI karar-XML opt-in akışında402döndü; model accuracy **null**. Ödeme/hesap yetkisi değişikliği yapma.

## Güncel A7–10 teknik giriş kartı

| İş | Gerçek dosya ve kontrat |
|---|---|
| Haftalık tahmin | `analysis/forecast.py`;16–260tamhafta; development-onlynaive/mean4 seçimi; son4rollingorigin holdout; ampirik uncalibrated band; no-data state |
| Karar/strateji | `analysis/decisions.py`; current filters + data/build hash; quality/country/basket/forecast/scenario adayları; support40+20+20+20; business validation0; stabil skor sonra objective tie-order |
| XML/BM25/LLM | `analysis/knowledge/business-methods.json`; original authored yöntem notları + kaynakURL/SHA; gerçek adviSU BM25top3; XML16KBserializer; front+end instruction/few-shot; yalnız adayID/reason JSON; ham satır/ürün/ülke adı yok; opt-inHF |
| Gerçek ek reuse | `analysis/adapted/formatting.py`; adviSU `_plain_text/split_summary/compact_summary` gövdeleri runtime; pinnedSHAledger12dosya. XML/scenario/forecast yenihedefkod, kaynak kopyası diye sayma |
| API/DB | `core/src/workbench.ts`; POST `/v1/dashboard/workbench/forecast`, POST `/decisions`; GET `/decisions`, `/decisions/:id`; viewer/CSRF/permission/bounded/PGpermit/audit; migration `0021_workbench_decisions.sql` |
| UI | `core/web/src/workbench/DecisionStudio.tsx`, `BrandIcons.tsx`, `Workbench.tsx`, `workbench.css`; dört nav; CmdK; immutable history; MD/JSON/XML; evidence inspector; revisionkey aynıIDreopen scroll/disclosure reset |
| Görsel kaynak | `assets/app-icon.jpeg`,33yeniSVG(brand dahil), toplam6raster/37SVG; Gemini chat `https://gemini.google.com/app/4d72a457fda047a0`; turnsSVGd84c79b3d1f6bdd1/app8207fba35dc491ed/utilb5f9739aad87714f; PROVENANCE.md |
| Appearance | `data-theme=light/dark`; OS başlangıcı + bellekte toggle; D103.1 browser persistence yasağı korunur; lacivert/füme; düz kaynak metni; measured contrast ve44px topcontrols |
| Test/ölçüm | `analysis/tests/test_decisions.py`33yeni; tüm analytics207; `analysis/evaluate_decisions.py`; worker36/36başarı, HTTP/OIDC/PG/browser/HFhariç; actual JSON `docs/evidence/verification/phase10-performance.json` |
| Rapor/rehber | `docs/phases/PHASE_7_REPORT.md`..`PHASE_10_REPORT.md`, `TEST_GUIDE.md`; UCI actual JSON/MD/XML `docs/evidence/phase10/` |

**Değişmez sayılar (v1 protokolü, tarihsel):** UCI52tamhafta; mean4holdoutMAE£55,787.19, naive£41,723.39. Seçilen model **daha kötü**; test görülünce seçim değiştirilmez, UI uyarır/temporal puan0. Band kalibre değil. Son tam hafta£324,370.83; varsayımsal5%volume/0%price →£340,589.37, fark£16,218.54. Grossdelta kâr/ROI/causal uplift değildir. Dayanak60/100, %60doğruluk değildir.

**Yeni prompt sınırı:** model sadece odak seçer; serbest strateji metni/SQL/metric/score üretemez. Açıklama/adımlar/hesap/atıflar yereldir. “LLM tüm iş kararlarını doğruladı” deme. Arbitrary businessdocupload veya generalfreeproseentailment henüz yok. Sonraki genişleme source/privacy/owner/eval sözleşmesi ister.

## Kullanıcının amacı ve yetki

Alper'in DataAnalyticsTool / Context Layer projesini Selman'ın adviSU ve PoliEco kodlarını gerçekten adapte ederek güçlü, kolay kullanılan, LLM'e hazır bütüncül analytics ürününe dönüştürmek. Sadece esinlenmek yeterli değil. Kaynak commit/dosya/sembol → hedef → değişiklik → runtime kullanımı → test kanıtı kaydedilir. Her kaynak zorla ürüne sokulmaz; LSTM ancak ölçülmüş fayda varsa.

Kullanıcı başlangıçta analiz/kodsuz hazırlık istedi; sonraki açık talebi yerel geliştirmeyi, aşamaları uygulamayı, çalıştırmayı, test verisi/rehberini ve önce/sonra karşılaştırmasını yetkilendirdi. Kalite korunarak sonraki aşamalara devam edilebilir. Rutin yerel kararlar için tekrar soru gerekmez. Son kullanıcı mesajı ayrıca sağladığı HF token ile Llama entegrasyonu/gerçek sınırlı probe, oturumu açık Gemini ile özgün asset ve GitHub push yetkisini verdi. HF ödeme/paket değişikliği, gerçek müşteri bağlantısı ve production yayın yapılmadı; kapsam olmadan varsayılmaz. Token değeri bu dosyada/Git içinde bulunmaz.

UI/UX merkezi gereksinim: Hick–Hyman doğrultusunda dört ana görev ve kademeli uzman araçları; Fitts doğrultusunda ulaşılabilir hedefler/yakın eylemler; tutarlı boşluk/renk/tipografi/ikon, klavye ve görünür focus/durum/hata. Bunlar tasarım kararlarıdır; görevli kullanıcı ölçümü ve tam WCAG denetimi olmadan başarı oranı/sertifika iddia edilmez. Güncel: Gemini web üretimi6raster/37SVG, ürünikonu ve utility ailesi; lacivert/füme darkmode eklendi. Görsel kaynak ve exactfile hash manifesti korunur. Asset gerekirse işlevsel anlam ve erişilebilirlik korunur.

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
| 5 / CSV hazırlama | Genel CSV profil, identifier koruma, açık retail/GBP eşleme, dönüşüm önizle/geri al, receipt ile doğrulanmış import | `docs/phases/PHASE_5.md`, `PHASE_5_REPORT.md`, `specs/analyst-workspace-phase5.md` |
| 6 / ML deneyi ve görsel genişletme | Train-only CV, baseline/RF/linear, random/group/time, sayısal fold-içi SMOTE, gerçek holdout ve owner kart; Influencer adaptasyonu; üç ek Gemini görsel | `docs/phases/PHASE_6.md`, `PHASE_6_REPORT.md`, `specs/analyst-workspace-phase6.md` |

Aşama 3'ün sözleşmeyle seçilmiş kapsamı betimleyici zaman/ağ analizidir; model eğitimi zorla eklenmedi. “Aşama 3 tamam” demek “SNIPS/Influencer modelleri eğitildi” demek değildir. T01–T26'nın tamamı veya bütün kaynakların entegrasyonu kapanmış sayılmaz.

Başlangıç uzman değerlendirmesi **60,78≈61/100**; Aşama 1 **73**, Aşama 2 **yaklaşık 76**, Aşama 3 **77,74≈78**. Aynı ağırlıklar ve kriter tablosu PHASE_3_REPORT içinde. Bunlar geçici uzman puanları; deneysel UX/pazar benchmark'ı değil. 92 hedef, elde edilmiş sonuç değil. Sonraki katkı tahminleri NEXT_BACKLOG tablosunda büyükten küçüğe; puanlar toplamsal garanti değildir.

## Gerçek yeniden kullanım — ne çalışıyor, ne henüz çalışmıyor

Tam kayıt `docs/phases/REUSE_LEDGER.md`, kaynak SHA/commit/semboller `analysis/SOURCE_LEDGER.json`.

- **Alper:** Fastify/Postgres/OIDC/CSRF/rol/audit/migration/SPA altyapısı ve `sqlval.validate_statement` gerçekten kullanılır. Eski yönetim ekranı korunur. Yeni motor public veya owner-uploaded materyalize veriyi hesaplar; canlı execute_sql token yolunu bypass etmez. Generator deterministik ve LLM'siz kalır. Ürün ek kararı `docs/phases/PRODUCT_EXTENSION.md`, HLR/specs ve DECISIONS içinde.
- **adviSU runtime:** `analysis/adapted/guardrails.py`, `confidence.py`, `language.py`; `_BM25` → `lexical.py` + `analysis/context.py`; `rows_to_csv/rows_to_xlsx` → `exports.py`; `content_hash_text/source_id_for` → `identity.py`; LocaleContext → frontend. UsageMeter ratio uyarlaması Aşama4 sadeleştirmesinde gerçek request status ile değiştirildi; ratio artık runtime reuse sayılmaz. Domain ayarları akademik sistemden analytics'e uyarlandı; sadece benzer isimli yeniden yazım değildir.
- **adviSU adapte/testli ama canlı değil:** `providers.py` gerçek transport/retry/deadline/circuit/stream sanitizer gövdeleri, MockTransport testleri. HF ProviderSpec/Settings ve `analysis/llm.py` gerçek çağrıya bağlandı. Kullanıcı seçerse strict intent/scope planı alınır; model SQL/Python/olgusal prose çalıştırmaz. Gerçek HF çağrısı HTTP402; başarılı model yanıtı yok. UI açık hata ile hesaplanmış standart cevabı korur. API yapılandırılmış olma durumu ile başarılı connection ayrıdır. `claim_coverage.py` lexical modülü taşındı ama runtime kullanılmıyor; sayı doğruluğu kontrolü diye sunulmaz. `identity.py` bytes/cache yardımcıları da henüz runtime kullanılmıyor.
- **PoliEco runtime:** `adapted/networks.py` zscore_frame/build_sparse_signed_graph; `adapted/temporal.py` stage_months/owner_concentration_hhi/build_party_affinity/negative_edge_share gövdeleri. Siyasi adlandırmalara verilen ürün/ülke eşlemesi kayıtlı; ideoloji/IO/global RNG taşınmadı. İki kutuplu gatekeeper kodu adapte fakat generic ürün skorunda kullanılmıyor.
- **Yeni hedef kod:** `analysis/claims.py` beyan edilmiş metric/dimension/unit/rank sayılarını artifact'a çözer ve adviSU confidence'a verir; serbest LLM metin entailment verifier değildir. `layout.py` collision-spaced yerleşim ve pozitif bağlardan cohesion; `temporal.py` invoice bootstrap ve sabit ürün evreni yeni uygulama kodudur.
- **Influencer artık runtime'da:** cell63 `apply_log_transform/preprocess_features` → `analysis/adapted/ml_preprocessing.py::FoldPreprocessor`; train-only schema/skew/log seçimi, ayrı fit/transform, MinMaxScaler + imputer/OHE her fold içinde. Negatif girdiler için signed-log. cell66 `log_mse_like_counts` aynı adapterda, sonlu/nonnegative guard ile özgün ölçekte RMSLE hesabı. `analysis/ml.py` yeni güvenli CV/SMOTE/RF orchestration; SMOTE/RF yaklaşımı kullanıldı diye notebook stacking gövdesi kopyalandı denmez. 18 ML testi, gerçek Wine/Diabetes holdout; source SHA 12 dosyalık ledger içinde. Cell60 domain ratio/interaction henüz taşınmadı; OOF stacking yok.
- **SNIPS araştırılmış, henüz runtime değil:** `ML_REUSE_RESEARCH.md` ve `ML_SOURCE_INVENTORY.json`. Train-only vocab/padding sorunları kayıtlı. Analytics intent baseline faydası olmadan LSTM ekleme.
- Ek adviSU conversation_memory/source_indexer/file_lifecycle/retrieval_policy ve PoliEco robustness adayları `EXTRA_REUSE_RESEARCH.md/.json`, `ML_REUSE_RESEARCH.md` ve NEXT_BACKLOG içinde. Araştırılan aday, çalışır özellik olarak sayılmaz.

`analysis/verify_sources.py` pinned upstream hash'lerini read-only doğrular; 12 dosya eşleşti. **`analysis/port_sources.py` adaptasyonları overwrite edebilir; körlemesine tekrar çalıştırma.** Kaynak commit lisans/attribution notlarını ve hedef testlerini koru.

## Teknik yol haritası — önce bu dosyalara bak

| Konu | Repo köküne göre dosyalar |
|---|---|
| Veri hazırlama | `analysis/prepare.py`, `preparation.py`, `ml.py`, `adapted/ml_preprocessing.py`, `analysis/data/demo_retail.csv`, `analysis/data/demo_oracle.json`, `analysis/.local/` ignored DuckDB/metadata |
| Hesap / provenance / soru | `analysis/worker.py`, `claims.py`, `context.py`, `layout.py`, `temporal.py`, `sql_lab.py` (`compare_results` burada) (hepsi analysis/ altında) |
| Adaptörler / kaynak kanıtı | `analysis/adapted/`, `analysis/SOURCE_LEDGER.json`, `verify_sources.py` |
| API / kimlik | `core/src/workbench.ts`, `server.ts`, `spa.ts`; `core/migrations/0017_analyst_workspace.sql`, `0018_workbench_queries.sql`, `0019_workbench_lifecycle.sql`, `0020_workbench_ml.sql` |
| UI | `core/web/src/workbench/Workbench.tsx`, `ExpertTools.tsx`, `TemporalView.tsx`, `Preparation.tsx`, `ModelStudio.tsx`, `Locale.tsx`, `UsageMeter.tsx`, `types.ts`, `csv.ts`, `workbench.css` |
| Uygulama entegrasyonu | `core/web/src/App.tsx`, `app.css`, `core/web/build.mjs`; `core/src/devidp.ts` optional bindHost sadece fixture'da loopback |
| Test | `analysis/tests/`, `core/test/workbench.test.ts`, `workbench-csv.test.ts`; mevcut auth/KB/property regresyonu |
| Çalıştırma | `deploy/phase1/start.sh`, `start.mjs`; sabit sürümler `analysis/requirements.txt` + root constraints |
| Ürün/test/devam | `docs/phases/TEST_GUIDE.md`, `UX_DECISIONS.md`, `PHASE_1–10*.md`, `NEXT_BACKLOG.md`; `specs/analyst-workspace-phase1–10.md` |

Not: Yukarıdaki kompakt tabloda bazı Python dosyaları aynı `analysis/` kökünü paylaşır; gerçek tam yolları rg --files ile kontrol et. Frontend build çıktıları generated/ignored'dır; kaynağı değiştirip build et.

## Veri sözleşmesi — sayıları uydurma

**Sentetik demo:** seed 47, 542 ham / 540 geçerli satır, 180 sipariş, 1.639 adet, 2.140.500 pence = £21.405,00, AOV £118,92; France £7.031,10 / 60 sipariş. Oracle pandas/worker'dan bağımsız stdlib Decimal ve basket hesaplarıyla doğrulanır. Demo gerçek şirket verisi diye sunulmaz.

**Gerçek açık veri:** UCI Online Retail, Daqing Chen, DOI10.24432/C5BW33, CC BY4.0, https://archive.ics.uci.edu/dataset/352/online+retail . 2010-12-01–2011-12-09 tarihsel veri; 541.909 ham / 530.104 dahil satır. Toplam **£10.666.684,54 / 19.960 sipariş / 5.588.376 adet / 3.922 ürün kodu**. Kaynak zip hash'i metadata içinde. Pozitif quantity/price ve geçerli tarih/invoice/product; iptal/iade dışlanır. Duplicate 5.268 satır korunur, raporlanır. Kalite flag sayıları örtüşebilir; toplam dışlanan 11.805 satır. Ham müşteri id hashlenir; preview/SQL view'a verilmez.

Brüt satış satır seviyesinde GBP kuruşuna yuvarlanır; net gelir veya kâr değildir. Kargo/hizmet/Manual satırları korunur ve kullanıcıya kapsam notu gösterilir. Fiziksel ürün/hizmet sınıflandırması henüz yapılmadı. İlk/son ay kısmi olabilir; dönem coverage metadata ve filtre tarih uçlarına dayanır, aradaki her gün tam kaydedildi demek değildir.

CSV artık herhangi bir schema için profil çıkarır; dashboard dönüşümü explicit retail/GBP/invoice_line eşlemesine bağlıdır. Önizleme/source/mapping/options receipt hash ile importa bağlanır; alan/dönüşüm değişirse yeniden önizle. Müşteri kodu opsiyonel, kolon değerleri generic profile dönmez. CSV sınırları: 2 MB / 10.000 satır, birim fiyat en fazla dört ondalık basamak; fazlası sessizce yuvarlanmadan reddedilir. Formül metinleri boşluk/BOM/control dahil güvenli dışa aktarılır; numeric Excel hücreleri numeric kalır. SQL en fazla 500 satır / 30 kolon; standart CSV önizleme ilk 30 satırdır.

## Analitik ve güvenlik sınırları

- Dört ana görevde aynı OIDC/CSRF/session ve analyst/ops rolleri; dataset/run/query için owner scope. Bütün worker yollarında actor1/global3 ortak admission + aynı DB için cross-process PostgreSQL advisory permits; disconnect worker kill. Dağıtık job queue/SLA değildir. Owner run archive/restore auditlidir; source/result silmez. Dataset/query retention ve tenant RLS açık.
- Salt okunur SQL: Alper validator + AST/functions izin listesi; müşteri id/dış dosya/ağ/catalog/join/recursive erişimi reddedilir. DuckDB read_only + external access off, memory 128 MB, 1 thread, no spill, 5 saniye interrupt. Bütün Python process'i için OS hard memory limiti değildir. Worker timeout 45 saniye / output 5 MB.
- Ana graph top 24 ürün / en güçlü 150 kenar; derece/betweenness yalnız görünür subgraph'ta unweighted. Cohesion toplulukları yalnız pozitif bağlardan. Similarity ülke satış profiline dayanır; tek ülke kaldığında kenar üretilmez. Co-purchase aynı invoice içinde DISTINCT ürün; nedensellik değildir.
- Dönem graph aynı en fazla 24 ürün evrenini üç pencerenin birleşiminden seçer; 276 çift sınırı. Jaccard empty union'da null. AOV iid invoice bootstrap seed 47 / 200 tekrar, n 20–50.000; dışındaysa neden gösterilir. Cluster/time uncertainty veya etki testi değildir.
- Recipe `retail-analysis-v4`, metric `retail-v1`. v1 summary, v2 daha geniş sonuç, v3 yerleşim/signed community, v4 hesap source/dependency fingerprint + plan identity; eski kayıtlar overwrite edilmez. Yeni digest summary/series/rankings/preview/graph/answer ve build/planı kapsar; telemetry zaman/token değerleri digest dışında. Fingerprint analiz Python kaynakları + listed root dependency inputs + core route kodudur; OS/container/driver attestation değildir. Custom SQL sabit sıra için ORDER BY ister.
- Standart satış asistanında net/profit/why/predict desteklenmez; ayrı Model stüdyosu kullanıcı hedefiyle sınıflama/regresyon deneyidir. Asistan geleceği tahmin ediyormuş gibi konuşmaz; ağ/zaman sorusu ilgili araca yönlenir. Policy-refused prompt title/rerun recipe'ye yazılmaz; bu genel DLP garantisi değildir. LLM soru bazında kapalı başlar; seçimle soru+sabit policy HF'e gider, veri satırı/sonucu gitmez. Anahtar environment veya mode0600 ignored `analysis/.local/hf-provider.json` içindedir; değeri okuma/ekrana/loga/Git'e yazma. Gerçek inference402 çözülmeden live model başarısı iddia etme.
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

## Son doğrulama — gerçek kanıt

- **174 analitik Python testi geçti**, `docs/evidence/verification/phase6-python.log`: önceki142 + preparation14 + ML18. 50 offline LLM plan fixture model accuracy değildir. Gerçek fit/holdout, train-only schema, unknown category, group/timestamp boundary, skewed Wine/SMOTE untouched holdout testleri dahildir.
- **GitHub e94819a koşusu BEŞ JOB YEŞİL:** https://github.com/mesely/DataAnalyticsToolv2/actions/runs/38800676565 . Core473 passed/4 skipped (477); root Python841 passed/17 skipped; analytics173 pass (son skew testinden önce). `phase6-github-ci.txt` gerçek log extract. Eski Docker bağımlı sync-drill/sync-run/mcp-execute kapısı cloud koşusuyla kapandı. Yerel Docker hazır olmayınca fixture bootstrap skip/hata verir; cloud yeşilini yerel sonuç diye yazma.
- Son görsel/ek skew testi sonrası build/web TypeScript,174 Python ve15 asset/NUL testi geçti; son kod041982c branch CI beş job success: phase6-github-final.json. Exact image/NUL guard + manifest kontrolü gerekir. Python/Node paket kurulumu test sayılmaz.
- A6 tarihinde11 pinned source dosyası doğrulandı; A7–10 sonrası12dosya doğrulandı. `analysis/verify_sources.py` read-only; `port_sources.py` adaptörleri overwrite edebilir, çalıştırma.
- A5 tarayıcı gerçek eşleme/receipt invalidation/dedup/import:3 satır/2 sipariş £14.70 →2 satır/2 sipariş £12.60, dashboard aynı tutar. Import sonrası catalog/run yarışı bulundu; sıralı akış + response öncesi permit cleanup ile düzeltildi.
- A6 tarayıcı gerçek Wine142/36, Logistic macro-F1 .971781 (baseline .186667); Diabetes353/89, Ridge MAE43.902866 (baseline61.370787). JSON kart indirildi/yeniden okundu, ham CSV yok. Model kartı hesaptan tekrar açılır. Bu küçük benchmark sonucu ürün-geneli başarı garantisi değildir.
- Ekranlar `docs/evidence/phase5/`, `phase6/` gerçek UI; özellikle `05-preparation-art.jpeg`, `06-model-art.jpeg`, `08-mobile-art.jpeg`. 390px mobil belge375/dialog343, brokenImages0, Esc kapatma doğrulandı. Görevli kullanıcı pilotu/tamWCAG değil.
- Gemini3 ek raster: `assets/data-preparation.jpeg`, `model-studio.jpeg`, `relationship-explorer.jpeg`; toplam5 raster/4 navigationSVG. `assets/PROVENANCE.md` chat URL/turn/usage; manifest hash ve scanner exact binary exception. Dekoratif alt boş, boyut sabit; metrik/sonuç resmi yerine kullanılmaz.

## Sonraki ajana birkaç örnek

**“progress.md'yi oku ve Aşama 2'yi yap.”** Aşama 2 zaten yerel kabul tamam. PHASE_2_REPORT ve mevcut SQL/arama/export/compare testlerini oku; ilk eksik/doğrulanamayan kapıyı bildir, aynı özelliği baştan yazma. Kullanıcı iyileştirme istiyorsa yeni dar kapsam/test kanıtı ekle.

**“Aşama 4'e devam et.”** Önce PHASE_4_REPORT açık kapılarını kontrol et. Admission/cancel/fingerprint/run archive zaten uygulandı; yeniden yapma. Gerçek HTTP402 kredi kapısı açık; model kalitesi değil fixture kontratları test edildi. Production IdP/tenant/RLS, dataset/query retention, HTTP/cancel stress/5M/50M ve UX pilotu kalan işlerdir. Eksik dış koşulu varsayma; bağımsız teknik paketi testleyip gerçek sonucu raporla.

**“Influencer kodunu kullan.”** Cell63/66 A6 runtime adapterında zaten kullanılıyor; REUSE_LEDGER ve `analysis/adapted/ml_preprocessing.py` oku, baştan kopyalama. Yeni ratio/interaction/OOF işinde ML_REUSE_RESEARCH ve envanterde gerçek notebook/hücreyi bul; target/decision time/group-time split/holdout'u önce yaz. SMOTE/scaler yalnız train fold'a fit edilir; güncel/gelecek aggregate ve test üstünde model seçimi aktarılmaz. Modülü test+model card ile kapat, sadece import edilmiş kodu runtime başarı sayma.

**“Nerede kaldık / bir önceki aşamayı göster.”** Yerel URL, güncel A5/A6 rapor ve önce/sonra karşılaştırmasını ver; eski üç aşama durumunu güncel sanma. 78 uzman puanını measured industry win diye sunma. Test sayısını logdan al; hedef puanı mevcut sonuçla karıştırma.

LLM planı aynı değilse replay digest değişebilir; temperature0 plan determinism garantisi değildir. Donmuş plan replay modu/live eval açık.

## Aşama 4 uygulama giriş haritası ve yayın kartı

- `analysis/llm.py`: config/status, static policy, strict plan validation, safe telemetry ve failure fallback. HF token server-side; çalışma config'i ignored0600, sadece izin ve varlık kontrolü yap. `analysis/adapted/providers.py` HF adaptasyonu, `worker.py` use_llm opt-in/claim/digest; `fingerprint.py` kaynak listesi.
- `core/src/workbench.ts`: AsyncLocalStorage cancel signal, PG subject/global advisory permits, catalog/import dahil shared admission, /runs/:id/archive. Migration `0019_workbench_lifecycle.sql`; eskileri değiştirme.
- `core/web/src/workbench/assets/`: iki Gemini JPEG + dört geometry-only SVG, PROVENANCE.md. `core/web/build.mjs` hash'li file loader, `core/src/spa.ts` dar static asset route. `UsageMeter.tsx` artık quota değil request status. Giriş fixture ekranı da sadeleştirildi.
- `analysis/tests/test_phase4.py`, `core/test/workbench.test.ts`, `tests/test_brand_assets.py`, `tests/test_nul_scan.py` A4 test girişleri. `tools/nul_scan.py` yalnız exact PNG/JPEG exceptions; yeni screenshot ekleyince manifest/exceptions güncelle. `.github/workflows/tests.yml` offline analytics ve core fixture hazırlama ekli; secret/paid inference CI'ya girmez.
- `docs/evidence/ASSET_MANIFEST.json` gerçek screenshot/artwork hash'leri; `docs/evidence/verification/phase4-*` actual test/build/load/provider receipts. `analysis.benchmark` 0.53M full-graph subprocess için 1/3 concurrency, 12'şer gözlem, hata0; küçük örnek gözlemi, HTTP/production/memory ölçümü değil.
- Yeni `Perakende satış özeti` QA kaydı görünür/restore durumda; önceki kendi Aşama1 demo fixture bulgusu arşivde, geri alınabilir. İlgisiz kayıt silinmedi. Varsayılan dataset UCI; örnek veri Perakende örneği, source modalında sentetik olduğunu korur.
- Git hedefi **https://github.com/mesely/DataAnalyticsToolv2**, branch **feat/analytics-workspace-phase4**. `origin` AlperCamli read-only korunur; `publish` meselyv2 remote. Repo normu PR review; main merge veya production deploy otomatik yapılmaz. Son yayın sonucu aşağıdaki kartta güncellenir.

**A6 tarihsel yayın kartı (güncel A7–10 sonucu üst/son kartta):** GitHub push başarılı; PR https://github.com/mesely/DataAnalyticsToolv2/pull/1 açık. README/ekranlar dalda: https://github.com/mesely/DataAnalyticsToolv2/tree/feat/analytics-workspace-phase4 . Main merge/production deploy yapılmadı. Secret scan geçti; token ignored0600. Son uygulama kodu041982c: https://github.com/mesely/DataAnalyticsToolv2/actions/runs/38822570859 **BEŞ JOB YEŞİL**, GitHub public web summary üzerinden doğrulandı. `docs/evidence/verification/phase6-github-final.json` gerçek status receipt. e94819a tarihsel sayılar473core/841root/173analytics; son koşunun log sayılarını API timeout nedeniyle çıkaramadık, tahmin etme. Sonrasında yalnız kanıt/devir doküman commit'i vardır; kaynak kod değişmedi. Yerelde174 analitik ve build/typecheck geçti. CI'da .venv olmadığı için CORE_ANALYSIS_PYTHON=python açıkça ayarlandı.

## Aşama5/6 teknik devam kartı

- `analysis/preparation.py`: bounded UTF-8 CSV parser, schema profile, strict ISO mapping, options/receipt; `worker.py` prepare ve receipt-bound mapped import; eski sabit şema import geriye uyumlu.
- `/v1/dashboard/workbench/prepare`, `/import`: `core/src/workbench.ts`, aynı viewer/CSRF/bounded. Mappingli dataset id owner12 + receipt12; başka transform overwrite etmez. Source metadata preparation recipe/preview içerir.
- `analysis/ml.py`: explicit target/features/task/split/context/availability;100–3000 rows/30 features; seed47; split önce; training3fold selection; holdout20%; MLv1 card/source/runtime versions/hash. `.data/ML_PROVENANCE.json` gerçek fixture atfı; `wine-ml.csv`, `diabetes-ml.csv`.
- `analysis/adapted/ml_preprocessing.py`: gerçek Influencer cell63/66; test `analysis/tests/test_ml.py`. Fit transformer hiçbir holdout indeksini görmez; bu tüm semantic leakage ispatı değildir.
- Migration0020 `workbench_experiments`. POST `/ml`; GET `/ml` ve `/ml/:id` owner; `/ml-sample/wine.csv` ve `diabetes.csv` authenticated. CSV/executable model PostgreSQL'e yazılmaz; kart/recipe yazılır. Model card retention henüz yok.
- `Preparation.tsx`, `ModelStudio.tsx`; dört ana nav korunur, Model stüdyosu analiz girişinde ve CmdK içinde. Ham CSV yalnız yükleme/worker süresince browser/process belleğinde; Gemini/HF'e gönderilmez.
- A7–A10 kalan plan ve somut giriş dosyaları `NEXT_BACKLOG.md`. Önce yeni spec/contract; acceptance log+browser+devir+push sırasını aynı kaliteyle uygula. Yeni iş başlatmadan eski ürün için refactor/rewrite yapma.

## A6 TARİHSEL ANKOR — güncel kabul olarak kullanma

**Aşama1–3 tamam; A4 yerel paket tamam/canlı402 ve üretim dış kabul açık. A5 hazırlama ve A6 ML deneyi uygulanmış; son kod041982c geniş CI yeşil.** Son görsel/skew kodu041982c beş job CI yeşil; sonrasında yalnız devir/kanıt doküman güncellemesi vardır. Kod `/Users/selmanyilmaz/Projects/context-layer`; URL http://127.0.0.1:8123/app/ ; `selman` / `analiz-demo`. İlk sonraki iş PHASE_5/6_REPORT ve NEXT_BACKLOG; A7 henüz başlamadı. Parquet/metric compiler/OOF/serving/tenant/pilot/scale bitmiş sayılmaz. Tüm5 repo link/commit üst tabloda. Secret değerini okuma/yazma/paylaşma. Üst/son kartı, gerçek CI ve PR durumunu birlikte güncelle.

Son browser turu16 Ekim: demo CSV542→540 satır/180 sipariş/£21.405.00 import sonrası seçili katalog ve dashboard tutarlı, hata yok. Son kart açılanda dialog başa kayar; history ile method disclosure state ayrıldı. CmdK Model stüdyosu eylemini listeler.

Son doğrulama kaynağı: `docs/evidence/verification/phase6-browser-qa.json` (CSV → dashboard, klavye, yeniden açılan model kartı, mobil, README13/13 görsel). Final kod CI linki041982c; doküman commitlerinin yeni workflow sonucunu kaynak kod kapısıyla karıştırma.


## SON ANKOR — güncel devam / A7–10

Repo `/Users/selmanyilmaz/Projects/context-layer`, branch `feat/analytics-workspace-phase4`, publish `mesely/DataAnalyticsToolv2`, PR https://github.com/mesely/DataAnalyticsToolv2/pull/1; origin AlperCamli read-only. Yeni kod fddc4f1; final CI/QA receipt'i doğrula. App http://127.0.0.1:8123/app/; selman/analiz-demo (yerel fixture). Tokenı gösterme veya tekrar isteme; serverignored0600, gerçek402hemplannerhemdecisionXMLakışında görüldü. Başarılı canlıLLM cevabı0/accuracy null.

**“Aşama10'u tamamla/devam et”**: üstkart → PHASE_10_REPORT → sonCI/browserreceipt. Önce tamamlanmamış kabul, sonra NEXT_BACKLOG. Aynı kartın reopen reset/mobil/koyu-açık/CmdK/Esc ve JSON/MD/XMLdownload akışını gerçek browser ile doğrula. CI başlangıçta iki testharness uyumsuzluğuyla kırıldı; cd47504 düzeltti. Sadece fixture çalıştı diye model doğruluğu yazma. Dosya yolu/source/evidence ref/bütçeyi koru. Görüntü eklediğinde scanner namedexception + SHAmanifest + gitstage zorunlu. Browser automation bağlantısı geçici kesilmişti; gerçek screenshot yerine mock üretme.

**“Aşama7/8/9'u bitir”**: yeni forecast/decision/report paketi zaten var; dar ek paketi baştan yapma. Kullanıcı geniş orijinal kapsamı istiyorsa NEXT_BACKLOG'daki Parquet/semantic/OOF veya RLS/hardresource/retention veya governedBI/conversationreference kapısını seç; spec+test+QA ile gerçek çıktıyı kapat. Aşama adı değişti diye eski işi tamam sayma.

**“Tahmini/LLMdoğruluğunu maximize et”**: PHASE_10_REPORT'taki naiften kötü holdout ve402kapısını başlangıç al. Mevcut son4testi yeniden tuning için kullanma; yeni development/holdout protokolü yaz. Llama erişimi düzelmeden uydurmaaccuracy verme. XML tekbaşına doğruluk artışı ispatı değil. Supportscore olasılık/ROI değil.

Disk bu tur doldu; yalnız projevenv .pyc ve bu çalışmanın Prettier npxcache'i silinerek~140MB yeniden üretilebilir alan açıldı. Kullanıcı belgesi/verisi silinmedi. Büyük yeni dependency/artifact eklemeden df kontrol et; başka proje Docker'ını restart etme. Doğru Python `.venv/bin/python` (sistem python3'te langchain yok); Node24 PATH yukarıdaki rehberde. Program artifact'ları yalnız publicUCI içerir.
