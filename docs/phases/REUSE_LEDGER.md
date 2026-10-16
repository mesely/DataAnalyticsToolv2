# Gerçek kod yeniden kullanım kaydı

Pinned kaynak extraction `analysis/port_sources.py`, kaynak hash/commit kayıtları `analysis/SOURCE_LEDGER.json` içinde. Kaynak modülün bulunması ile runtime kullanımı ayrı değerlendirilir.

| Kaynak → hedef | Gerçek adaptasyon | Kullanım / kanıt |
|---|---|---|
| adviSU llm_providers → analysis/adapted/providers.py | Provider settings/transport/retry/deadline/circuit/stream sanitization korunmuş; akademik config factory açık settings ister | MockTransport başarı ve reasoning stripping testi; canlı model/key yapılandırılmadı |
| adviSU confidence → adapted/confidence.py | ConfidenceSignals/Result ve assess karar gövdesi; analytics intent policy | Yerel açıklama admission + unchecked evidence ret testi |
| adviSU guardrails → adapted/guardrails.py | Unicode/encoded/injection/secret kontrolleri; localization ve input limiti hedefe uyarlanmış | Soruda gerçek assess_input; injection testleri |
| adviSU language → adapted/language.py | Dil analizi gövdesi; analytics TR sözlük ekleri | Soru diline göre açıklama |
| adviSU BM25 → adapted/lexical.py | _BM25 algoritma gövdesi çıkarılmış, Chroma/ders bağımlılığı çıkarılmış | Worker search testli; context arama UI Aşama 2 |
| adviSU claim_coverage → adapted/claim_coverage.py | Lexical coverage kodu | Adapte edildi, Phase 1 deterministic açıklamada runtime kullanılmıyor; sayısal doğruluk denetimi diye sunulmaz |
| PoliEco → adapted/networks.py | zscore_frame/build_sparse_signed_graph/compute_gatekeeper_scores gövdeleri | Similarity modunda gerçek numeric çekirdek; symmetry/seed testli. İki-kutuplu gatekeeper skoru Phase 1'de kullanılmıyor |
| adviSU LocaleContext → web/src/workbench/Locale.tsx | Tek context/hook ve typed translation sınırı props-managed locale'a uyarlanmış | TR/EN arayüz, tek session/API |
| adviSU UsageMeter → workbench/UsageMeter.tsx | remaining/limit/ratio/usedPct/threshold gövdesi; API/locale/Tailwind hedefe uyarlanmış | Yerel in-flight durum göstergesi; günlük LLM kotası değil |

adviSU commit e1e224134a3ce9a52c758c35ce517b1d42c9b75a; PoliEco commit c1705e76a9e2c36ddda36c95d03bd733cf52a17a. Alper'in core/session/OIDC/CSRF/Postgres/migration/audit/SPA altyapısı korunur; canlı execute_sql/token sözleşmesi değişmez. Yeni motor yalnız public/uploaded local materyalize dataset hesaplar.

Henüz taşınmayanlar: full ChatPage, hybrid/rerank, shared resource controls, Influencer ve SNIPS eğitimleri. Tamamlanmış gibi sayma. Ek tekrar kullanım adayları: adviSU export_utils CSV gövdesi (formula escaping ile), conversation_memory bounded context (PII/history policy), source_indexer/file_lifecycle yaşam döngüsü (belge ve tablo farkı korunarak), benchmark manifest/hash yardımcıları; PoliEco bootstrap/permutation/placebo/window yardımcıları. Uygulamadan önce fonksiyon/test/domain varsayımı incelenecek.

## Aşama 2 — ek gerçek adaptasyon

