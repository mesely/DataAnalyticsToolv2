# Aşama 11 — AW-14 ölçülmüş kalite döngüsü raporu

**Güncel devam raporu:** [PHASE_11_CONTINUATION.md](PHASE_11_CONTINUATION.md). Aşağıdaki ilk tur ölçümleri tarihsel kanıttır; devam turunda doğruluk açıkları kapatıldı ve gerçek tarayıcı kabulü tamamlandı.

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
(bilinmeyen tip/kimlik, atıfsız olgu/hesap/öneri, aday olmayan öneri, atıflı dayanağa eşit olmayan sayı reddedilir; devam turunda işaret/birim/ondalık büyüklük ve küçük tam sayılar da kapsandı); bir onarım denemesi, sonra yerel. Model metni yerel sayıların yerine
geçmez. Karar özeti/rapor/XML'e eklendi; DecisionStudio "Analist anlatısı" bölümü ve kanıt paketi indirme.
Devam turunda küçük tam sayı istisnası kaldırıldı. Kalan sınır: doğrulayıcı anlamsal doğruluk değil mekanik tutarlılık ölçer.
Testler: `test_narrative.py` (9) + güncellenen `test_decisions.py`. Harness v2 (`llm_eval`): 8 narrate vakası; yerel
renderer kendi sözleşmesini 1,00 geçer, tasarlanmış-kötü yanıtların tamamı reddedilir (1,00); **gerçek model satırı
BLOCKED (HTTP 402, 16 Ekim 10:10 UTC probu)**. Kanıt `docs/evidence/phase10/llm-eval.json`, rapor `LLM_EVALUATION.md`.

## 3. Alım v2 (csv-preparation-v2) — IMPLEMENTED · TESTED · UI
Parquet (DuckDB `read_parquet`, tüm sütunlar metin, aynı 2 MB/10.000 satır/60 sütun/4.096 karakter sınırı, yeni
bağımlılık yok); `decimal_comma` ve `date_format` (iso/dmy_slash/mdy_slash/dmy_dot) açık seçenekler, receipt'e bağlı;
profil her sütun için `decimal_comma_candidates` ve `date_patterns` sayar (önizlemeden önce ne olacağı görünür);
tarayıcı UTF-8 başarısızsa Windows-1252 önerir; devam turunda Windows-1254 seçimi, yerel metin önizlemesi ve açık onay eklendi. Kimlikler ve para sessizce dönüştürülmez: `5,25`
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

