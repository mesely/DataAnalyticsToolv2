# Aşama7 — tahmin ve görünüm ek paketi

16 Ekim2026. AW-10 uygulanmıştır. Önceden planlanan Parquet/genel semantik
compiler/OOF stacking kapanmadı; aşağıdaki teslim bunların yerine tamamlandı
iddiası değildir. Ana devir: progress.md; tüm kabul: PHASE_10_REPORT.md.

- `analysis/forecast.py`: kayıtlı kapsamın tam Pazartesi–Pazar haftaları;
  en az16/en fazla260 hafta. İlk/son kısmi hafta dışarıda, aradaki gözlemsiz
  günler sıfır; veri toplama bütünlüğü kanıtlanmış sayılmaz.
- Son-hafta ve son4hafta ortalaması. İlk4haftadan sonra one-step rolling
  development; son4 origin seçimden ayrı. Önceki test haftası sonraki
  origin için artık gözlenmiştir; bu sabit-origin dört-adım tahmini değildir.
- MAE/RMSE/WAPE ve her origin gerçek/tahmin. Development mutlak hatalarının
  ampirik90.yüzdeliği bant; kalibre edilmiş coverage garantisi yok.
- UCI52tamhafta: development mean4 seçti; holdoutMAE£55,787.19,
  naif£41,723.39. Naifi geçemedi uyarısı var; son testte yöntem değiştirilmedi.
- İnceleme amaçlı2011-12-05 haftası projeksiyonu£349,862.60;
  güncel2026ticaret tahmini değildir.
- `BrandIcons.tsx`, `assets/PROVENANCE.md`: Gemini web'den app-icon.jpeg,
  33yeniSVG(brand dahil), toplam6raster/37SVG. Eski4navkorundu.
- Navy/füme dark + light, OS başlangıcı ve bellekte manuel toggle; browser
  persistence yok. Kaynak · Açık veri düzmetin; yeşil rozet kaldırıldı.
- Model/karar işlemleri dört ana navı artırmadan açıklamalı girişlerde.

Spec: `specs/analyst-workspace-phase7.md`. Test: `analysis/tests/test_decisions.py`.
UI: `DecisionStudio.tsx`, `Workbench.tsx`, `workbench.css`.

## Güncelleme 16 Ekim gece — tahmin protokolü v2 (`weekly-gross-v2`)

