# Context Layer / Analytics — tek giriş ve devir rehberi

## ŞİMDİ OKU — AW-17: Groq (GPT-OSS 20B) dil modeli (17 Ekim 2026)

- **Sağlayıcı:** kullanıcının Groq anahtarı.
  - Model `openai/gpt-oss-20b`; hesapta Llama sohbet modeli yok.
  - Anahtar `analysis/.local/groq-provider.json` dosyasında (0600, Git dışı). Sunucuda `GROQ_API_KEY` yeterli.
  - Kurulum ve doğrulama: `python -m analysis.llm_setup [--check]`.
- **Canlı ölçüm** (`docs/evidence/verification/phase12-llm-eval-groq.json`):
  - yönlendirme 19/19
  - karar odağı 6/6
  - Grafik stüdyosu 19/24 (alan 38/47)
  - anlatı 1/3 kabul (ek örneklerde 7/11)
  - medyan 434 ms
- **Canlı koşunun bulduğu hatalar:**
  - Anlatı bağlamı ham ondalık sayılar taşıyordu (`59858.674000000006`); model değeri aynen kopyalasa bile
    reddediliyordu. Değerler artık kanonik biçimde yazılıyor, test ediliyor.
  - JSON üretim hatası (400) artık bir kez yeniden deneniyor.
  - Günlük kota 429'unda istek beklemeden yerel sonuca dönüyor, ekran "kullanım sınırı" diyor.
  - Değerlendirme reddedilen cevabı kesinti sayıyordu; artık yanlış cevap sayıyor.
- **Arayüz:** "Llama" etiketleri sağlayıcıdan bağımsız hale geldi, model adı durumdan geliyor. Karar stüdyosundaki
  model seçeneği sağlayıcı yokken kapalı. Grafik stüdyosu sağlayıcıya ne gittiğini yazıyor.
- **Gizlilik:** `tests/test_no_committed_secrets.py` izlenen her dosyada anahtar biçimlerini tarıyor. pytest ve
  vitest kayıtlı anahtarı testlerden yalıtıyor (`CONTEXT_LLM_DIR`).
- **Açık:**
  - Ücretsiz Groq günlük kotası 200.000 token; ekip kullanımı için ücretli katman gerekir.
  - 17 Ekim'de değerlendirmeler kotayı doldurdu; karar stüdyosu ekran görüntüsü bu yüzden alınmadı.
  - Self-hosted Llama canlı ölçülmedi.

## ÖNCEKİ — AW-16 devamı: dışlama, betikte katmanlar, dayanak ağacı, maskot, son UI geçişi (17 Ekim 2026)

- **Dışlama** ("İngiltere hariç", "except UK and EIRE"): ChartSpec'e eklemeli anahtar `exclude_countries` geldi
  (spec A1). Planlayıcı Türkçe ve İngilizce anlıyor; geri ekleme dışlamayı kaldırıyor. SQL'de `NOT IN (?)`.
- **Betikte katmanlar:** dışa aktarılan grafik aralık, trend, bant ve hareketli ortalamayı yeniden hesaplıyor
  (`stats.py`, bağımlılıksız Student-t). `--check` bunları da karşılaştırıyor (spec A3).
- **Güvenlik düzeltmesi:** dışa aktarılan Python'a gömülen SQL artık kaçışlı. Yüklenen veriden gelen ülke adı
  `"""` veya ters bölü içerse de literali kapatamıyor; bunu bir test doğruluyor.
- **Dayanak ağacı** (`Reasoning.tsx`): ifadeler tür başına numaralı (O1, H1, Ç1…) ve kanıt paylaşımına göre iç içe.
  Seçim beş seçeneğin puanlanmasıyla yapıldı (UX_DECISIONS).
- **Portreler ve maskot:**
  - 10 portre var: iki insan analist dahil ve tek kelimelik adlarla.
  - Maskot dört pozda (asılı, tablet, el sallama, büyüteç), aynı Gemini konuşmasında üretildi.
  - Kullanıldığı yerler: kenar çubuğu markası, giriş sayfası, oturum bitti ekranı, rehber, Grafik stüdyosu, boş
    durumlar.
- **Son UI geçişi:**
  - SQL laboratuvarı ve zaman değişimi ayrı diyaloglarda açılıyor.
  - Metrik tanımları Kanıt diyaloğunda.
  - Ana bölge ve diyaloglarda en çok 15 komut var.
  - Denetim: 19 ekran/diyalog × 4 genişlik × 2 tema (160 ölçüm, hepsi 100, lint bulgusu 0) (`docs/evidence/verification/phase12-aw16-design-sweep.json`).
- **Llama:**
  - Kendi barındırılan OpenAI uyumlu uç nokta desteği eklendi (`python -m analysis.llm_setup --endpoint …`;
    llama.cpp, Ollama, vLLM).
  - Hugging Face 402 döndürüyor (kredi yok).
  - Drive'daki model bu makinede çalıştırılamadı: 8 GB RAM, 2,4 GB boş disk. Canlı doğruluk ölçülmedi.