## 7. İlk tur HTTP kabulü (tarihsel SERVER) ve devam turu kabulü
Çalışan yerel fixture'a karşı gerçek OIDC dev IdP girişi, CSRF, PostgreSQL ve Python worker ile 21 kontrol, **21/21
geçti** → `docs/evidence/verification/phase11-http-qa.json` (üretici betik scratchpad'de; yalnız public UCI/sentetik veri).
Kapsanan: üç fixture kimliği; `/decisions` UCI (HTTP gidiş-dönüş 1.680 ms, warm değil) → v3 tahmin alanları, 3 ülke
dilimi, etiket içermeyen teşhisler, altı tipli yerel anlatı (12 cümle), dayanak kimlikleri çözülür, `analysis_context`
6.243 bayt ve sonu `output_contract`, Markdown raporunda anlatı; aynı kaydı yeniden açma aynı `output_sha256`; başka
kimlik 404; viewer 403; CSRF'siz 401/403; Parquet profil → eşlemeli önizleme (receipt) → owner import; eşlemesiz Parquet
import 400; CSV+Parquet birlikte 400; bozuk Parquet 400; profil teşhis alanları; Wine ML kartında olasılık metrikleri
(log loss 0,1827 / Brier 0,0702 / ECE 0,1279 — küçük benchmark); servis edilen web bundle yeni UI metinlerini içeriyor.
Devam turunda CUA üzerinden gerçek tarayıcı kabulü **16/16 PASS**: `docs/evidence/verification/phase11-browser-qa.json`. Güncel sunucu kontrolü yeniden üretilebilir `analysis.verify_workspace` ile **21/21**: `phase11-http-qa-continuation.json`. İlk turun tarayıcı engeli ve eksik `phase10-browser-qa.json` kaydı tarihsel olarak korunur; yeni sonuç tam WCAG, kullanıcı pilotu veya E2E performans ölçümü değildir.

## 7b. Ölçü ve dönem bağı (Opus devam turu) — IMPLEMENTED · TESTED · SERVER · BROWSER
Spec: `specs/analyst-workspace-phase11.md` "AW-14 binding amendment". `analysis/narrative.py`: `MEASURES` (ölçü adı +
ayırt edici EN/TR terimler), `periods()` (her dayanağın ISO dönemi), sayı başına önceki dört kelimelik pencere (aynı yan
cümle, önceki sayıdan sonra) ve tarih başına dönem kontrolü; paket/XML `measure` ve `period` taşır; çıktı sözleşmesi
kuralı sonda tekrarlar. Yerel EN/TR anlatı metni **değişmedi** ve yeni doğrulayıcıdan geçer (negatif senaryo dahil).
Karşı örnekler (geçerli kimlik + paketteki değer): MAE takası EN/TR, hata değerini "gross sales" diye sunmak, payı brüt
satış diye sunmak, son pencere tarihini sonraki hafta projeksiyonunun yanına koymak, tarihli kalite sayısı — hepsi red.
Testler: `test_narrative.py` +4 → analytics **274 passed**; `llm_eval` narrate 16 (n15/n16). HTTP kabulü 21/21
(`phase11-http-qa-binding.json`, çalışma ağacı); tarayıcı 6/6 (`phase11-browser-binding.json`: TR anlatı değişmedi,
XML öznitelikleri, 390 px taşma yok). Aynı turda bulunan küçük UI kusuru: TR yüzde düğmesi "84,611%" gösteriyordu,
cümle "%84,6" — yerel yüzde biçimine ve tek ondalığa çevrildi. Ardından sayıdan sonraki ≤2 kelime de bağlandı (bağlaç/noktalamada durur; Türkçe isim-sonra düzeni için):
"£47.206,66 naif referans hatası" takası reddedilir; 279 test. Sınır: kelime düzeyinde mekanik kontrol; pencerelerin
dışındaki tanımlar ve eş anlamlılar bağlanmaz; canlı model ölçümü BLOCKED (402), çağrılmadı.

## 7c. Worker soğuk başlangıcı — LangChain yalnız model çağrısında (Opus devam turu) — MEASURED · SERVER
Profil (`-X importtime`, cProfile): her `run` ve `decisions` isteği, model kapalıyken bile yalnız sağlayıcı durumunu
bildirmek için `analysis.llm` → `analysis.adapted.providers` → LangChain yüklüyordu (~1,05 s kümülatif import).
Yerel `hf-provider.json` bulunduğu için `status()` ProviderSettings kuruyordu. Düzeltme: `_credentials()` sağlayıcı
importu olmadan (token, model) okur; `status()` aynı alanları döndürür; `configuration()`, `build_chat_model` ve
`LLMProviderError` yalnız model kurulurken/çağrılırken import edilir (`llm.py`, `decisions.py`, `narrative.py`).
Aynı betik/oturum/makine, n=9, eşzamanlılık 1 (`phase11-performance-startup.json`, önce = aynı HEAD'de üç dosya
geçici stash): run p50 1.483 → 703 ms, ülke filtreli run 1.429 → 665 ms, decisions 1.497 → 733 ms, forecast 135 →
136 ms (değişmedi; zaten LangChain yüklemiyordu); 72/72 istek hatasız. Önceki not "filtreli istekte DuckDB parametresi
pandas'ı yükler (~1 s)" bu turda ölçülerek düzeltildi: filtreli forecast'ta ek maliyet ~0,2 s (pandas import, sıcak
disk); asıl darboğaz LangChain'di. `evaluate_decisions.py` artık `--actions run run_filtered forecast decisions` alır.
HTTP kabulü değişiklik sonrası 21/21. Ölçülmeyen: /run HTTP gidiş-dönüşü ve tarayıcıda görünür gecikme.
**Bilinçli olarak yapılmayan:** DuckDB 1.5.6 Python istemcisi boş olmayan her parametre listesinde (int/float/str/date)
pandas'ı yükler (ölçüldü: 170–500 ms soğuk; parametresiz sorgu 13 ms). Kalan ~0,2 s yalnız değerleri SQL metnine
gömerek kazanılabilir; güvenli SQL ürününde bağlı parametreden vazgeçilmedi. Doğru çözüm kalıcı worker süreci
(importları amorti eder) — süreç izolasyonu/iptal sözleşmesini etkileyen ayrı mimari karar.

## 7d. Aylık dönem dilimleri (Opus devam turu) — IMPLEMENTED · TESTED · BROWSER
`forecast.period_slices`: hedef haftanın ayına göre, aşama ayrımıyla seçilen/naif MAE, bias, %90 bant içinde k/n ve
ortalama genişlik. Geliştirme bantları yalnız önceki artıklardan (ilk 8 origin bantsız), final sabit yarıçap; seçimden
sonra hesaplanır. Testler: dilimler kayıtları bölüştürür, ay MAE'leri bağımsız oracle'a eşit, bant sayıları toplam
kapsamayla (22/26 geliştirme, 7/10 final) uzlaşır, final değişikliği geliştirme dilimlerini değiştirmez. UCI ölçümü
(MEASURED, betimsel): final pencerenin naife göre %21 avantajı Eylül sonu/Ekim'den gelir — **Kasım 2011'in 4 final
haftasında mean8 MAE £59.288,62, naif £41.723,39; bant 2/4; tüm hata eksik tahmin (bias +£59.288,62)**. Ekim 4/5 bant,
seçilen £45.061 < naif £60.944. Geliştirmede Şubat–Mart ve Eylül'de de naif daha iyiydi. Yeni teşhis
`final_month_worse_than_naive` 2011-11'i adlandırır. Okuma: 8 haftalık ortalama tatil rampasını geriden izliyor; bu bir
yöntem değişikliği gerekçesi **değildir** (10 final origin üzerinde ayar yapılmaz); ≥2 sezon veriyle seasonal naive
veya takvim değişkenleri yeni bir dondurulmuş protokol ister. UI: Karar stüdyosunda katlanır "Aylara göre hata ve %90
bant kapsaması" tablosu (Markdown raporunda da); kaydırılabilir tablo bölgesi klavyeyle odaklanır (role=region, 2 px
odak, ok tuşu ile kaydırma doğrulandı). TR kapsama cümlesi artık "%85 / %70" yazar. Kanıt: `phase11-forecast-uci.json`
(`period_slices`), `phase11-browser-binding.json` 10/10. Analytics **277 passed**.

