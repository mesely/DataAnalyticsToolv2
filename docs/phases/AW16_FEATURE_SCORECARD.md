# AW-16 özellik olgunluk karnesi (17 Ekim 2026)

Kod dışa aktarma, Grafik stüdyosu ve analist portreleri için 100 üzerinden olgunluk puanları. Her satır bir kanıta
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

## Kod dışa aktarma — 96 / 100

| Ölçüt | Puan | Kanıt / kırım |
|---|---:|---|
| Doğruluk | 20 | Paket repodan bağımsız bir klasörde `--check` ile çalışıyor (Fransa kapsamı + grafik: 11/11). SQL dosyası aynı KPI'ları üretiyor. Beklenen değerler, motorun kendi `overview()` sonucuyla karşılaştırılmadan paket verilmiyor. 16 test (kullanıcı başlığının SQL yorumundan kaçamadığını doğrulayan test dahil). |
| Tekrarlanabilirlik | 10 | Aynı kapsam iki kez dışa aktarılınca zip byte'ı byte'ına aynı; dosya başına SHA-256; tam sayı beklenen değerler. |
| Güvenlik ve yönetişim | 15 | Uç nokta sahiplik + CSRF + denetim kaydı içeriyor; başkasının verisi 404 dönüyor (CI testi). Müşteri kimliği dışa aktarılmıyor. Çıktı sınırı yalnız bu uç için 12 MB. |
| Dürüstlük | 10 | README brüt satış ≠ net gelir, iptaller, hizmet satırları gibi sınırları yazıyor. |
| Tasarım ve erişilebilirlik | 14 | Denetim 100 (Hick 98, arka sayfadan geliyor). Linter temiz. Kod görünümü klavyeyle odaklanabiliyor. −1: README önizlemesi Markdown'ın bir alt kümesi, figürler yer tutucu olarak gösteriliyor. |
| Yerelleştirme | 5 | Tüm dosyalar Türkçe veya İngilizce üretiliyor. Veri seti adı ve açıklaması kaynak dilinde kalıyor (bilinçli). |
| Performans | 10 | Python dosyası p50 104 ms, Fransa paketi 404 ms, 530 bin satırlık tam paket 742 ms. |
| Belgeleme | 10 | Spec §1 + sonuçlar; paket README'si kapsam, sözlük, değişiklik tarifleri ve yeniden üretim adımlarını içeriyor. |
| Doğrulanmamış yollar | 2 | −3: Paketin dışa aktarılan Chart Studio grafiği yalnızca temel seriyi taşıyor; aralık, trend ve bant betikte yeniden uygulanmıyor. Bir geliştiriciyle görev testi yapılmadı. |

## Grafik stüdyosu — 91 / 100

| Ölçüt | Puan | Kanıt / kırım |
|---|---:|---|
| Doğruluk | 19 | 79 test: planlayıcı (TR/EN, iyileştirme, kaldırma), istatistikler bağımsız scipy.stats/numpy ile karşılaştırılıyor, kısmi dönemler. −1: "İngiltere hariç" gibi dışlama istekleri ifade edilemiyor (`no_change` dönüyor). |
| Tekrarlanabilirlik | 10 | Her sonuçta spec + veri + katmanların `output_sha256` değeri; SQL ve parametreler görünüyor. |
| Güvenlik ve yönetişim | 15 | Model çıktısı sıkı şemadan geçiyor, kullanıcı metni güvenilmez veri sayılıyor, girdi koruması var, istek ≤ 500 karakter; sahiplik/CSRF/denetim (CI testi). |
| Dürüstlük | 10 | Sayıları yalnızca yerel motor üretiyor. Toplamlar için aralık reddediliyor ve kontrol bandına çevriliyor. Varsayımlar cümle olarak yazılıyor. Sıfırın altına inen bıyıklar kesiliyor ve bu dipnotla söyleniyor. |
| Tasarım ve erişilebilirlik | 14 | Denetim 100 (Hick 98). Linter 1280/390 px'te iki temada temiz. Veri ve SQL sekmeleri grafiğin erişilebilir karşılığı. −1: grafik noktaları klavyeyle tek tek gezilemiyor (Veri sekmesi telafi ediyor). |
| Yerelleştirme | 5 | Planlayıcı Türkçe ve İngilizce anlıyor; plan çipleri ve notlar etiketlenmiş. |
| Performans | 9 | Aylık ve karşılaştırma istekleri ~350 ms. Aralık ve trend istekleri 1,51 s'den 0,61 s'ye indi. −1: SciPy özel fonksiyonlarının yükleme maliyeti hâlâ ~0,3 s. |
| Belgeleme | 10 | Spec §2 + sonuçlar, README turu, GIF. |
| Doğrulanmamış yollar | −1 | −6: Canlı Llama planlama yolu HTTP 402 nedeniyle hiç gerçek modelle çalışmadı (yalnızca enjekte model). Kullanıcı görev testi yapılmadı. |

## Analist portreleri ve ürün işareti — 88 / 100

| Ölçüt | Puan | Kanıt / kırım |
|---|---:|---|
| Doğruluk | 20 | Seçim sunucuda kişi başına saklanıyor ve yeniden yüklemede kalıyor (tarayıcıda doğrulandı); izin listesi dışı değer 400 (CI testi). |
| Tekrarlanabilirlik | 10 | Varsayılan portre kişiye göre deterministik; dosya hash'leri manifestoda. |
| Güvenlik ve yönetişim | 15 | Serbest URL veya yükleme yok; CSRF ve denetim kaydı var; tarayıcı depolaması yok. |
| Dürüstlük | 10 | Kaynak belgesi üretim yolunu, 800 px yakalamayı ve üretilemeyen insan portrelerini açıkça yazıyor. |
| Tasarım ve erişilebilirlik | 15 | 96 px seçenekler, radyo grubu rolü, görünür alan adları; denetim 100, linter temiz. |
| Yerelleştirme | 5 | Alan adları Türkçe ve İngilizce. |
| Performans | 10 | Her portre ~18 KB JPEG (256 px). |
| Belgeleme | 8 | −2: Gemini'nin özgün dosyası değil, 800 px tarayıcı yakalaması saklandı (gömülü tarayıcıdan indirme diske ulaşmadı). |
| Doğrulanmamış yollar | −5 | −10: İstenen insan analist portreleri bu oturumda üretilemedi (otomatik izin denetimi engelledi); yedi sektör + maskot hazır. |