| Kaynak → hedef | Adaptasyon | Runtime ve kanıt |
|---|---|---|
| Alper sqlval/__init__.py validate_statement/check_statement_class → analysis/sql_lab.py çağrısı | Mevcut parser/SELECT/şema doğrulama gerçekten kullanılır; üzerine yerel DuckDB dar function/AST/grain sınırı, kimliksiz view ve kaynak limitleri | expert SQL → gerçek DuckDB sonucu; güvenlik/oracle testleri. Canlı execute_sql token yolu değişmedi |
| adviSU server/modules/export_utils.py rows_to_csv/rows_to_xlsx → adapted/exports.py | Gerçek writer/workbook/styling/freeze/filter gövdeleri; akademik row builders çıkarıldı. Safe headers/cells, numeric preservation, <=500rows, query-column order ve boş header desteği eklendi | SQL sonuç CSV/XLSX indirme, gerçek dosya tekrar okuma; formula, duplicate-safe-header ve sıralama testleri |
| adviSU source_of_truth.py content_hash_bytes/text, source_id_for, embedding_cache_key → adapted/identity.py | Saf fonksiyonlar çıkarıldı; Mongo/config modülü import edilmez | content_hash_text/source_id_for: SQL kanıt kimliği; content_hash_text: full v2 analysis digest. Diğer iki yardımcı henüz runtime kullanılmıyor |
| adviSU _BM25 → analysis/context.py | Aynı kernel; accent/ı normalization, dataset-owned metric/schema/source corpus, exact-title navigation boost | Context arama API ve UI; zero-match, scope hash, Türkçe query testleri. Vector RAG veya LLM araması değildir |

Ek source SHA/commit/symbol kayıtları SOURCE_LEDGER.json içindedir. `analysis/verify_sources.py` pinned upstream hash'leri salt okunur doğrular. Eski port_sources.py adaptasyonları overwrite edebilir: yeni domain değişiklikleri gözden geçirilmeden yeniden çalıştırılmaz.

## Aşama 3 — zaman ve betimleyici sağlamlık

PoliEco `src/build_economic_shock_study.py` (c1705e76a9e2c36ddda36c95d03bd733cf52a17a) → `analysis/adapted/temporal.py`: gerçek `stage_months`, `owner_concentration_hhi`, `build_party_affinity`, `negative_edge_share` fonksiyon gövdeleri. `analysis/temporal.py` dönemleri bunlarla kurar; ürün satış paylarını açıkça `agenda_share` girdisine eşler ve ülke profili matrisini en fazla24 ürünle sınırlar. Siyasi ideoloji, dosya IO, global RNG ve iki kutuplu gatekeeper varsayımları aktarılmadı. Yeni invoice bootstrap betimleyici yöntemdir; kaynak siyasi bootstrap deneyinin aynısı diye sunulmaz.

Runtime: önce/odak/sonra satış/HHI/affinity + aynı ürün evreninde co-purchase/Jaccard; bağımsız CSV/basket/HHI oracles, seed/null/coverage, gerçek UCI ve owner testleri. Kaynak SHA/commit/semboller SOURCE_LEDGER.json içinde; 10 pinned dosyanın upstream hash'i verify_sources.py ile doğrulandı.

Yeni `analysis/claims.py` kaynak projeden kopyalanmış gibi sayılmaz: deterministik açıklamanın beyan edilen sayısal iddialarını metric/dimension/unit/rank ile sonuç kaydına çözümler; sonucu adviSU confidence kararına verir. adviSU lexical claim_coverage halen runtime'da kullanılmıyor ve serbest LLM metin doğrulaması tamamlanmış değil.

`analysis/layout.py` yeni hedef kodudur: görsel çakışma giderme ve signed graph için yalnız pozitif bağlardan topluluk. Kaynak similarity kernelini değiştirmez. SNIPS/Influencer için ML_REUSE_RESEARCH.md ve ML_SOURCE_INVENTORY.json gerçek dosya/hücre/fonksiyon araştırmasıdır; henüz runtime aktarımı değildir.

## Aşama 4 — gerçek provider genişletmesi ve sadeleşen UI

adviSU provider çekirdeğine `huggingface` ProviderSpec/Settings eklendi; aynı transport/retry/deadline/sanitization gövdeleri `analysis/llm.py` üzerinden runtime'da çağrılır. Strict iki anahtarlı intent/scope planı mevcut allowlisted hesaplara yönlenir; serbest model SQL/code/prose çalıştırılmaz. Gerçek HF çağrısı HTTP402 kredi gereksinimi döndürdü; canlı model başarı/accuracy kanıtı yok. 50 offline plan-contract vakası model benchmark'ı değildir.