## 7e. TR teşhis metinleri (Opus devam turu) — IMPLEMENTED · TESTED · BROWSER
Tahmin teşhisleri artık `params` taşır (sayılar, tarihler, aylar); İngilizce `message` rapor ve model paketi için
korunur. Karar stüdyosu TR modunda 12 kodun her biri için TR şablonu kullanır; bilinmeyen kod veya eksik params
İngilizce mesaja düşer, hiçbir teşhis gizlenmez. Koruyucu test: forecast.py'deki her kod params taşır ve TS'de bir
`case` karşılığı vardır (yeni kod eklenip çevrilmezse test kırılır). Tarayıcı: UCI'nin 6 teşhisi TR'de tamamen Türkçe;
EN'e geçince sunucu mesajları aynen. Analytics **278 passed**.

## 7f. Kaydırılabilir tabloların klavye erişimi (Opus devam turu) — IMPLEMENTED · BROWSER
Yeni `core/web/src/workbench/TableWrap.tsx`: tablo kapsayıcıdan genişse kapsayıcı `tabIndex=0`, `role=region` ve
etiket (verilen metin veya tablonun caption'ı) alır; sığıyorsa sekme durağı eklemez. 15 kapsayıcı (Karar stüdyosu,
Model stüdyosu, Hazırlama, SQL lab, dönem görünümü, genel bakış) bu bileşene geçti; önceden dördü koşulsuz odaklanabilir
ama etiketsizdi, dokuzu hiç odaklanamıyordu. Odak halkası `:focus-visible` ile 2 px. Core kaynak envanteri testine
(`dashboard-b1.test.ts` APP_SOURCES) yeni dosya eklendi; o test yerelde Docker fixture'ı nedeniyle koşmaz, envanter ve
yasak dize kontrolleri betikle tekrarlandı, CI'da koşar. Tarayıcı: 1024 px'te sığan tablolar sekme durağı değil;
390 px'te taşan iki tablo etiketli bölge; ok tuşu kaydırması önceki adımda doğrulandı.

## 7g. Yerel yönlendirici doğruluğu ve harness v2.1 (Opus devam turu) — IMPLEMENTED · TESTED · BROWSER
Ayrıntı `LLM_EVALUATION.md`. Düzeltilen yanlış-yanıt kusurları: adet/sipariş ve "en düşük" sıralamaları satış-tutarı
zirvesiyle; değişim soruları ("satış nerede düştü") statik toplamla; "item/SKU" soruları özetle yanıtlanıyordu. Pazar
ifadeleri ("where", "pazar", "nerede") ülke sıralamasına, ay/hafta ifadeleri (sıralama sorusu değilse) zaman aracına
gider. Harness v2.1 yerel yanıt niyetini ölçer: davranış 13/19 → 15/19, niyet 11/17 → 15/17 (aynı harness; iyimser —
kategoriler değerlendirme setinde görüldü, düzeltmeler ayrı 24 parafrazla geliştirildi). Tarayıcı: "En çok adet satan
ürün hangisi?" sınır rozeti ve açıklama gösterir. 299 test.