- **README:** baştan yazıldı. Sade anlatım, 20 aşamalı uçtan uca teknik tablo, tekrar üretim adımları, 18 ekran
  görüntüsü ve GIF.
- **Açık:**
  - Canlı Llama ölçümü (erişilebilir bir sunucu gerekiyor).
  - Kullanıcı görev testi.
  - Docker gerektiren core testleri yalnız CI'da koşuyor.

## ÖNCEKİ — AW-16: kod dışa aktarma, Grafik stüdyosu, analist portreleri, tanıtım README (17 Ekim 2026)

- **Kod dışa aktarma** (`analysis/code_export.py`, `POST /export/code`, `CodeExport.tsx`). Dışa aktar menüsü, komut paleti ve Grafik stüdyosundaki "Koda aktar" bu diyaloğu açar.
  - Paket içeriği: README, yorumlu `analysis.py` (tek bağımlılık duckdb, `--check`), `analysis.sql` (SET VARIABLE), `charts.py`, Parquet veri, `expected.json` ve SVG figürler.
  - Deterministik: aynı kapsam iki kez dışa aktarılınca byte'ı byte'ına aynı zip çıkar.
  - Paket repo dışında `--check` ile 11/11 yeşil.
- **Grafik stüdyosu** (`analysis/chart_studio.py`, `POST /chart`, `ChartStudio.tsx`).
  - Serbest metin istek ve adım adım iyileştirme: dönem, ülke karşılaştırma, ilk N, %95 GA (yalnız ortalamalar), OLS trend, ±2σ bant, hareketli ortalama.
  - Llama yalnızca ChartSpec planlar; geçersiz veya erişilemez plan → yerel planlayıcı (ekranda yazar).
  - scipy.stats → scipy.special: aralık/trend isteklerinde p50 1,51 s → 0,61 s.
- **Portreler:** 8 Gemini portresi + yeni ürün işareti (maskot) + favicon.
  - Seçim sunucuda: `workbench_profiles`, geçiş 0022, `GET/PUT /profile`.
  - Harf avatarı kaldırıldı.
  - **İnsan portreleri üretilemedi:** otomatik izin denetimi engelledi; kullanıcıya soruldu.
- **README** ürün tanıtımı olarak yeniden yazıldı.
  - Görseller `docs/showcase/` altında: 14 ekran görüntüsü + GIF, headless Chrome ile 1440×900 @2x.
  - İçerik: mimari, ölçülmüş süreler, kategori karşılaştırması ve "neyin yerini tutmaz" bölümü.
- **Karneler:** `docs/phases/AW16_FEATURE_SCORECARD.md` (kod 96, grafik 91, portre 88). Spec: `specs/analyst-workspace-phase12.md` (sonuçlar dahil).
- **Diğer düzeltmeler:**
  - Ağ notu yerelleştirildi; dil değişince analiz yeniden çalışıyor.
  - Anlatı etiket sütunu 136 px oldu.
  - Derleme `dist/assets` klasörünü her seferinde temizliyor.
- **Açık:**
  - Canlı Llama (402).
  - Dışa aktarılan grafik betiğinde istatistik katmanları yok.
  - Dışlama istekleri ("X hariç") desteklenmiyor.
  - Kullanıcı görev testi yapılmadı.

## ÖNCEKİ — AW-15 özgün simge ailesi + tasarım maksimizasyonu (17 Ekim 2026)

İstek: hiçbir simge hazır asset olmayacak; hepsi Gemini üretimi ve ürüne özgü; tasarım/kural puanları 100'e.
- **Simgeler:** lucide-react paketi ve 36 eski SVG kaldırıldı. Gemini konuşmasında 7 tur → 52 glyph
  (`core/web/src/workbench/assets/glyphs/gemini-batch-1..7.json`, değiştirilmeden; hash'ler PROVENANCE +
  ASSET_MANIFEST). `python -m tools.design.glyphs` doğrular ve `glyphs.generated.ts` + `glyphs.generated.css`
  üretir. `Glyph.tsx` React.createElement ile çizer. Tarayıcı işaretleri (summary üçgeni, select oku, takvim,
  checkbox tiki, sayı okları) de aynı aileden.
- **Tasarım sistemi:** tip 12/14/16/20/24/32, kalınlık 400–700, 4px ritim, yarıçap 6/10/14, kontrol 44px,
  açık tema metin tonları ≥4.6:1 (`tools/design/normalize_css.py`, `contrast_tones.py`). Kapsam tek kartta
  (`wb-scope`), CSV/JSON "Dışa aktar" menüsünde, mobilde hero KPI.