`analysis/fingerprint.py`, PostgreSQL advisory admission ve geri alınabilir owner run archive yeni hedef kodudur; kaynak projeden kopyalanmış diye sayılmaz. v4 eski kayıtları overwrite etmez. Locale adaptasyonu çalışır. Önceki adviSU UsageMeter kota/ratio uyarlaması Aşama 4'te kaldırıldı; bu dosya artık gerçek istek durumunu gösterir ve ratio gövdesi runtime reuse olarak sayılmaz. Gemini özgün artwork'ü source asset provenance dosyasında kayıtlıdır. SNIPS/Influencer eğitim durumu değişmedi.

## Aşama 6 — Influencer artık runtime'da

Kaynak: `mesely/Influencer-Category-and-Like-Prediction-Stacking-SMOTE-RF`,
commit `b217890ec18c35180c7ac7bc3a8dcd28a6c1794e`,
`influencer_classification_and_like_count_regression.ipynb` hücre63 ve66.
Kaynak notebook SHA: `analysis/SOURCE_LEDGER.json`; orijinal hücre gövdeleri
`ML_SOURCE_INVENTORY.json` içinde. 11 pinned dosya doğrulandı.

| Kaynak sembol | Gerçek hedef | Uyarlama / kanıt |
|---|---|---|
| cell63 `apply_log_transform`, `preprocess_features` | `analysis/adapted/ml_preprocessing.py`: `apply_log_transform`, `FoldPreprocessor` | Kopya üstünde sütun döngüsü ve log dönüşümü korunur; negatif veriye signed-log genişletmesi. Train-only schema/skew/log seçimi, ayrı fit/transform, MinMaxScaler ve imputer/category encoder her fold pipeline'ında. `test_preprocessor_is_train_only_unknown_categories_and_no_mutation`, `test_no_pipeline_fit_sees_holdout` |
| cell66 `log_mse_like_counts` | Aynı adapter, `analysis/ml.py::metrics` | Orijinal ölçek log1p → fark karesi → ortalama gövdesi; sonlu/nonnegative guard. RMSLE bunun karekökü; negatiflerde null. Regresyon gerçek açık veride çalışır |
| cell30/33 SMOTE/RF yaklaşımı | `analysis/ml.py::candidate_models` | Yeni güvenli orchestration; orijinal hücre gövdesi kopyalandı diye sayılmaz. imblearn pipeline sampler'ı yalnız eğitimde; sayısal gate/k=2, CV-only seçim. OOF stacking henüz uygulanmadı |

SNIPS henüz runtime'da değil. Her kaynağı zorla ekleme; TF-IDF/LSTM ancak
ayrı analytics intent dataset'i ve ölçülmüş baseline kazancıyla değerlendirilir.


## Aşama 7–10 — karar bağlamı ve gerçek özetleyici

adviSU `server/modules/response_formatter.py` içindeki `_plain_text`,
`split_summary`, `compact_summary` gövdeleri `analysis/adapted/formatting.py`
içine çıkarıldı. `analysis/decisions.py::decision_brief` runtime'da çağırır:
hesaplanan aday metinlerinden extractive özet; Mongo/akademik audit taşınmadı.
SHA/pin SOURCE_LEDGER içinde;12upstream dosyası read-only doğrulandı.

`knowledge` mevcut gerçek adviSU BM25 ile üç yöntem notu seçer;
`select_actions` gerçek provider transport/retry/deadline kullanır. `context_xml`,
checklist, forecast ve scenario yeni hedef kodudur; kopya kaynak diye sayılmaz.
Strict ID/reason JSON serbest LLM prose entailment doğrulaması değildir.
Conversation_memory genel referans çözümü hâlâ açık; explicit owner UUID ile
arşiv açma, bu modülün adapte edildiği anlamına gelmez.
