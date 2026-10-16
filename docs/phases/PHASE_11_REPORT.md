# Aşama 11 — AW-14 ölçülmüş kalite döngüsü raporu

16 Ekim 2026 (öğleden sonra turu). Spec: `specs/analyst-workspace-phase11.md`. Önceki 7–10 ek paketleri korunur; bu rapor
yalnız bu turda ölçülen değişiklikleri anlatır. Gerçek kullanıcı pilotu, üretim RLS/retention/hard isolation ve başarılı
canlı LLM değerlendirmesi **açık** kalır.

## 1. Tahmin bandı geçerliliği (weekly-gross-v3) — IMPLEMENTED · TESTED · MEASURED
Seçim protokolü değişmedi (UCI: mean8). Bant ölçeği (absolute/relative) yalnız geliştirme origin'lerinde **yuvarlanan**
kapsamayla seçilir (her yarıçap yalnız önceki artıklardan); kuantil sonlu-örneklem split-conformal indeksi; final
pencere ölçek seçimine girmez. Tablo `PHASE_7_REPORT.md` v3 bölümünde: UCI %90 bandı geliştirmede 0,85 (eski düz
kuantil 0,77), final pencerede 0,70; **kalibre değil** etiketi korunur, UI iki kapsamayı birlikte yazar. Yeni teşhis
`band_undercovers_development`. Ek: lider ülke dilimleri (UK / Netherlands / EIRE) aynı final origin'lerde seçilen
yöntem ve naif — UCI'de üçünde de mean8 naifi geçti (MAE £45.523/£48.503, £7.367/£10.917, £4.213/£5.422; Netherlands
18 sıfır hafta → seyrek). Dilimler teşhistir, seçimi değiştirmez; `slice_disagreement` kodu etiket içermez.
Kanıt: `docs/evidence/phase10/forecast-v3-uci.json`. Testler: `test_forecast.py` +5, `test_decisions.py` +1 (dilim).

## 2. Tipli analist anlatısı (decision-narrative-v1) — IMPLEMENTED · TESTED · UI
`analysis/narrative.py`: yerel deterministik renderer (olgu/hesap/çıkarım/varsayım/öneri/sınır; her sayı atıf
yapılan dayanağa eşit) her zaman mevcut; model anlatısı `analysis_context` XML paketi üzerinden, mekanik doğrulayıcı
(bilinmeyen tip/kimlik, atıfsız olgu/hesap/öneri, aday olmayan öneri, atıflı dayanağa eşit olmayan ≥3 basamaklı/ayraçlı
sayı, eksik kanıt hakkında olgu reddedilir); bir onarım denemesi, sonra yerel. Model metni yerel sayıların yerine
geçmez. Karar özeti/rapor/XML'e eklendi; DecisionStudio "Analist anlatısı" bölümü ve kanıt paketi indirme.
Bilinen sınır: bir–iki basamaklı tam sayılar denetlenmez; doğrulayıcı anlamsal doğruluk değil mekanik tutarlılık ölçer.
Testler: `test_narrative.py` (9) + güncellenen `test_decisions.py`. Harness v2 (`llm_eval`): 8 narrate vakası; yerel
renderer kendi sözleşmesini 1,00 geçer, tasarlanmış-kötü yanıtların tamamı reddedilir (1,00); **gerçek model satırı
BLOCKED (HTTP 402, 16 Ekim 10:10 UTC probu)**. Kanıt `docs/evidence/phase10/llm-eval.json`, rapor `LLM_EVALUATION.md`.

## 3. Alım v2 (csv-preparation-v2) — IMPLEMENTED · TESTED · UI
Parquet (DuckDB `read_parquet`, tüm sütunlar metin, aynı 2 MB/10.000 satır/60 sütun/4.096 karakter sınırı, yeni
bağımlılık yok); `decimal_comma` ve `date_format` (iso/dmy_slash/mdy_slash/dmy_dot) açık seçenekler, receipt'e bağlı;
profil her sütun için `decimal_comma_candidates` ve `date_patterns` sayar (önizlemeden önce ne olacağı görünür);
tarayıcı UTF-8 başarısızsa Windows-1252 ile okur ve bunu söyler. Kimlikler ve para sessizce dönüştürülmez: `5,25`
seçenek olmadan açık hata; `31/01/2025` ile MM/DD seçilirse "1 tarih değeri uymuyor". Rotalar `/prepare` ve `/import`
`parquet_base64` kabul eder (Parquet import eşleme ister). Testler: `test_preparation.py` +4 (18). Core TS rota testi
yerelde koşmadı (Docker fixture); CI sonucu progress kartında.

