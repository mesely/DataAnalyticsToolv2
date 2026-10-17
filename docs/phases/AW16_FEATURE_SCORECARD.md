# AW-16 özellik olgunluk karnesi (17 Ekim 2026)

Kod dışa aktarma, Grafik stüdyosu, dayanak ağacı, portreler ve maskot için 100 üzerinden olgunluk puanları. Eşik: her özellik ≥ 90 ve hiçbir ölçütte sıfır yok. Her satır bir kanıta
dayanır; kırılan puanlar gerekçesiyle yazılır. Bu bir mühendislik öz değerlendirmesidir: kullanıcı araştırması veya
bağımsız denetim değildir.

## Ölçütler

| Ölçüt | Ağırlık | Neye bakıldı |
|---|---:|---|
| Doğruluk | 20 | Bağımsız hesaplarla karşılaştıran testler, uçtan uca çalıştırma |
| Tekrarlanabilirlik | 10 | Deterministik çıktı, hash'ler, kendi kendini doğrulama |
| Güvenlik ve yönetişim | 15 | Kimlik/CSRF, sahiplik, girdi sınırları, denetim kaydı, gizlilik |
| Dürüstlük | 10 | Model sayı üretmiyor mu, varsayımlar ve sınırlar söyleniyor mu |
| Tasarım ve erişilebilirlik | 15 | DOM denetimi (Fitts, kontrast, ritim, tip, hizalama), layout lint, klavye |
| Yerelleştirme | 5 | Türkçe/İngilizce arayüz, sunucu metinleri |
| Performans | 10 | Ölçülmüş işçi süreleri |
| Belgeleme | 10 | Spec, README, kaynak belgeleri, teslim edilen dosyaların kalitesi |
| Doğrulanmamış yollar | 5 | Canlı veya insan testi yapılmayan kısımlar |

## Kod dışa aktarma — 98 / 100 (önce 96)

| Ölçüt | Puan | Kanıt / kırım |
|---|---:|---|
| Doğruluk | 20 | Paket repodan bağımsız bir klasörde `--check` ile çalışıyor. Grafik katmanları (aralık, trend, bant, hareketli ortalama) betikte yeniden hesaplanıyor; altı UCI paketi Chart Studio değerleriyle kuruş düzeyinde, R² ve p 1e-6 içinde eşleşiyor. `analysis.sql` aynı değerleri DuckDB toplamlarıyla veriyor. |
| Tekrarlanabilirlik | 10 | Aynı kapsamın zip'i byte'ı byte'ına aynı; beklenen değerler tam sayı. |
| Güvenlik ve yönetişim | 15 | Sahiplik, CSRF ve denetim kaydı var. Yüklenen veriden gelen ülke adı (tırnak, ters bölü, yeni satır, kod çiti) Python'a, SQL'e ve README'ye kaçışlı yazılıyor; bunu bir test doğruluyor (inceleme sırasında bulunan açık kapatıldı). |
| Dürüstlük | 10 | README katmanın varsayımını ve sınırını yazıyor; aralık sınırları yalnız Python'da, SQL dosyası bunu söylüyor. |
| Tasarım ve erişilebilirlik | 14 | Denetim tüm genişlik ve temalarda 100. −1: README önizlemesi Markdown'ın bir alt kümesi. |
| Yerelleştirme | 5 | Üretilen yorumlar seçilen dilde. |
| Performans | 10 | Python dosyası p50 104 ms, Fransa paketi 404 ms, tam paket 742 ms. |
| Belgeleme | 10 | Spec §1, değişiklik A3 ve inceleme düzeltmeleri; paket README'si katmanı anlatıyor. |
| Doğrulanmamış yollar | 4 | −1: Bir geliştiriciyle görev testi yapılmadı. |

## Grafik stüdyosu — 94 / 100 (önce 91)