- **Puanlar** (`tools/design/audit.js`, 4 ekran × 2 tema × 1440/390): Fitts 78→100, metin kontrastı 98
  (açık 72–74)→100, boşluk 29→100, tip 52→100, hizalama 34→100, Hick–Hyman 94→98–100, simge özgünlüğü 100.
  Ayrıntı: `docs/phases/DESIGN_SCORECARD.md`, ham: `docs/evidence/verification/phase12-design-audit.json`.
- **Testler:** `tests/test_design_system.py` (58: gramer, üretilmiş TS/CSS güncel, manifest, stok paket yok,
  CSS ölçekleri sabit, rem/vw yok, kontrast bloğu güncel); APP_SOURCES'a `Glyph.tsx` + `glyphs.generated.ts`.
- **Açık:** Hick 98 (Analiz, 17 komut: üç örnek soru bilinçli tutuldu). Kullanıcı testi/WCAG denetimi yok.
- **Son görsel geçiş (aynı gün):**
  - 15 yüzey × 1440/1024/768/390 × iki tema tarandı; 24 kusur bulundu ve düzeltildi
    (`phase12-design-final-pass.json`).
  - Önemli düzeltme: koyu temada sabit `#fff` degrade metni okunmaz yapıyordu ve ilk denetim bunu kaçırmıştı;
    denetim artık degradeleri ölçüyor.
  - Düzen artık içerik sütununa göre kırılıyor (container query).
  - Ağ etiketleri çakışmıyor; 7. Gemini turunda `compare` glyph'i eklendi.
  - Derleme eski asset'leri temizliyor.
  - Linter: `tools/design/layout_lint.js`.

## ÖNCEKİ — Opus 5.5 devam turu (16 Ekim 2026 akşam) — son durum

**Önce:** `git status --short` (temiz olmalı), `git log --oneline -12`, `gh run list --repo mesely/DataAnalyticsToolv2 --limit 3`
(beş iş: core, nul-scan, tests, benchmark-integrity, analytics). Bu turun commitleri `5aa6123`→`a3e3da6` (hepsi aynı dala
push edildi; tamamlanan her CI koşusu beş iş success). Uygulama 8123 + devIdP 8188 açık bırakıldı (`deploy/phase1/start.sh`).

| # | Birim (commit) | Ne değişti | Kanıt |
|---|---|---|---|
| 1 | Ölçü/dönem bağı (`5aa6123`, `5b09c6e`, `a3e3da6`) | `analysis/narrative.py`: `MEASURES` + `periods()`; sayının önündeki ≤4 ve ardındaki ≤2 kelime (bağlaç/noktalamada durur) başka ölçüyü adlandırıp kendininkini adlandırmıyorsa ret; tarih atıflı dayanağın döneminde olmalı; XML `measure`/`period`. Yerel EN/TR anlatı değişmedi | spec AW-14 binding amendment; `test_narrative.py`; eval narrate 17 (n15–n17) |
| 2 | Soğuk başlangıç (`e8d335f`) | LangChain yalnız model çağrısında import; `status()` sağlayıcısız | run p50 1.483→703 ms, decisions 1.497→733 ms, n=9 aynı betik (`phase11-performance-startup.json`) |
| 3 | Aylık tahmin dilimleri (`111f415`) | `forecast.period_slices` + `final_month_worse_than_naive`; Karar stüdyosu katlanır ay tablosu; rapor tablosu | UCI Kasım 2011 final: mean8 £59.289 vs naif £41.723, bant 2/4 (yöntem değiştirilmedi) |
| 4 | TR teşhisler (`405c6ff`) | teşhis `params` + 12 TR şablon; koruyucu test | tarayıcı: 6 UCI teşhisi Türkçe |
| 5 | Tablo klavye erişimi (`9ab6f56`) | `TableWrap.tsx`: taşarken `tabIndex/role=region/aria-label`; 15 kapsayıcı; APP_SOURCES | tarayıcı 1024/390 px; CI core yeşil |
| 6 | Yerel yönlendirici + harness v2.1 (`87dde64`, `a3e3da6`) | adet/sipariş/en-düşük sıralama ve değişim soruları artık yanlış rakamla yanıtlanmaz; item/SKU/pazar/ay ifadeleri; eval yanıtlanan niyeti ölçer | davranış 13→15/19, niyet 11→15/17 (iyimser; 26 ayrı parafraz `test_local_router.py`) |
| 8 | İki sezonluk veri (17 Ekim, kullanıcı onayıyla indirildi) | `uci2` = UCI Online Retail II (DOI 10.24432/C5CG6D); `python -m analysis.prepare --online-retail-ii <zip>`; 2010-12-01..09 sayfa çakışması doğrulanıp bir kez alınır; katalogda yalnız hazırlanmışsa | aynı protokol seasonal naive seçti: final 12 origin MAE £44.185 vs naif £62.055 (−%28,8), bant 9/12; `phase11-forecast-uci2.json` |
| 7 | UI küçükleri (`5aa6123`, `111f415`) | TR yüzde "%84,6" (eski "84,611%"), TR kapsama "%85/%70", anlatı notları ölçü/dönem reddini adlandırır | tarayıcı receipt `phase11-browser-binding.json` 13/13 |