## 4. ML olasılık metrikleri — IMPLEMENTED · TESTED · UI
Sınıflama kartlarında `holdout.probabilistic` / `baseline.probabilistic`: log loss, çok sınıflı Brier, ECE (10 kutu),
ikili ortalama kesinlik; seçimden sonra raporlanır, seçimi etkilemez (`selection_metric` macro F1). ModelStudio tablosu.
Test: `test_ml.py` +1 (19). Wine fixture gerçek değerleri UI/JSON kartında; bunlar küçük benchmark sonuçlarıdır.

## 5. Performans (MEASURED, dar kapsam)
`.venv/bin/python -m analysis.evaluate_decisions` → `docs/evidence/verification/phase11-performance.json`. Tam
subprocess, warm cache, 9 istek/hücre, makine yük altında (mediaanalysisd ~%100 CPU gözlendi); HTTP/OIDC/PG/browser
dahil değil; SLA değildir.

| İş | Eşzamanlı | n | p50 ms | örnek p95 ms | Hata |
|---|---:|---:|---:|---:|---:|
| forecast | 1 | 9 | 130 | 411 | 0 |
| forecast | 3 | 9 | 143 | 154 | 0 |
| decisions | 1 | 9 | 2098 | 2462 | 0 |
| decisions | 3 | 9 | 2515 | 2594 | 0 |

Bulgu: worker başlangıcı `analysis.prepare` üzerinden pandas'ı her istekte yüklüyordu (import 0,9 s ölçüldü);
pandas/numpy fonksiyon içine alındı → worker import 0,10 s, forecast p50 882 → 130 ms (aynı turda, aynı makine).
Decisions ~2,1 s değişmedi (overview+graph yolu pandas/numpy/networkx kullanır; sonraki hedef). Önceki tur değerleri
(forecast 357 ms) farklı yük koşullarında ölçüldü; karşılaştırma yalnız bu tur içindeki önce/sonra içindir.
İkinci bulgu (ölçüldü): DuckDB 1.5.6 Python bağlayıcısı `execute(sql, params)` çağrısında parametre listesi/tuple/dict
görünce **pandas'ı import eder** (~1 s soğuk); parametresiz sorgu etmez. Ülke dilimleri bu yüzden tek sorguda alt
sorguyla yazıldı (ek parametre listesi yok; soğuk forecast 1.043 → 0,110 s). Filtreli istekler (ülke/tarih) ana sorgu
parametreleri nedeniyle hâlâ bu bedeli öder; güvenli çözüm (katalogla doğrulanmış literal veya parametre dışı bağlama)
sonraki iş olarak NEXT_BACKLOG'a yazıldı — kullanıcı girdisini SQL'e kaçışsız gömmek kabul edilmez.

## 6. Testler (gerçek log)
`.venv/bin/python -m pytest analysis/tests -q` → **254 passed** (önceki 228). `tests/test_nul_scan.py` +
`test_brand_assets.py` → 48 passed. Web `tsc --noEmit` ve `npm run build` geçti. Core `workbench.test.ts` yerelde
`source_unavailable` (Docker daemon kapalı; connector fixture `postgres:16` ister) → **CI'da koştu ve geçti**:
https://github.com/mesely/DataAnalyticsToolv2/actions/runs/38886787881 (e4f82af, 5 job success).

## 7. Tarayıcı kabulü
BEKLİYOR — bu turda tarayıcı aracı güvenlik sınıflandırıcısı geçici olarak erişilemezdi; gerçek ekran alınınca bu
bölüm ve `docs/evidence/verification/phase11-browser-qa.json` doldurulur. Mock üretilmedi.

## 8. Açık kalanlar
Gerçek LLM erişimi (402), 5–8 kullanıcı pilotu, üretim RLS/retention/hard isolation, 5M+ ölçek, decisions yolunun
2 s başlangıcı, ≥2 sezon veriyle seasonal naive doğrulaması, dönem (ay) dilimleri, Parquet için core TS rota testi.