## 7h. İki sezonluk tahmin benchmark'ı — UCI Online Retail II (kullanıcı onayıyla indirildi) — MEASURED · BROWSER
Kaynak: https://archive.ics.uci.edu/dataset/502/online+retail+ii, DOI 10.24432/C5CG6D, CC BY 4.0 (sayfadan doğrulandı);
zip 45.622.418 bayt, SHA-256 `572e3627…7bfb`; repoya eklenmedi. `analysis/prepare.py --online-retail-ii`: iki yıllık sayfa
birleştirilir; **2010-12-01..09 (22.523 satır, 1.088 fatura) iki sayfada birebir tekrar** — satır hash multiset'iyle
doğrulanıp bir kez alınır, eşleşmezse birleştirme reddedilir. 1.044.848 ham → 1.019.654 dahil; 25.194 dışlanan; 11.812
tekrar satır korunur/raporlanır. Çapraz kontrol: 2010-12-01 sonrası UCI (v1) ile satır/tutar/sipariş aynı, tek fark
v1'de olmayan son gün POST satırı (581587, £18,00; tam hafta dışında). `uci2` isteğe bağlı genel veri setidir: yalnız
hazırlanmışsa katalogda; CI 45 MB indirmez.

Aynı weekly-gross-v3 protokolü, **değişiklik yok**: 104 tam hafta → seasonal_naive kayıtlı, ilk origin 53, 39 geliştirme,
12 final (2011-09-12..2011-11-28). Kanıt `docs/evidence/verification/phase11-forecast-uci2.json`.

| yöntem | geliştirme MASE | final MAE £ | final MASE | naife göre | final bias £ |
|---|---:|---:|---:|---:|---:|
| **seasonal_naive (seçildi)** | 0,673 | 44.185 | 1,065 | **−%28,8** | +5.429 |
| mean4 | 1,019 | 50.691 | 1,221 | −%18,3 | +34.482 |
| holt_damped_0.3_0.1 | 0,998 | 51.083 | 1,231 | −%17,7 | +29.951 |
| mean2 | 1,114 | 51.210 | 1,234 | −%17,5 | +17.737 |
| ses_0.5 | 0,990 | 53.854 | 1,298 | −%13,2 | +25.458 |
| mean8 | 1,012 | 56.590 | 1,364 | −%8,8 | +56.590 |
| naive | 1,000 | 62.055 | 1,495 | 0 | +10.972 |

Okuma: seçilen yöntem final pencerede de tüm adayların en iyisi ve neredeyse yansız. Kasım 2011 final: £14.370 vs naif
£41.723, bant 4/4 — tek yıllık veride mean8'in kaçırdığı tatil rampası. Eylül 2011 final zayıf (£88.236 vs naif £91.013,
bant 1/3). %90 bant: geliştirme yuvarlanan 29/31, final 9/12 (%75) — hâlâ eksik kapsama, kalibre değil. Final MASE 1,065
> 1: final dönem geliştirmeden zordur. Sınırlar: tek bir yıl-yıl karşılaştırması (2010→2011); 52 hafta = 364 gün olduğundan
tatil günleri her yıl bir gün kayar; tek mağaza/perakendeci. Bu, "mevsimsel naif her zaman kazanır" iddiası değildir.
Tarayıcı: menüde Online Retail II, KPI'lar DB toplamlarıyla aynı, Karar stüdyosu "Geçen sezonun aynı haftası", 12 dönem,
naif uyarısı yok, ay tablosu ve anlatı tutarlı. 305 test.

## 8. Açık kalanlar
Gerçek LLM erişimi (402), 5–8 kullanıcı pilotu, üretim RLS/retention/hard isolation, 5M+ ölçek, decisions yolunun
decisions/run yolunda kalan ~0,7 s başlangıç (pandas/networkx; graph gerektirir), ≥2 sezon veriyle seasonal naive doğrulaması, dönem (ay) dilimleri ve anlatı için anlamsal iddia-dayanak doğrulaması (ölçü/dönem bağı kelime düzeyinde eklendi). Parquet core TS rotası önceki CI’da geçti; açık iş olarak tutulmaz.