**Testler (yerel, gerçek):** analytics **305 passed**; NUL/asset 48; web tsc+build; HTTP kabulü 21/21 (`verify_workspace`).
Core TS suite yerelde Docker fixture'ı yüzünden koşmaz → CI'da koşar (son tamamlanan koşular yeşil).

**Bilinçli olarak yapılmayan / olumsuz sonuçlar:** DuckDB 1.5.6 boş olmayan her Python parametre listesinde pandas
yükler (170–500 ms); değerleri SQL'e gömmek yerine bağlı parametre korundu. Kasım final penceresinde seçilen yöntem
naiften kötü; final pencere üzerinde ayar yapılmadı. Bağ kontrolü kelime düzeyinde; anlamsal entailment değil. Canlı
LLM çağrılmadı (402; accuracy null). Disk: tur içinde 577 MB'a düştü; yalnız npm önbelleği silindi (459 MB) → ~1,1 GB.

**Sonraki iş (beklenen etkiye göre):**
1. **Yapıldı (17 Ekim):** iki sezonluk Online Retail II (yukarıda 8). Kalan tahmin işi: bant hâlâ final 9/12 eksik
   kapsıyor; ≥3 sezonluk veya başka perakendeci verisiyle yeni dondurulmuş protokol (mevcut finaller üzerinde ayar yok).
2. Canlı model değerlendirmesi — HF kredi kapısı açılınca `python -m analysis.llm_eval --providers hf` (dış bağımlılık).
3. Kalıcı worker süreci (kalan ~0,6 s pandas/networkx/import başlangıcı) — izolasyon/iptal sözleşmesini etkileyen mimari karar; önce spec.
4. Üretim kapıları (tenant RLS, retention, hard isolation) ve 5–8 gerçek kullanıcı pilotu — ürün/insan kararları.
5. Yerel yönlendiricide kalan: p14 "Compare it with that" (zaman aracına gidiyor, beklenen netleştirme) ve p19 (kâr ifadesi
   nedeniyle ihtiyatlı ret) — değerlendirme setine bakarak ayarlama yapma; önce yeni parafraz seti.

---

## GPT-6.1 Sol → Opus 5.5 Handoff

**ÖNCE BU KARTI OKU (16 Ekim 2026 devam turu).** A11 düzeltmeleri ve gerçek tarayıcı kabulü kapandı. Eski aşağıdaki kartlar tarihsel kayıttır; orijinal A1/T01 listesinden yeniden başlama. Önce `git status`, sonra bu kartın CI kapısı; sonra aşağıdaki ilk görev. Bu konuşmaya veya eski ajan hafızasına ihtiyaç yok.

### Mevcut repo / HEAD / CI

