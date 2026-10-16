# Benchmark matrisi — ne ölçüldü, ne ölçülmedi (16 Ekim 2026, AW-14 sonrası)

Her hücre bir etiket taşır: **MEASURED** (gerçek log/kanıt dosyası var), **NOT MEASURED**, **BLOCKED** (dış bağımlılık),
**ESTIMATED** (kullanılmaz). Ölçüm türleri karıştırılmaz: MICRO = fonksiyon, SERVER = worker subprocess, BROWSER = UI,
E2E = tıklamadan görünen sonuca. Kaynak dosyalar `docs/evidence/` altındadır.

| Boyut | Metrik | Değer | Etiket | Tür | Kanıt |
|---|---|---|---|---|---|
| A. Analitik doğruluk | UCI toplamları (brüt £10.666.684,54 / 19.960 sipariş / 5.588.376 adet) oracle ile eşleşir | eşleşiyor | MEASURED | MICRO | `analysis/tests/test_phase2.py`, TEST_GUIDE |
| A. Analitik doğruluk | Sentetik demo oracle (540 satır / 180 sipariş / £21.405,00) | eşleşiyor | MEASURED | MICRO | `analysis/data/demo_oracle.json` |
| B. Tahmin | Geliştirme MAE (34 origin), seçilen mean8 / naif | £30.445 / £33.201 (MASE 0,917 / 1,0) | MEASURED | MICRO | `forecast-v3-uci.json` |
| B. Tahmin | Final pencere MAE (10 origin, seçimden ayrı), mean8 / naif | £47.207 / £59.859 (MASE 1,42 / 1,80; +21 %) | MEASURED | MICRO | aynı |
| B. Tahmin | %90 bandı yuvarlanan geliştirme kapsaması / final kapsaması | 0,846 / 0,70 — **kalibre değil** | MEASURED | MICRO | aynı |
| B. Tahmin | %90 bant ortalama genişliği: geliştirme / final | £124.948,63 / £130.997,26 | MEASURED | MICRO | `phase11-forecast-uci.json` |
| B. Tahmin | Lider ülke dilimleri (UK/NL/EIRE) seçilen < naif, final | 3/3 evet | MEASURED | MICRO | aynı |
| B. Tahmin | Aylık final dilimi: Kasım 2011 (4 hafta) mean8 / naif MAE; %90 bant | £59.289 / £41.723 — naif daha iyi; 2/4 | MEASURED | MICRO | `phase11-forecast-uci.json` period_slices |
| B. Tahmin | Seasonal naive, iki sezon (UCI Online Retail II, 104 hafta): final MAE (12 origin) seçilen / naif | £44.185 / £62.055 (−%28,8); %90 bant final 9/12 | MEASURED | MICRO | `phase11-forecast-uci2.json` |
| C. LLM groundedness | Gerçek model (HF Llama 3.3 70B) plan/decide/narrate doğruluğu | — | **BLOCKED** (HTTP 402) | — | `llm-eval.json` hf satırı |
| C. LLM groundedness | Doğrulayıcı öz-denetimi: tasarlanmış-kötü yanıtların reddi (decide 6, narrate 17, claims 8) | 1,00 / 1,00 / 1,00 | MEASURED (model değil) | MICRO | `phase11-llm-offline.json` |
| C. LLM groundedness | Yerel deterministik yönlendirme: davranış / yanıtlanan niyet (19 soru; harness v2.1) | 0,79 / 0,88 (önce 0,68 / 0,65; iyimser) | MEASURED | MICRO | aynı |
| D. Öneri kullanışlılığı | Dayanak skoru; iş doğrulaması bileşeni | 0/20 — kullanıcı/iş ölçümü yok | NOT MEASURED | — | PHASE_8/10 raporu |
| E. Uçtan uca performans | Worker subprocess forecast p50 / p95 (tarihsel A11 ilk tur, n=9) | 130 / 411 ms | MEASURED | SERVER | `phase11-performance.json` |
| E. Uçtan uca performans | Worker subprocess decisions p50 / p95 (tarihsel A11 ilk tur, n=9) | 2.098 / 2.462 ms | MEASURED | SERVER | aynı |
| E. Uçtan uca performans | HTTP `/decisions` UCI gidiş-dönüş (OIDC oturum + CSRF + PG + worker; tek gözlem, soğuk) | 1.680 ms | MEASURED (n=1) | SERVER | `phase11-http-qa.json` |
| E. Uçtan uca performans | Devam worker forecast / decisions p50 (n=3; HTTP kabulüyle örtüşen sistem yükü) | 148 / 1.759 ms; 6/6 hatasız | MEASURED (hız karşılaştırması değil) | SERVER | `phase11-performance-continuation.json` |
| E. Uçtan uca performans | Worker subprocess p50, n=9, eşzamanlılık 1 — önce → sonra (LangChain yalnız model çağrısında): run 1.483 → 703 ms; ülke filtreli run 1.429 → 665 ms; decisions 1.497 → 733 ms; forecast 135 → 136 ms | yarıya indi | MEASURED | SERVER | `phase11-performance-startup.json` |
| E. Uçtan uca performans | Tarayıcı yükleme/LCP/CLS; tıklama→görünen sonuç | — | NOT MEASURED | E2E/BROWSER | — |
| F. Güvenilirlik | HTTP kabulü: kimlik/CSRF/sahiplik/rota sınırları (21 kontrol) | 21/21 | MEASURED | SERVER | `phase11-http-qa-continuation.json` (üretici: analysis.verify_workspace) |
| E. Uçtan uca performans | 0,53M satır tam graph (1/3 eşzamanlı, 12 gözlem) | hata 0 | MEASURED (tarihsel A4) | SERVER | PHASE_4_REPORT |
| F. Güvenilirlik | Worker admission/cancel/timeout 45 s/5 MB; 36/36 benchmark isteği hatasız | 0 hata | MEASURED | SERVER | phase10/11 performance |
| F. Güvenilirlik | HTTP yük/cancel/dead-client stres, 5M/50M satır | — | NOT MEASURED | — | NEXT_BACKLOG 6 |
| G. UX keşfedilebilirlik | Görevli kullanıcı ölçümü (5–8 kişi) | — | NOT MEASURED | — | NEXT_BACKLOG 2 |
| H. Erişilebilirlik | Klavye/Esc/focus, 390 px mobil, bozuk görsel 0 (A6 tarayıcı kabulü) | geçti | MEASURED (tarihsel, A6) | BROWSER | `phase6-browser-qa.json` |
| H. Erişilebilirlik | A11 gerçek tarayıcı kabulü: karar/anlatı/dilim/tema/390px/klavye/CSV/Parquet/indirmeler | 16/16 PASS; 44px form hedefleri; sayfa taşması ve bozuk görsel yok | MEASURED (tam WCAG değil) | BROWSER | `phase11-browser-qa.json` |
| H. Erişilebilirlik | Tam WCAG denetimi / ekran okuyucu | — | NOT MEASURED | — | — |
| I. Görsel kalite | 6 raster / 37 SVG özgün aile; manifest hash | doğrulandı | MEASURED | — | `ASSET_MANIFEST.json`, 48 test |
| J. Sürdürülebilirlik | Analytics pytest / NUL-asset / web tsc+build | 305 / 48 / geçti | MEASURED | MICRO | bu tur logu |
| J. Sürdürülebilirlik | Core TS suite (yerel) | Docker fixture → koşmaz | BLOCKED (yerel) / CI'da koşar | — | progress kartı |
| K. Ölçeklenebilirlik | 5M/50M satır bütçesi | — | NOT MEASURED | — | NEXT_BACKLOG 6 |
| L. Tekrarlanabilirlik | Aynı girdi → aynı output_sha256 (karar/tahmin/ML kartı) | geçiyor | MEASURED | MICRO | test_decisions/test_narrative/test_ml |
| ML | Wine holdout macro-F1 (Logistic) / baseline | ≈0,972 / 0,187 | MEASURED | MICRO | TEST_GUIDE A6 |
| ML | Diabetes holdout MAE (Ridge) / baseline | 43,90 / 61,37 | MEASURED | MICRO | TEST_GUIDE A6 |
| ML | Olasılık kalitesi (log loss/Brier/ECE) kartta | raporlanıyor; seçimi etkilemez | MEASURED | MICRO | test_ml |

En büyük ölçülmüş darboğazlar (sırayla): (1) gerçek LLM erişimi yok → C boyutu tamamen BLOCKED; (2) decisions soğuk
başlangıcı ~2,1 s (pandas/numpy/networkx import + DuckDB parametre→pandas); (3) tahmin bandı nominalin altında kapsıyor
(0,85/0,70) — veri 52 hafta, mevsimsel aday yok; (4) HTTP ve tarayıcı işlevsel kabulü var; LCP/CLS ve tıklama→görünen sonuç gecikmesi ölçülmedi. Tahmin: naif aday hâlâ kayıtlı ve
kazanırsa seçilir; "tahmin kalitesi yüksek" iddiası yoktur.
