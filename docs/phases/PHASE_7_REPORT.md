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
