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
| B. Tahmin | Lider ülke dilimleri (UK/NL/EIRE) seçilen < naif, final | 3/3 evet | MEASURED | MICRO | aynı |
| B. Tahmin | Seasonal naive doğrulaması (≥104 hafta) | veri 52 hafta | NOT MEASURED | — | teşhis `seasonal_naive_unavailable` |
| C. LLM groundedness | Gerçek model (HF Llama 3.3 70B) plan/decide/narrate doğruluğu | — | **BLOCKED** (HTTP 402) | — | `llm-eval.json` hf satırı |
| C. LLM groundedness | Doğrulayıcı öz-denetimi: tasarlanmış-kötü yanıtların reddi (decide 6, narrate 8, claims 8) | 1,00 / 1,00 / 1,00 | MEASURED (model değil) | MICRO | aynı |
| C. LLM groundedness | Yerel deterministik yönlendirme davranış doğruluğu (19 soru) | 0,68 | MEASURED | MICRO | aynı |
| D. Öneri kullanışlılığı | Dayanak skoru; iş doğrulaması bileşeni | 0/20 — kullanıcı/iş ölçümü yok | NOT MEASURED | — | PHASE_8/10 raporu |
| E. Uçtan uca performans | Worker subprocess forecast p50 / p95 (1 eşzamanlı, n=9) | 130 / 411 ms | MEASURED | SERVER | `phase11-performance.json` |
| E. Uçtan uca performans | Worker subprocess decisions p50 / p95 (1 eşzamanlı, n=9) | 2.098 / 2.462 ms | MEASURED | SERVER | aynı |
| E. Uçtan uca performans | HTTP `/decisions` UCI gidiş-dönüş (OIDC oturum + CSRF + PG + worker; tek gözlem, soğuk) | 1.680 ms | MEASURED (n=1) | SERVER | `phase11-http-qa.json` |
| E. Uçtan uca performans | Tarayıcı yükleme/LCP/CLS; tıklama→görünen sonuç | — | NOT MEASURED | E2E/BROWSER | — |
| F. Güvenilirlik | HTTP kabulü: kimlik/CSRF/sahiplik/rota sınırları (21 kontrol) | 21/21 | MEASURED | SERVER | `phase11-http-qa.json` |
| E. Uçtan uca performans | 0,53M satır tam graph (1/3 eşzamanlı, 12 gözlem) | hata 0 | MEASURED (tarihsel A4) | SERVER | PHASE_4_REPORT |
| F. Güvenilirlik | Worker admission/cancel/timeout 45 s/5 MB; 36/36 benchmark isteği hatasız | 0 hata | MEASURED | SERVER | phase10/11 performance |
| F. Güvenilirlik | HTTP yük/cancel/dead-client stres, 5M/50M satır | — | NOT MEASURED | — | NEXT_BACKLOG 6 |
| G. UX keşfedilebilirlik | Görevli kullanıcı ölçümü (5–8 kişi) | — | NOT MEASURED | — | NEXT_BACKLOG 2 |
| H. Erişilebilirlik | Klavye/Esc/focus, 390 px mobil, bozuk görsel 0 (A6 tarayıcı kabulü) | geçti | MEASURED (tarihsel, A6) | BROWSER | `phase6-browser-qa.json` |
| H. Erişilebilirlik | A7–11 ekranlarının tarayıcı kabulü (Karar stüdyosu anlatı/dilim/tema/mobil, hazırlama seçenekleri) | — | NOT MEASURED (phase10-browser-qa.json hiç yazılmadı; bu turda tarayıcı aracı erişilemezdi) | BROWSER | — |
| H. Erişilebilirlik | Tam WCAG denetimi / ekran okuyucu | — | NOT MEASURED | — | — |
| I. Görsel kalite | 6 raster / 37 SVG özgün aile; manifest hash | doğrulandı | MEASURED | — | `ASSET_MANIFEST.json`, 48 test |
| J. Sürdürülebilirlik | Analytics pytest / NUL-asset / web tsc+build | 254 / 48 / geçti | MEASURED | MICRO | bu tur logu |
| J. Sürdürülebilirlik | Core TS suite (yerel) | Docker fixture → koşmaz | BLOCKED (yerel) / CI'da koşar | — | progress kartı |
| K. Ölçeklenebilirlik | 5M/50M satır bütçesi | — | NOT MEASURED | — | NEXT_BACKLOG 6 |
| L. Tekrarlanabilirlik | Aynı girdi → aynı output_sha256 (karar/tahmin/ML kartı) | geçiyor | MEASURED | MICRO | test_decisions/test_narrative/test_ml |
| ML | Wine holdout macro-F1 (Logistic) / baseline | ≈0,972 / 0,187 | MEASURED | MICRO | TEST_GUIDE A6 |
| ML | Diabetes holdout MAE (Ridge) / baseline | 43,90 / 61,37 | MEASURED | MICRO | TEST_GUIDE A6 |
| ML | Olasılık kalitesi (log loss/Brier/ECE) kartta | raporlanıyor; seçimi etkilemez | MEASURED | MICRO | test_ml |

En büyük ölçülmüş darboğazlar (sırayla): (1) gerçek LLM erişimi yok → C boyutu tamamen BLOCKED; (2) decisions soğuk
başlangıcı ~2,1 s (pandas/numpy/networkx import + DuckDB parametre→pandas); (3) tahmin bandı nominalin altında kapsıyor
(0,85/0,70) — veri 52 hafta, mevsimsel aday yok; (4) HTTP/tarayıcı E2E ölçümü yok. Tahmin: naif aday hâlâ kayıtlı ve
kazanırsa seçilir; "tahmin kalitesi yüksek" iddiası yoktur.
