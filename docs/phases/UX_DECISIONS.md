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

## 17 Ekim — AW-15: özgün glyph ailesi ve ölçülen tasarım sistemi

Bu bölüm, yukarıdaki "tutarlı Lucide fonksiyon ikonları" kararının yerini alır. Kullanıcı isteği üzerine hiçbir
simge hazır asset değil: lucide-react ve 36 eski SVG kaldırıldı; Gemini'de yedi turda üretilen 52 glyph tek
gramerle (açık sağ üst köşe + pirinç indeks noktası) kullanılıyor; tarayıcının yerel işaretleri de aynı aileden.
Kapsam (veri seti + filtre) tek kartta, dışa aktarma tek menüde, tip/boşluk/yarıçap ölçekleri araçla sabitlendi.
Puanlar, formüller ve sınırlar: `DESIGN_SCORECARD.md`; ham ölçüm `evidence/verification/phase12-design-audit.json`.
Bunlar DOM sezgileridir, kullanıcı testi değildir.


## 17 Ekim — AW-16: olgu ↔ hesap bağının gösterimi (dayanak ağacı)

Sorun: karar özetindeki ve Grafik stüdyosu yorumundaki ifadeler iki sütunlu bir listede (tür | metin) duruyordu.
Hangi hesabın hangi olguya, hangi önerinin hangi çıkarıma dayandığı yalnızca kanıt düğmelerinin metni
karşılaştırılarak anlaşılabiliyordu; aynı türden birden fazla ifade de numarasızdı.

Beş seçenek aynı ölçütlerle puanlandı (0–100, ağırlıklı toplam). Puanlar ekran taslakları ve çalışan prototip
üzerinde verilmiş tasarım yargısıdır; kullanıcı testi değildir.

| Seçenek | İzlenebilirlik (30) | Okunurluk (20) | Hick, ek kontrol yok (10) | 390px uyumu (15) | Erişilebilirlik (15) | Belirlenimcilik ve risk (10) | Toplam |
|---|---:|---:|---:|---:|---:|---:|---:|
| A. Klasik tablo (tür, metin, kanıt) | 30 | 70 | 100 | 50 | 80 | 100 | 62,5 |
| B. Numaralı düz liste, "dayanır: O1, H2" | 65 | 80 | 100 | 90 | 90 | 95 | 82,0 |
| C. Numaralı iç içe ağaç, sınırlar ilgili adımın altında | 90 | 85 | 95 | 85 | 90 | 90 | **88,8** |
| D. Düğüm-bağ grafiği (tuval) | 95 | 55 | 70 | 35 | 40 | 50 | 62,8 |
| E. Katman sütunları (olgu → hesap → çıkarım → öneri) | 85 | 65 | 90 | 40 | 70 | 70 | 71,0 |

Karar: **C**, B'nin "Ayrıca dayanır" satırıyla birlikte. Gerekçe:

- Bağ, modelin yargısı değil veriden türetilir: bir ifade, kendisinden bir alt katmanda olup aynı kanıt kimliğini
  paylaşan en yakın ifadelere dayanır (olgu/varsayım → hesap → çıkarım → öneri). Kanıt paylaşmayan ifade kök
  olarak kalır; bağ tahmin edilmez.
- Her ifade tür başına numaralanır (O1, O2, H1, Ç1, Ö1, S1; İngilizcede F, A, C, I, R, L). Birden fazla dayanağı olan
  ifade ilkinin altında durur, diğerleri "Ayrıca dayanır: O2" satırında adıyla yazılır.
- Sınırlar, nitelediği en derin adımın altında pirinç kenarlı bir blokta; hiçbir adımla kanıt paylaşmayanlar
  "Tüm sonuç için sınırlar" grubunda.
- Fareyle bir ifadenin üzerine gelindiğinde dayandığı ve ona dayanan zincir dışındaki her şey soluklaşır. Bu ek bir
  kontrol değildir (Hick yükü yok); klavye ve ekran okuyucu için yapı iç içe `ol` listeleri ve kimlik etiketleriyle
  zaten okunur.
- D (grafik) en yüksek izlenebilirliği verdi ama 390px'te okunmuyor, klavye ile gezilemiyor ve düzen her
  çalıştırmada aynı kalmıyor. E masaüstünde iyi, mobilde yatay kaydırma gerektiriyor.

Uygulama: `core/web/src/workbench/Reasoning.tsx` (`buildReasoning`, `ReasoningTree`), Karar stüdyosu ve Grafik
stüdyosu aynı bileşeni kullanır; kurallar `core/test/workbench-reasoning.test.ts` ile sabitlenir.