Önceki sürüm yalnız naif ile son-4-hafta ortalamasını karşılaştırıyor, son4 origin'i holdout sayıyordu ve seçilen
mean4 o pencerede naiften kötüydü (MAE £55.787 / naif £41.723). Yeni protokol kodda sabitlendi, veri görülmeden
kural olarak yazıldı: **kayıtlı adaylar** naive, seasonal_naive (yalnız ≥104 hafta), drift, mean2/4/8,
SES α 0,2/0,5/0,8, sönümlü Holt (α 0,3 ve 0,6); **seçim yalnız geliştirme origin'lerinde en düşük MAE**, eşitlikte
daha basit yöntem; **final pencere** = son min(12, max(4, n//5)) origin, seçimden sonra her aday için
hesaplanır ve seçimi etkilemez. Metrikler MAE/RMSE/WAPE/sMAPE/MASE (geliştirme naif MAE'sine ölçekli)/bias;
MAPE bilinçli olarak yok. Teşhisler: seasonal_naive_unavailable, zero_weeks, outlier_weeks, possible_level_shift,
unstable_development_error, small_selection_margin, final_window_worse_than_naive. Bant: geliştirme mutlak
hatalarının %80/%90 ampirik yarıçapı; final penceredeki kapsama betimseldir, kalibrasyon iddiası değildir.

UCI 52 tam hafta (34 geliştirme origin, final 10): `docs/evidence/phase10/forecast-v2-uci.json`.

| yöntem | geliştirme MAE £ | geliştirme MASE | final MAE £ | final MASE | final sMAPE | final bias £ | naife göre |
|---|---:|---:|---:|---:|---:|---:|---:|
| **mean8 (seçildi)** | 30.445 | 0,917 | 47.207 | 1,422 | 0,163 | +47.207 | +21,1 % |
| ses_0.5 | 31.517 | 0,949 | 45.927 | 1,383 | 0,157 | +11.851 | +23,3 % |
| ses_0.2 | 31.556 | 0,950 | 48.663 | 1,466 | 0,167 | +46.420 | +18,7 % |
| mean4 | 31.643 | 0,953 | 39.678 | 1,195 | 0,133 | +20.226 | +33,7 % |
| ses_0.8 | 32.443 | 0,977 | 52.713 | 1,588 | 0,181 | +1.267 | +11,9 % |
| naive | 33.201 | 1,000 | 59.859 | 1,803 | 0,208 | −1.440 | 0 |
| mean2 | 35.157 | 1,059 | 43.042 | 1,296 | 0,143 | +2.874 | +28,1 % |
| holt_damped_0.6_0.1 | 35.165 | 1,059 | 49.727 | 1,498 | 0,168 | −1.904 | +16,9 % |
| drift | 35.722 | 1,076 | 60.524 | 1,823 | 0,211 | −775 | −1,1 % |
| holt_damped_0.3_0.1 | 46.803 | 1,410 | 41.484 | 1,249 | 0,140 | +16.117 | +30,7 % |

Okuma: geliştirmede seçilen mean8 final pencerede naifi %21 geçer; ama her adayın final MASE'si 1'in üstündedir,
çünkü final pencere (2011 Ekim–Aralık tatil rampası) geliştirme dönemlerinden zordur ve pozitif bias (gerçek >
tahmin) sistematik düşük tahmini gösterir. mean4 final pencerede daha iyi olurdu; seçim geliştirmeye bağlı olduğu
için değiştirilmedi. %80/%90 bantların final kapsaması 0,70 → bant kalibre değildir (UI uyarısı korunur).
Teşhisler: seasonal naive yok (52 hafta), 1 sıfır hafta, aykırı haftalar 2010-12-27 / 2011-11-07 / 2011-11-14,
son 8 haftada olası seviye kayması. Eski son-4 holdout sonucu tarihsel olarak PHASE_10_REPORT'ta durur; iki
sonuç farklı pencereleri ölçer, biri diğerini geçersiz kılmaz.

## Güncelleme 16 Ekim öğleden sonra — bant geçerliliği v3 (`weekly-gross-v3`, AW-14)

Seçim protokolü değişmedi (aynı adaylar, aynı geliştirme-only seçim, aynı final pencere; UCI'de yine **mean8**). Değişen
yalnız belirsizlik bandı: iki ölçek kayıtlı (**absolute** pence, **relative** = |hata|/tahmin × nokta tahmin); hangisinin
kullanılacağı **yalnız geliştirme origin'lerinde yuvarlanan kapsama** ile seçilir — her origin'in yarıçapı yalnız daha
önceki geliştirme artıklarından hesaplanır (8 artık birikince başlar). Eşitlik absolute'a döner. Kuantil, sonlu-örneklem
split-conformal indeksi ⌈(n+1)·düzey⌉'dir; indeks n'i aşarsa en büyük artık kullanılır (bu hâlâ eksik kapsayabilir).
Final pencere ölçek seçimine girmez; kapsaması betimseldir. `calibrated` false kalır. Yeni teşhis
`band_undercovers_development` (%90 bandı geliştirmede <%80 kapsarsa). Kanıt `docs/evidence/phase10/forecast-v3-uci.json`.

| UCI 52 hafta, mean8 | %80 | %90 |
|---|---:|---:|
| Geliştirme yuvarlanan kapsama · absolute (26 değerlendirilen origin) | 0,731 | 0,846 |
| Geliştirme yuvarlanan kapsama · relative | 0,731 | 0,846 |
| Seçilen ölçek | absolute (eşitlik) | |
| Yarıçap (tüm geliştirme artıkları) | £50.924 | £65.499 |
| Final pencere kapsaması (10 origin, betimsel) | 0,70 | 0,70 |

Okuma: conformal indeks %90 bandının geliştirme kapsamasını eski düz kuantile göre 0,77 → 0,85'e çıkardı; nominalin
hâlâ altında. Final penceredeki 0,70 değişmedi (tatil rampası dağılım kaymasıdır). Bant **kalibre değildir** ve UI bunu
geliştirme/final kapsama sayılarıyla birlikte söyler. 2011-12-05 noktası £308.417,06; bant £242.918,43–£373.915,69.
Bu 2026 ticaret tahmini değildir. Testler: `analysis/tests/test_forecast.py` (+5: conformal indeks oracle, yalnız-geçmiş
artık kapsama oracle, heteroskedastik seride relative seçimi, final pencerenin ölçek seçimini değiştiremediği, teşhis).
