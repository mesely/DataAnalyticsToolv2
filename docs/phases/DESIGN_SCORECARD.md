# AW-15 — Özgün glyph ailesi ve tasarım karnesi (17 Ekim 2026)

İstek: uygulamadaki her simge (aktif veri seti, görünümü daralt, çalışma alanı, tema, dil, yükle, veri hakkında,
KPI simgeleri…) hazır asset olmayacak, Gemini ile üretilip ürünün tasarım diline özgü olacak; denge, boşluk ve
Fitts / Hick–Hyman gibi kurallar 100 üzerinden puanlanıp en yükseğe çıkarılacak.

Ölçümler `tools/design/audit.js` ile render edilmiş DOM üzerinde alınır (geçişler dondurulur). Bunlar
**sezgisel DOM ölçümleridir**: kullanıcı testi, görev süresi ölçümü ya da WCAG sertifikası değildir.
Ham kayıt: `docs/evidence/verification/phase12-design-audit.json`; son görsel geçiş:
`docs/evidence/verification/phase12-design-final-pass.json`.

## Radikal kararlar

1. **Tek glyph dili.** lucide-react kaldırıldı (paket ve 6 bileşen), 36 eski SVG silindi. Yerlerine Gemini ile
   yedi turda üretilmiş 52 glyph geldi (`assets/glyphs/gemini-batch-1..7.json`, değiştirilmeden saklandı,
   SHA-256'ları `PROVENANCE.md` ve `ASSET_MANIFEST.json` içinde). Dil, uygulama simgesinden türetildi:
   24×24 ızgara, 1.75 çizgi, kapalı konturlarda açık sağ üst köşe, anlamın düştüğü noktada tek pirinç "indeks
   noktası", en fazla 6 parça. Her ad tek anlam taşır (ör. `narrow_view` yalnız "Görünümü daralt").
2. **Tarayıcının hazır işaretleri de kaldırıldı.** `<summary>` üçgeni, `<select>` oku, tarih seçici takvimi,
   onay kutusu tiki ve sayı oku artık aynı aileden geliyor (`glyphs.generated.css`, data-URI maskeler).
3. **Kapsam tek kartta (Gestalt ortak bölge).** Aktif veri seti çubuğu ile "Görünümü daralt" filtreleri tek
   `wb-scope` kartında birleşti; ayrı iki kutu, tek karar bölgesine dönüştü.
4. **Sessiz yüzeyler.** Kenarlıklar yerine tek gölge ve 14px yarıçap; kart içi boşluk `--inset` (24px, mobilde
   16px). Yarıçaplar 10 farklı değerden 3 değere (6/10/14) indi.
5. **Tip ölçeği.** 12 farklı boyut (8–9px dahil) → 12/14/16/20/24/32; 9 kalınlık → 400/500/600/700.
   `tools/design/normalize_css.py` bunu sabitler; testler rem/em/vw/clamp boyutlarını reddeder.
6. **Hedef boyutu.** Her kontrol ≥44×44 (`--control`); onay kutuları etiketleriyle 44px; grafik düğümlerine
   36px yarıçaplı görünmez vuruş alanı.
7. **Komut sayısı (Hick–Hyman).** CSV/JSON tek "Dışa aktar" menüsünde; analiz ekranındaki yinelenen "Kaydet"
   kaldırıldı; ana bölge komutları 22 → 16.
8. **Açık tema kontrastı.** 62 metin tonu aynı renk tonunda koyulaştırıldı, beyaz ve sayfa zemininde ≥4.6:1
   (`tools/design/contrast_tones.py`, üretilmiş blok).
9. **Mobil denge.** 390px'te birincil KPI tam genişlik "hero", ardından bir çift, sonra tam genişlik son metrik
   (öksüz yarım kart yok); panel başlıkları tam genişlik, görünüm sekmeleri altında.

## Ölçülen puanlar (100 üzerinden)

Önce: koyu tema, 1440px, Genel bakış (ilk denetim). Sonra: 4 ekran (Genel bakış, Analiz asistanı, İlişki ağı,
Bulgularım) × 2 tema × 2 genişlik (1440×900, 390×844), toplam 16 ölçüm.

| Ölçüt | Formül (özet) | Önce | Sonra (en düşük–en yüksek) |
|---|---|---:|---:|
| Fitts (hedef boyutu) | %60·≥44px + %40·≥24px | 78 | 100–100 |
| Metin kontrastı (WCAG 1.4.3) | eşiği geçen metin oranı | 98 koyu / 72–74 açık | 100–100 |
| Simge kontrastı (WCAG 1.4.11) | ≥3:1 simge oranı | 100 | 100–100 |
| Boşluk ritmi | 4px ızgarasındaki boşluk oranı | 29 | 100–100 |
| Tip ölçeği | 100 − 8·max(0, boyut − 6) | 52 | 100–100 |
| Hizalama | 100 − 15·(kart içerik hattı − 1) | 34 | 100–100 |
| Hick–Hyman (ana bölge) | 100 − 12·max(0, log2(n+1) − 4) | 94 | 98–100 |
| Simge özgünlüğü | hazır paket dışı simge oranı | (bkz. not) | 100–100 |

Hick–Hyman 100 değil: Genel bakış ve İlişki ağında 16 komut (4.09 bit, puan 99), masaüstü Analiz asistanında
17 komut (4.17 bit, puan 98). Fark üç örnek soru düğmesinden geliyor. Bu düğmeler hatırlama yükünü azalttığı
için bilinçli olarak tutuldu. Not: ilk denetim sürümü `aria-hidden` simgeleri saymadığı için özgünlük puanı
başlangıçta yanlış olarak 100 göründü. Envantere göre başlangıçta 6 lucide bileşeni, 21 yardımcı SVG ve tarayıcı
yerel işaretleri vardı; şimdi sıfır hazır paket ve sıfır yerel işaret var. CSS ile çizilen widget glyph'leri
(`::before`) denetimin simge sayımına girmez; onları `tests/test_design_system.py` doğrular.

Ek: 390px'te 8 ölçümün hepsinde sayfa genişliği 390px (yatay kaydırma yok); 44px altında hedef sayısı 0;
WCAG eşiğinin altında metin sayısı 0.

## Son görsel geçiş (uçtan uca)

4 ekran + 11 diyalog/uzman yüzeyi; 1440, 1024, 768 ve 390 px; iki tema. Her yüzeyde ekran görüntüsü incelendi ve
`tools/design/layout_lint.js` çalıştırıldı. Bu araç şunları denetliyor:
- kart dışına taşma ve kırpılma,
- simge ile metin arasındaki dikey hiza,
- bozuk, bozulmuş oranlı veya büyütülmüş görseller,
- aynı kart içinde 2–8 px'lik "yakın kaçan" sol kenarlar,
- değerini sığdıramayan kontroller,
- yatay sayfa kaydırması.

Geçiş 24 kusur buldu, hepsi düzeltildi (liste kayıtta). Önemli olanlar:

- **Önceki karnenin düzeltilmesi:** koyu temada "Ürün ilişkileri" kartı ve birincil KPI sabit `#fff` degrade
  kullanıyordu; açık zeminde açık renkli metin, 1,2–2,0:1 kontrast. İlk denetim degradeleri görmediği için metin
  kontrastı 100 çıktı; o puan bu iki kart için yanlıştı. Denetim artık her degrade durağına karşı ölçüyor.
- **Tasarım geçişinin kendi gerilemeleri:**
  - kart iç boşluğu diyalog başlıklarına sızıyordu;
  - 390 px'te ülke seçicisi 54 px'e çöküyordu.
  Linter'a `narrow_control` ve `near_miss` denetimleri eklendi; ikisi de bu hataları yeniden üretince yakalıyor.
- **Yeni karar:** düzen pencereye göre değil, içerik sütununun genişliğine göre değişiyor (`main` bir CSS
  container). KPI ızgarası, genel bakış çifti, uzman araçları ve ülke sıralaması kenar çubuğu açıkken de doğru
  kırılıyor.
- **İlişki ağı:** etiketler artık çakışmıyor; önce en çok bağlantılı düğümler etiketleniyor, sığmayanlar üzerine
  gelince veya odaklanınca görünüyor. Telefonda grafik ortadan açılıyor, kontroller sabit duruyor.
- **Yeni simge:** "İki analizi karşılaştırın" sorgu simgesini ödünç alıyordu; Gemini'de 7. turda `compare`
  glyph'i üretildi. Simge boyutları yalnız 16/20/24/32 (test zorunlu kılıyor).
- **Paketleme:** yerel derleme silinen eski ikonları sunmaya devam ediyordu (41 eski asset). Derleme artık
  `assets/` klasörünü sıfırdan kuruyor.

Son ölçüm (degradeye duyarlı denetim, 16 ekran/tema/genişlik): Fitts, metin kontrastı, simge kontrastı, boşluk,
tip, hizalama ve simge özgünlüğü her yerde 100. Hick–Hyman 98–100. Linter 50 yüzey/genişlik ölçümünde 0 bulgu
verdi.

## Uzman değerlendirmesi (ölçüm değil, gerekçeli yargı)

| İlke | Puan | Gerekçe / kalan açık |
|---|---:|---|
| Denge | 95 | Masaüstünde 4 eşit KPI ve 2:1 trend/ülke ızgarası; mobilde hero + çift + tam genişlik. Analiz ekranında sohbet ile bağlam paneli arasındaki görsel ağırlık hâlâ sohbete kayıyor. |
| Beyaz alan | 95 | 24/16px iç boşluk, %100 4px ritmi. İlişki ağı kontrolleri yoğun bir şerit olarak kalıyor. |
| Görsel hiyerarşi | 96 | Sayfa başlığı 32, KPI 24, gövde 14, ikincil 12; tek kobalt birincil eylem. |
| Tutarlılık | 98 | Tek glyph grameri, 3 yarıçap, 4 kalınlık, tek kontrol yüksekliği. |
| Gestalt (yakınlık / ortak bölge) | 95 | Veri seti ve filtreler tek kartta; KPI simgesi etiketle aynı satırda. |
| Kademeli açılım | 95 | Dışa aktarma menüde; uzman araçları, SQL ve kanıt ikinci katmanda. |
| Jakob yasası | 93 | Sol gezinme, ⌘K komut paleti ve standart diyaloglar; özgün glyph'ler alışılmış metaforları (büyüteç, takvim, ok) koruyor. |

## Yeniden üretme

```bash
.venv/bin/python -m tools.design.glyphs            # Gemini çıktılarından TS + CSS üretir (doğrular)
.venv/bin/python -m tools.design.normalize_css --check
.venv/bin/python -m tools.design.contrast_tones
.venv/bin/python -m pytest tests/test_design_system.py -q
```

Tarayıcıda: `tools/design/audit.js` (puanlar) ve `tools/design/layout_lint.js` (taşma/hiza) içeriğini sayfada çalıştırın (devtools veya otomasyon). Sonuç, formülleriyle
birlikte alt puanları döndürür.

## Sınırlar

Puanlar DOM sezgileridir. Gerçek kullanıcıyla görev süresi/hata çalışması, ekran okuyucu matrisi ve tam WCAG
denetimi yapılmadı. Glyph'ler kullanıcının yönlendirmesiyle Gemini'de üretildi; marka/tescil taraması değildir.
