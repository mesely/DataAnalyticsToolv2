# UI/UX geçişinin karar ve test kaydı

Tasarım dili: navy navigation + açık nötr çalışma yüzeyi, tek cobalt action accent, ortak 4/8px spacing, kontrollü border/radius, tabular sayılar, tutarlı Lucide fonksiyon ikonları. Ek görsel/dekor ana göreve değer katmadığı için Gemini'ye veri/görsel gönderilmedi; özel asset oluşturulmadı. SVG yalnız veri ağı/istatistiksel grafik çizimi, el yapımı icon değil.

Hick–Hyman yönü: dört ana görev, uzman kontrolleri görünür etiketli ikincil katmanda, global işlem araması. Menü sayısını azaltmak tek başına tepki süresi başarısı kanıtlamaz; gerçek kullanıcı süre/hata çalışması gelecekte yapılmalı.

Fitts yönü: birincil eylemler 44px hedef, ilgili eylemler yakında; mobil menü, icon-only butonlarda accessible label. MacKenzie araştırması: https://www.yorku.ca/mack/hci1992.html . WCAG 2.2 target minimum 24px/spacing istisnaları: https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum . Uygulanan 44px hedef bir tasarım tercihidir; bütün grafik düğümlerine veya WCAG sertifikasına genellenmez.

Progressive disclosure: overview'da ana sayılar, data/quality görünümü sekmelerle; SQL/hashes/recipe kanıt diyaloğunda; yönetim araçları ayrı açılır bölümde. NN/g: https://www.nngroup.com/articles/progressive-disclosure/ . Örnek sorular ve metrik sözlüğü hatırlama yükünü azaltır; uzman keşfi command palette ile desteklenir.

Kontrol listesi: gerçek desktop ve 390px mobile screenshot; klavye odak; native dialog trap/Esc; graph table alternatifi; export kapsam etiketi; source/public/synthetic farkı; loading/empty/refusal/cannot_verify durumları. Tam WCAG/ekran okuyucu uyumu veya 5 kullanıcı testi yapılmış değildir. Bu bir somut implementation + heuristic/interaction pass, laboratuvar kullanılabilirlik skoru değildir.

## Aşama 4 — ürün dili ve özgün görseller

Mevcut çalışan ekran screenshot'ı alınıp incelendi. Sorunlar: genel sloganlar görev adını geri plana atıyor, yerel/aşama etiketleri ürünün iç akışına sızıyor, kota benzeri yüzdelik gerçek ilerleme ölçmüyordu. Düzeltme: Satış özeti gibi doğrudan başlıklar; geliştirme kimliği ve yöntem ayrıntıları kendi bağlamında; yalnız gerçek request status. Navy/cobalt/neutral token'lar ve 8px ritim korunur, sayılar tabular numerals kullanır. Gemini'den iki özgün still-life görsel ve dört label'lı navigation SVG alındı. SVG aktif içerik/dış kaynak kontrolünden geçti; tablolar ve hesap grafiği illüstrasyonlardan ayrı. Synthetic provenance kaldırılmadı; Perakende örneği Veri hakkında bölümünde açık.

Son kabul 1280×900 ve 390×844, ekranlar evidence/phase4 altında. Ekran görüntüsü; kullanıcı görevi tamamlama zamanı, Hick/Fitts performans ölçümü veya tam WCAG sertifikası değildir. Gerçek görevli pilot ve ekran okuyucu/zoom matrisi açık.

## 16 Ekim — hazırlama / model / ilişki görsel ailesi

Gemini'de üç özgün JPEG daha üretildi; toplam5 raster +4 özel navigation SVG.
Kobalt cam + seramik + küçük pirinç vurgu, mevcut navy/cobalt kimliği genişletir.
Veri hazırlama/model girişinde116px, model giriş kartında72px, ilişki girişinde128px;
mobilde86/56/90px. Verinin kendisi yerine dekoratif metrik/başarı resmi kullanılmaz.
Profil geldikten sonra giriş illüstrasyonu kaybolur, eşleme alanına yer açılır.
Sonuç tablosunda gerçek sayılar baskındır; CTA'lar sabit ve okunur kalır. Her
illüstrasyonda alt="", width/height; kaynak/provenance teknik dosyada tutulur.
Tam WCAG veya görevli kullanıcı pilotu yapılmış olduğu anlamına gelmez.
