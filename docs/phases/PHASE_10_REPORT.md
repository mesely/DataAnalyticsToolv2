# Aşama10 — yerel değerlendirme ve teslim kanıtı

16 Ekim2026. Aşama7–10'un yeni tahmin/karar/görünüm ek paketleri uygulandı;
eski geniş backlog tamamlanmış sayılmaz. Gerçek kullanıcı pilotu, üretim
RLS/resource/retention, Parquet/genericmetrics/OOF, liveBI ve başarılı canlı
LLM değerlendirmesi açıktır. Güncel CI/browser sonucu progress üst/son kart ve
`docs/evidence/verification/phase10-*` içindedir.

## Önce / sonra

| Alan | Aşama6 sonu | Bu teslim |
|---|---|---|
| Görünüm | Açık tema, sınırlı özgün nav | Açık+koyu lacivert/füme;6Gemini raster/37SVG; sade kaynak metni |
| Predictive | CSV supervised ML | Ek olarak one-week retail forecast, development seçim/4-origin holdout, naif karşılaştırma |
| Prescriptive | Yok | Açık fiyat/hacim/bütçe senaryosu; nedensel optimizer değil |
| Karar desteği | Hesaplanan açıklama | Sıralı inceleme adayları, mekanik dayanak skoru, eksikler ve3adımlı plan |
| LLM bağlamı | Soru+staticrouting | Ek olarak veri-minimize XML, BM25 yöntem retrieval, strict candidate selection |
| Rapor | CSV/XLSX/analysisJSON | Owner karar arşivi, yeniden açma, source-linked inspector, MD/JSON/XML |
| CanlıLLM | Gerçek402 | Yeni tokenla da gerçek402; başarı/accuracy ölçülemedi |

## Ölçülmüş tahmin hatası

530,104satırlık tarihî UCI;52tamhafta, geliştirme seçiminden ayrı son4rolling
origin. Mean4 seçildi. MAE£55,787.19 / RMSE£68,309.83 / WAPE0.15945457;
naif MAE£41,723.39 / WAPE0.11925650. Seçilen yöntem bu testte **daha kötü**.
Testi gördükten sonra yöntem değiştirilmedi. Aday tahminin temporal skor20'si0.
2011-12-05 haftası noktası£349,862.60; ampirik bant£273,228.45–£426,496.76.
Bu2026ticaret tahmini ve kalibre edilmiş olasılık aralığı değildir.

Son tam hafta£324,370.83 üzerinden varsayımsal%5hacim/%0fiyat:
£340,589.37brüt, £16,218.54fark. Bütçe ayrı; kâr/ROI/causal uplift değil.

## Tekrarlanabilir performans gözlemi

Komut `.venv/bin/python -m analysis.evaluate_decisions`.
Tam subprocess başlangıcı+JSON+hesap; **HTTP/OIDC/PG/browser/HF dahil değil**.
Warmcache, küçükörneklem, makineyükü kontrol edilmedi. Her hücre9istek;
örnekp95 bu büyüklükte en kötü gözleme eşittir. ProdSLA veya3kullanıcı HTTP
stress sonucu değildir. İlk koşu da saklandı; yalnız hızlı koşu seçilmedi.

| İş | Eşzamanlıworker | n | p50ms | örnekp95ms | Hata |
|---|---:|---:|---:|---:|---:|
| forecast | 1 | 9 | 357.28 | 796.16 | 0 |
| forecast | 3 | 9 | 413.50 | 462.59 | 0 |
| decisions | 1 | 9 | 1137.99 | 4507.52 | 0 |
| decisions | 3 | 9 | 3353.78 | 3884.89 | 0 |

JSON: `phase10-performance.json`; önceki gözlem `phase10-performance-initial.json`.
Dar kapsam36/36başarılı; kuyruk, gerçek ağ, tarayıcı ve sağlayıcı süreleriyle
birleştirilmiş uçtanuca hizmet garantisi verilmez.

## Doğrulama

-207analytics pytest PASS;33yeni karar/tahmin testi dahil. Tarihsel50mock
  plannercontract fixture gerçek model accuracy'si değildir.
-48asset/NULtest PASS;12pinnedupstream SHA doğrulandı; webbuild/tsc ve
  Pythoncompileall geçti. Son görseller eklenince namedexception/manifest tekrar doğrulanır.
-Yerel core test başlatıcısı Dockerconnector fixture'ında durdu,60testskip;
  buPASSdeğil. GitHubDockerregresyonu ayrıca yürütülür.
-İlk2bc/a71koşusundaki iki testharness uyumsuzluğu giderildi: anonimPOST
  rawfetch ile, assetMIMEtest yeniapp-icon adıyla; güvenlik koşulu gevşetilmedi.
-Tarayıcı UCI karar hesabı19960sipariş/52hafta/%5senaryo; evidence ülketablosu
  odaklandı. JSON/MD/XML gerçek indirildi, XML kayıtla aynı ve ürün/ülke adı içermiyor.
-Son görünüm/aynıkartreopen/mobil/keyboard kabulü ve son CI receipt'i
  `phase10-browser-qa.json` / `phase10-github-final.json` içine işlenir.

## Bulunan sınırlamalar ve sonraki deney

1. Gerçek HF402: başarılı canlı cevap0, doğruluk **null**, müşteri tokenı
   serverignored0600. Ücret/izin değişikliği yapılmadı. Önce erişim, sonra
   dondurulmuş TR/EN golden+OOD/injection/refusal/citation değerlendirmesi.
2. Tahmin referanstan kötü; yeterli veriyle seasonal-naive/drift/calendar
   adaylarını yalnız yeni development protokolünde karşılaştır. Bu holdout'u
   tekrar tekrar tuning için kullanma; yeni untouched dönem ayır.
3. Aralık coverage kalibre edilmedi;4test noktası güç iddiasına yetmez.
4. İşverisi eksik: iade/marj/stok/elastikiyet yok; businessvalidation0.
5. Payloadschema güvenliği gerçekLLM anlamsal doğruluğu veya strateji başarısı değildir.
6. Worker sürelerinde yük kaynaklı değişkenlik var; HTTP admission/cancel/
   backpressure ve hardisolation/5M ölçüm ayrı iş.
7. Kademe10'un gerçek5–8kullanıcıpilot ve tam erişilebilirlik sertifikası
   gerçekleştirilmedi. Sonraki agent bu işleri sahte katılımcıyla kapatamaz.