| Ölçüt | Puan | Kanıt / kırım |
|---|---:|---|
| Doğruluk | 20 | Dışlama artık destekleniyor ("İngiltere hariç", "except UK and EIRE", geri ekleme). Yerel planlayıcı 24 değerlendirme isteğinin 24'ünü doğru planlıyor (`phase12-llm-eval.json`). 478 analiz testi geçiyor. |
| Tekrarlanabilirlik | 10 | Her sonuçta `output_sha256`, SQL ve parametreler var. |
| Güvenlik ve yönetişim | 15 | Ülkeler katalogla doğrulanıyor ve `NOT IN (?)` ile bağlanıyor. Model planı aynı doğrulamadan geçiyor; bilinmeyen dışlanan ülke `invalid_plan` veriyor. |
| Dürüstlük | 10 | Yorum yalnız hesaplanan değerlerden yazılıyor ve her cümle kanıt anahtarı taşıyor. |
| Tasarım ve erişilebilirlik | 14 | Denetim 100. −1: grafik noktaları klavyeyle tek tek gezilemiyor; Veri sekmesi bunu karşılıyor. |
| Yerelleştirme | 5 | Türkçe ve İngilizce istekler, Türkçe ülke adları. |
| Performans | 9 | −1: aralık ve trend istekleri hâlâ yaklaşık 0,6 s. |
| Belgeleme | 10 | Spec §2 ve A1/A2, README hattı, test rehberi. |
| Doğrulanmamış yollar | 1 | −4: Canlı Llama doğruluğu ölçülmedi. Hugging Face hesabı 402 (kredi yok) döndü. Kendi barındırılan uç nokta yolu yalnız sahte bir sunucuyla test edildi; Drive'daki Llama'yı bu makinede (8 GB RAM, 2,4 GB boş disk) çalıştırmak mümkün değildi. Kullanıcı görev testi yapılmadı. |

## Dayanak ağacı — 97 / 100 (yeni)

| Ölçüt | Puan | Kanıt / kırım |
|---|---:|---|
| Doğruluk | 19 | Bağlar yalnız paylaşılan kanıt kimliklerinden türetiliyor. Numaralama ve ebeveyn seçimini 3 birim testi sabitliyor. −1: Türetilen bağın analistin amaçladığı bağla örtüştüğü kullanıcıyla doğrulanmadı. |
| Tekrarlanabilirlik | 10 | Aynı ifadelerden her zaman aynı ağaç çıkıyor; model yargısı yok. |
| Güvenlik ve yönetişim | 15 | Yalnız sunucunun doğruladığı ifadeleri gösteriyor. |
| Dürüstlük | 10 | Kanıt paylaşmayan ifade kök kalıyor; bağ uydurulmuyor. |
| Tasarım ve erişilebilirlik | 15 | Beş seçenek puanlandı (seçilen 88,8). Yapı iç içe `ol` listeleri ve kimlik etiketlerinden oluşuyor. Üzerine gelme vurgusu ek kontrol değil. Denetim 100. |
| Yerelleştirme | 5 | Türkçe ve İngilizce önekler (O/H/Ç… ve F/C/I…). |
| Performans | 10 | İstemcide tek geçişte kuruluyor. |
| Belgeleme | 10 | UX_DECISIONS puan tablosu, spec ve test rehberi. |
| Doğrulanmamış yollar | 3 | −2: Kullanıcı testi yapılmadı. |

## Portreler ve maskot — 97 / 100 (önce 88)

| Ölçüt | Puan | Kanıt / kırım |
|---|---:|---|
| Doğruluk | 20 | 10 portre tek kelimelik adlarla sunuluyor; seçim sunucuda kalıcı. CI testi 10 kimliği ve izin listesini doğruluyor. |
| Tekrarlanabilirlik | 10 | Dosya hash'leri manifestoda; maskot ayırma yöntemi PROVENANCE'ta yazılı. |
| Güvenlik ve yönetişim | 15 | Serbest URL yok. Giriş sayfası yalnız `data:image/png;base64` kabul ediyor. |
| Dürüstlük | 10 | İnsan portreleri kurgusal karakter olarak istendi; üretim ve ayırma yolu açıkça yazılı. |
| Tasarım ve erişilebilirlik | 15 | Maskot dört pozda yedi yerde kullanılıyor; hepsi dekoratif ve 2× çözünürlükte. Denetim ve lint 100. |
| Yerelleştirme | 5 | Adlar Türkçe ve İngilizce. |
| Performans | 9 | −1: El sallayan maskot 102 KB PNG (WebP aracı yok). |
| Belgeleme | 8 | −2: Gemini'nin özgün dosyası değil, 794–800 px yakalama kullanıldı. |
| Doğrulanmamış yollar | 5 | İstenen insan portreleri üretildi. |