- Repo `/Users/selmanyilmaz/Projects/context-layer`; çalışma kopyası burasıdır. Kullanıcı cwd'si `/Users/selmanyilmaz/Desktop/guncel_cvler` **repo değildir**. Bu dosyanın aynası orada `progress.md`.
- Dal `feat/analytics-workspace-phase4`. Son uygulama commit'i **`2b3f9570ddd141d3945de17eb14abd4d498cfd82`**. Bu kartı/kanıtları içeren doküman commit'i bundan sonra gelir: kesin güncel HEAD için `git rev-parse HEAD` (kendi commit hash'ini aynı dosyaya gömmek mümkün değildir). Uygulama fingerprint'i **`a6f2dff3e356c9ee73f3a7ef5f34ea9f89fe05d9205114e3ea0b6ab9401fa83f`**, source-dependencies-v1,46 dosya.
- Publish: `https://github.com/mesely/DataAnalyticsToolv2.git`; `origin` Alper'in `https://github.com/AlperCamli/DataAnalyticsTool.git` deposudur, oraya push yapılmaz. Aynı açık PR: [#1](https://github.com/mesely/DataAnalyticsToolv2/pull/1). Force push/merge/history rewrite yapılmadı.
- **CI teslim kaydı: [38897028637](https://github.com/mesely/DataAnalyticsToolv2/actions/runs/38897028637), `4107eb733115abafb0c5100e81a50458afe79c2f` üzerinde BEŞ JOB SUCCESS.** Core474 passed/4 skipped; root Python874/17; analytics270/0. Exact receipt `docs/evidence/verification/phase11-ci.json`. Bu sonucu yazan son commit yalnız receipt/cache/devir notlarını değiştirir; en son HEAD/CI eşleşmesinin değişmez kaydı PR#1 açıklamasında ve güncel Checks'tedir. Devralırken bu satır güncel değilse `gh run list --repo mesely/DataAnalyticsToolv2 --branch feat/analytics-workspace-phase4 --limit 3`, ardından `gh run view <id> --repo mesely/DataAnalyticsToolv2 --json headSha,status,conclusion,jobs`. Beş iş: `core`, `nul-scan`, `tests`, `benchmark-integrity`, `analytics`. Eski doğrulanmış koşu38887656628/c96a294 hepsinde success; bunu yeni HEAD yeşili diye sunma.
- Son kod/kanıt tesliminde çalışma ağacı temizdi. Bu son kayıt yalnız CI receipt/cache/devir notlarını içerir ve aynı dala commit/push edilir; final kapısı **clean tree**, kontrol `git status --short` boş çıktı. Final teslimde belgesiz değişiklik bırakılmaz. Kalan değişiklikleri `git status --short` ile doğrula; başka ajanın/user'ın değişikliğini silme.

### Bu oturumda yapılan / dosya / doğrulama

| Birim | Gerçek değişiklik ve dosyalar | Doğrulama |
|---|---|---|
| Tahmin alanı ve bant | `analysis/forecast.py`: bütün adayların dev/final/dilim/next tahmini nonnegative; relative-zero tanısı; final undercoverage uyarısı; coverage ile mean width. `test_forecast.py` regresyonları | 60 haftalık seed5 son12=0 ters bant kapandı; bağımsız forecast+decisions51 passed; UCI seçim/sonuçları korunur |
| Tipli anlatı | `analysis/narrative.py`, `decisions.py`: signed Decimal, unit-aware/EN-TR number syntax, küçük sayılar dahil; final_origins/business_validation kaynakları; unavailable fact+calculation ret; XML ülke filtresi boole. `DecisionStudio.tsx`: mekanik kontrol ≠ anlamsal doğruluk | Yerel TR/EN/negatif senaryo; yanlış tutar/işaret/birim/0/99; filtered XML; gerçek UCI download validator'dan geçti |
| Alım sınırları | `analysis/preparation.py`: Parquet quoted identifiers, single-file access, extensions off,64MB DuckDB/1 thread/no spill, decoded8MB/field4096 sınırı materialization öncesi; nested/blob ret | Meşru tırnaklı sütun, compressed expansion, locale/date/ID testleri ve gerçek HTTP import |
| Kodlama ve mobil | `Preparation.tsx`: UTF8/1252/1254, local text preview, nonUTF8 confirmation, stale file async read guard. `workbench.css`: hazırlama select/label44px | Browser Çýðlýk→Çığlık; onaysız profil/import engeli; 007 korunur;44×290px;390px sayfa taşması yok |
| Tekrarlanabilir kabul | `analysis/verify_workspace.py`; `evaluate_decisions.py --samples/--concurrency` | Gerçek loopback HTTP21/21, kaynak/HEAD/web hash receipt; bounded subprocess6/6 hatasız |
| Kanıt/doküman | `docs/evidence/verification/phase11-*`, `docs/evidence/phase11/*.jpeg`, asset manifest/NUL named allowlist; README/TEST_GUIDE/BENCHMARK_MATRIX/NEXT_BACKLOG/LLM_EVALUATION/spec-index/DECISIONS | Browser16/16; analytics270; son metin sonrası ilgili31; asset/NUL48; web build/tsc geçti |

Kod commit'leri: `0cc3904` (doğruluk + ingestion + encoding), `1b9d66c` (repeatable HTTP/benchmark), `2b3f957` (44px/readability). Devralınan üç gönderilmemiş doküman commit'i `67abaeb`, `084577e`, `98f0600` korunur ve aynı dalda gönderilir. Her şeyin ayrıntısı `docs/phases/PHASE_11_CONTINUATION.md`.

### Claude çalışması — doğrulanan / düzeltilen

AW-14/Phase11 zaten uygulanmıştı: v3 finite-sample quantile, development-only scaling, heteroscedastic fixture, typed narrative, Parquet/decimal/date diagnostics, post-selection ML probability metrics ve lazy pandas import. Bunları sıfırdan yazmadık. Başlangıç temiz98f0600, remote c96a294, eski5-job CI green, HTTP21/21 ve servisler gerçekti. Heteroscedastic mevcut14 forecast testi geçiyordu; fakat final çöküşünde negatif radius kusuru ayrıca vardı.

Eski “her sayı kontrol edilir / ülke adları dışarı gitmez” iddiaları iki gerçek açıkla çelişiyordu; düzeltildi. Son analytics sayısı228 değil254'tü; şimdi270. Eski browser receipt yoktu; şimdi gerçek16/16 var. Country slices zaten UK/NL/EIRE idi; kalan iş **ay/dönem** dilimleri. Parquet core TS testi eski CI'da geçti; açık işler listesinden çıkarıldı. Eski performance36/36 ve eski HF402 kanıtı korunur, yeniden ölçülmüş gibi yazılmaz.

### Ölçüm durumu — bu sayıları karıştırma

**Forecast (MEASURED):** UCI52 tam hafta,34 dev/10 final,mean8,absolute. Dev MAE£30.445 vs naive£33.201. Final MAE **£47.206,66** vs **£59.858,67** (~%21,14 daha düşük), RMSE£61.456,97, MASE1,4218, bias+£47.206,66. Nominal90 coverage dev **22/26=%84,615**, final **7/10=%70**. Mean width dev£124.948,63/final£130.997,26. Next2011-12-05 £308.417,06, [£242.918,43,£373.915,69]. **Kalibre değil.** Dev coverage tuning diagnostic, bağımsız calibration değil. Final üzerinde tuning yok. Kanıt `phase11-forecast-uci.json`.

**Ingestion (VERIFIED):** CSVtext UTF8server source hash; raw nonUTF8 encoding byte receipt iddiası yok. Explicit quantity/price decimalcomma ve date ISO/dmy/mdy/dot; leadingzero IDs değişmez; profile→mapping→preview→receipt-bound owner import. Parquet2MB decoded bytes,10krow,60cols,4096char/field,8MB expanded text,primitive only. CSVfixture dedup2row/2orders/£12,60; dmycp1254 dates2025-02-01..02; ParquetISO2025-01-01..02. Dosyalar `analysis/.local/phase11-qa` ignored, üretici `verify_workspace.fixtures`.

**LLM (BLOCKED/NOT RUN):** Yerel narrative her zaman hazır; model additive/opt-in; repair once sonra local. Validator ID existence+syntax+numbers, **semantic entailment sağlamaz**. `phase11-llm-offline.json`14 narrative adversarial vaka (model değil), acceptance1.00; claims8; plan19,decide6. Son gerçek HF probu16Ekim10:10UTC HTTP402; bu oturumda yeni inference yapılmadı, accuracy/success null kalır. Token yalnız ignored0600 `analysis/.local/hf-provider.json` veya server env; okumaya/yazdırmaya/commitlemeye gerek yok. Tarihsel chat tokenları compromised say; yineleme.

**Browser (MEASURED):** `phase11-browser-qa.json`16 named checks PASS: login/landing/dataset/UCI/default+scenario/6type/evidence/forecast+country slices/reopen+samehash/JSON-MD-XML/CSVlocale/encodingguard/UnicodeID/Parquet/light/dark/390px/keyboard/44px. Native IAB CUA bu tur çalıştı. Viewport reset; localhost app tab deliverable bırakıldı; Gemini user tabı korundu. Bazı ilk ekranlar44px düzeltmesinden öncedir ve dosya adında `before` yazar;04/05/06 finaldir. **NOT MEASURED:** full WCAG/screenreader/zoom/contrast, real-phone,5–8-userpilot,LCP/CLS/click-visible latency. ML probability UI tekrar koşulmadı (değişmeyen yol; önceki HTTP/CI kanıtı ayrı).

**Performance (MEASURED / SERVER):** source1b9d66c, n3/action, concurrency1,6/6 worker success. Forecast p50/p95max148,10/413,63ms; decisions1759,09/1841,67ms. HTTP kabulüyle örtüşen yük vardı; öncesi/sonrası iyileşme veya SLA çıkarma. HTTP/OIDC/PG/browser/HF hariç. Eski9/hücre ve3concurrent benchmark ayrı dosyada tutulur.

### Servisler / disk / güvenli çalışma

- App8123 + devIdP8188 aynı NodePID67076; PG16 localhost5549 PID60336, DBcontextlayer_phase1. Docker kapalı/kullanılamıyor; Docker-only core rig'i tekrar zorlayarak zaman harcama. Mevcut CI'ı kullan.
- `/Users/selmanyilmaz/Projects/context-layer/.venv/bin/python`3.12. Node24 `/Users/selmanyilmaz/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin`; gerekirse PATH'in başına koy.
- Statik web değişikliği `npm --prefix core run build` + reload yeterli. TS backend değişince8123 dinleyen doğru PID'yi SIGTERM ile durdur, `./deploy/phase1/start.sh`; devIdP anahtarı yenilenirse yeniden login. Sağlıklı servis varken duplicate başlatma. Kullanıcı hesapları/fixture detayları launcher ve README'de; gerçek provider secret ayrı.
- Disk başlangıç~2GiB →350MiB dip→ temizleme sonrası~527MiB. Son kontrol sonrası **172,3MiB** yeniden üretilebilir cache geri kazanıldı: yalnız `Library/Caches/Google/Chrome/Profile 1/Code Cache/{js,wasm}` altında2saatten eski ve `lsof` ile açık olmadığı doğrulanmış1180 hash-adlı bytecode blobu. Cache index, cookie/history/session, aktif dosya, runtime, DB, CoreDevice ve unique downloads korunur. Yeni büyük model/dataset/npm reinstall yapma. Sadece adı/amacı doğrulanmış yeniden üretilebilir cache temizlenebilir; `.git`/veri/model/DB/secret/session/kanıt/asset silinmez.
- `port_sources.py` çalıştırma: adapte edilmiş kaynakları overwrite eder. Secret/NUL kontrolü tracked/staged dosyalarda, credential değerlerini çıktıya dökmeden yapılır.

### Açık riskler / başarısız deneyler

**P0:** bulunan açık kritik kusur kalmadı; bu güvenlik/production sertifikası değildir. **P1:** canlı model ölçümü dış kredi kapısı; free-prose semantic claim/metric binding eksik; production tenant+subjectRLS/retention/hard isolation açık. **P2:** nominalin altında final coverage, ≥2sezon gerçek benchmark, ay dilimleri, filtered DuckDB→pandas başlangıcı, TR ekranda İngilizce diagnostic text, full a11y/userpilot. **P3:** OOF stacking, conversation ref, governedBI, retrieval lifecycle, SNIPS baseline ihtiyacı — önceki backlog korunur.

Olumsuz sonuçlar: final coverage%70 kaldı; gerçek model accuracy ölçülmedi. İlk final-warning testindeki tek sıçrama naive sonraki haftalarda uyduğu için <%80 yaratmadı; çoklu sıçrama oracle'ı ile değiştirildi. DuckDB allowed_paths connect config'de çalışmadı; connection sonrası bound SET→external off→lock yolu test edildi. `.jpg` named-image testinden geçmedi; gerçek JPEG'ler `.jpeg` yapıldı, geniş binary exemption eklenmedi. Formatter offline cache yoktu, resmi küçük npm paketi kullanıldı. Ingestion reviewer otomatik araç engeliyle tamamlanamadı; ana ajan meşru quoted-name/expansion testleriyle bulguyu doğrulayıp kapattı; forecast/narrative review ve düzeltme review'ları tamamlandı.

### Sonraki beş görev — beklenen etkiye göre

| Sıra | Neden / iş | Dosyalar | Komut/test ve kabul kapısı |
|---:|---|---|---|
|1| **Model fact/calculation için metric/period/unit binding**. Geçerli sayı yanlış ölçüme bağlanabiliyor; semantic entailment henüz yok | Önce AW14'e additive spec; `analysis/narrative.py`, `decisions.py`, `llm_eval/cases.py`, `test_narrative.py`, `DecisionStudio.tsx` | `.venv/bin/python -B -m pytest analysis/tests/test_narrative.py analysis/tests/test_llm_eval.py analysis/tests/test_decisions.py -q`; valid-id/wrong-metric ve wrong-period örnekleri reddedilmeli veya model olgu/hesap metni kanonik yerel render'a çevrilmeli; mevcut yerel anlatı değişmemeli; live accuracy null kalmalı |
|2| Gerçek provider erişimi gelince dondurulmuş TR/EN plan/decide/narrate eval. Scripted1.00 model başarısı değildir | `analysis/llm.py`, `analysis/narrative.py`, `llm_eval/{cases,providers,evaluate}.py`, LLM_EVALUATION | `.venv/bin/python -B -m analysis.llm_eval --providers hf` yalnız mevcut izinli erişimle; kredi/hesap/ödeme/endpoint değişikliği otomatik yok. Her görevin gerçek yanıt/latency/tokens, unsupportednumeric/citation/refusal raporu; blocked görev null; ≥50 TR/EN golden ayrık geliştirme/eval |
|3| Forecast final undercoverage ve dönem dilimleri; kapsam×genişlik birlikte | `analysis/forecast.py`, `test_forecast.py`, `test_decisions.py`, DecisionStudio; AW14 | Mevcut `.venv/bin/python -B -m pytest analysis/tests/test_forecast.py analysis/tests/test_decisions.py -q`; ay/level dilimleri aynı final origins, dev-only seçim ve coverage/width/n. Yeni yöntem için yeni dondurulmuş değerlendirme veri/protokolü; mevcut10final üzerinden tuning yok |
|4| Filtered request başlangıcı/HTTP performansı | `analysis/worker.py filters_for`, `forecast.py`, `evaluate_decisions.py`, core workbench admission | `.venv/bin/python -B -m analysis.evaluate_decisions --samples 9 --concurrency 1 3`; filtered/unfiltered ayrı kontrollü worker+HTTP receipts, noSQLinterpolation/securityregression; p50/p95+hata/timeout/cancel. Düşük disk koşulunda büyük stress başlatma |
|5| Gerçek erişilebilirlik/kullanılabilirlik ve üretim kapıları | TEST_GUIDE, `core/web/src/workbench`, `core/src/workbench.ts`, migration0017–0021, NEXT_BACKLOG | Screenreader/zoom/contrast +5–8 gerçek kullanıcı görev zamanı/hata; synthetic katılımcı yok. TR diagnostic localization ve table keyboard scroll; production için tenant/retention/OSlimits ayrı spec/test ve yetkili deployment |

### Opus'un TAM İLK GÖREVİ

Repo kökünde `git status --short`, `git log -6 --oneline` ve PR'nin en güncel CI'ını kontrol et; yeni user değişikliğini koru. Sonra **görev1**: mevcut narrative typed contract'ı okuyup metric/period/unit bağlamını doğrulayan küçük additive sözleşmeyi önce spec'e yaz. Geçerli ID ve aynı sayıyı yanlış ölçüme bağlayan karşı örnekleri testte göster; model fact/calculation'larını yalnız gerçek ölçüme bağlayarak veya yerel kanonik render kullanarak kapat. Büyük yeniden yazım ve gerçek provider çağrısı gerektirme. Yerel TR/EN narrative/owner/hash/fallback, mevcut forecast split ve270 analytics regresyonu korunmalı. Rapor/README/progress/mirror güncelle, ilgili browser+CI kapısı, coherent commit/publish; sonra sıradaki işi sürdür.

### Kaynak projeler ve kanıt girişleri

Gerçek adaptasyon ledger'ı `docs/phases/REUSE_LEDGER.md`, kaynak hash'leri/commitleri orada. Beş orijinal kaynak korunur:

- [AlperCamli/DataAnalyticsTool](https://github.com/AlperCamli/DataAnalyticsTool.git) — platform/auth/governance; originalremote readonly.
- [mesely/adviSU](https://github.com/mesely/adviSU.git) — gerçek BM25/provider/guardrail/confidence/language/formatter/export/hash adaptasyonları; yalnız esin değil.
- [mesely/PoliEcoTRNetSci](https://github.com/mesely/PoliEcoTRNetSci.git) — network ve temporal yöntem adaptasyonları.
- [mesely/Influencer-Category-and-Like-Prediction-Stacking-SMOTE-RF](https://github.com/mesely/Influencer-Category-and-Like-Prediction-Stacking-SMOTE-RF.git) — fold-local preprocess/RMSLE; notebook skorları taşınmadı, eğitim burada ölçülür.
- [mesely/NLP-Intent-Detection-with-SNIPS-Dataset](https://github.com/mesely/NLP-Intent-Detection-with-SNIPS-Dataset.git) — araştırılmış, runtime LSTM ertelendi; uygun analytics intent corpus ve TFIDF baseline faydası olmadan zorlanmaz.

Okuma sırası: `CLAUDE.md` → `specs/spec-index.md` → `specs/analyst-workspace-phase11.md` → `docs/phases/PHASE_11_CONTINUATION.md` → `docs/phases/TEST_GUIDE.md` → NEXT_BACKLOG. Benchmark/LLM etiketlerini koru; *not measured* alanlarına puan/başarı uydurma. Bu kartın sonundaki “TAM İLK GÖREV” uzun tarihçeden daha güncel talimattır.

---

## Tarihsel kartlar — aşağıdaki durumlar kendi commit/tarihlerine aittir

## ŞİMDİ OKU — 16 Ekim 2026, öğleden sonra turu (AW-14, yeni ajan)

**Güncel kod: bu kartın altındaki commitler. e4f82af publish dalına push edildi → GitHub CI
https://github.com/mesely/DataAnalyticsToolv2/actions/runs/38886787881 **BEŞ JOB YEŞİL** (nul-scan, tests, core, benchmark-integrity,
analytics; core suite Parquet rotasını da kapsar). Sonraki doküman/perf commitleri push edilince yeni koşu doğrulanmalı.** Başlangıç durumu doğrulandı: 59aa444 CI 5 job yeşil; 228 analitik test yerelde geçti; uygulama ayaktaydı;
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


## Güncel devam girişini kaybetme — 16 Ekim 2026, GPT-6.1 Sol devam turu

Bu uzun dosyanın tarihsel son satırları güncel durum değildir. **Üstteki “GPT-6.1 Sol → Opus 5.5 Handoff”** kartı ve `docs/phases/PHASE_11_CONTINUATION.md` geçerlidir. Repo `/Users/selmanyilmaz/Projects/context-layer`, dal `feat/analytics-workspace-phase4`; güncel hash'i Git'ten oku. A11 browser16/16 ve HTTP21/21 tamam; model accuracy null ve forecast final90 coverage%70. İlk yeni iş: model fact/calculation için metric/period/unit binding; mevcut geçerli-ID/sayı kontrolünü anlamsal ispat sayma. Üst kartta dosya/komut/kabul kapısı ve kalan5iş var. Kaynak adaptasyonları ve orijinal roadmap korunur; A1'den başlama, `port_sources.py` çalıştırma, provider secret yazdırma.
