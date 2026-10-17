# Context Layer v3 — yapılacaklar listesi

Kaynak: 17 Ekim 2026 müşteri gözüyle yapılan uçtan uca test (Selman). Bu liste analitik çalışma alanını
(`core/web/src/workbench/`, `analysis/`) kapsar; platform kilometre taşları (CP-7, M1/M2 demoları) ayrı izlenir.

Her madde bitti sayılmadan önce: birim/uç testleri yeşil, CI'deki 5 kontrol yeşil, TR ve EN metinleri var,
ekran görüntüsü güncel, kabul ölçütü sağlanmış. Yeni kararlar `DECISIONS.md` içine AW-18'den başlayarak yazılır.

## Geri bildirimin özeti

| # | Geri bildirim | Kod tarafındaki karşılığı |
|---|---|---|
| G1 | İlişki ağında çizgiler çok ve kalınlıkları aynı; okunmuyor. | Kenarlar ağırlıktan bağımsız `strokeWidth={1.2}` ile çiziliyor (`Workbench.tsx` `NetworkView`). |
| G2 | İlişki ağı hakkında modelle soru sorulabilsin; hazır ve açık uçlu sorular. | Ağ sayfasında soru alanı yok. |
| G3 | Genel bakışta veriyi tablo olarak görmek: düzenleme, filtre, sıralama, CSV/Excel indirme; tabloya soru sormak. | Genel bakışta yalnız kartlar ve grafikler var; tablo yok. |
| G4 | Ülkeye tıklayınca filtre uygulanıyor ama tüm ülkelere geri dönülemiyor. | `filters: { ...applied, country }` uygulanıyor, geri alma yolu yok. |
| G5 | "Niye dışlamış?" Dışlama doğruysa gerekçesi gösterilsin, yanlışsa düzeltilsin. | Kısmi dönem, iade/iptal, sıfır/negatif fiyat ve "hariç" ülke dışlamaları var. Hangi ekran kastedildiği netleşmeli (bkz. Açık sorular). |
| G6 | "Groq ile planla / modelle yorumla" tikleri kalksın; ölçümde hangisi iyiyse sistem onu kullansın. | Üç yerde elle seçilen kutu var: Grafik stüdyosu, asistan, karar stüdyosu. |
| G7 | Model, "ülkeleri NATO / NATO dışı diye sınıfla, satışın yüzde kaçı, grafik yap" sorusunu yapamadı. | ChartSpec v1'de türetilmiş grup boyutu yok; dış bilgi (üyelik listesi) yok; soru "unsupported" diye kapanıyor. |
| G8 | Asistan karışık: karar stüdyosu mu, grafik stüdyosu mu, uzman araçları mı, model stüdyosu mu? İki ana başlık olsun, analizler onların içinde. | Analiz asistanı sayfasında 4 ayrı giriş noktası var. |
| G9 | Gerekirse referans bilgiyle (RAG) beslensin: tutarları TL'ye çevir, enflasyona veya altına göre normalize et. | Yalnız GBP; kur, enflasyon ve altın serileri yok. |

## Ölçümle belirlenen başlangıç noktası (G6 için)

`docs/evidence/verification/phase12-llm-eval-groq.json`:

| İş | Model (GPT-OSS 20B, Groq) | Yerel yöntem | Bugünkü karar |
|---|---:|---:|---|
| Soruyu doğru analize yönlendirme | 19/19 | 15/19 | Model daha iyi |
| Grafik isteğini planlama | 19/24 | 24/24 | Yerel daha iyi (ancak yerel bu 24 vakaya göre yazıldı; bağımsız sonuç değil) |
| Karar anlatısı | 1/3 doğrulayıcıdan geçti | her zaman | Yerel |
| Yetersiz soruda çekimser kalma, saldırı reddi | 6/6, 2/2 | 6/6, 2/2 | Eşit; yerel ucuz olduğu için yerel |

---

## Faz 1 — Hızlı düzeltmeler (okunabilirlik ve gezinme)

### 1.1 İlişki ağı okunabilirliği (G1)
- [ ] Kenar kalınlığı ağırlığa göre ölçeklensin: 1–6 px, karekök ölçeği. Böylece birkaç çok güçlü bağ diğerlerini ezmez.
- [ ] Kenar rengi ve saydamlığı ağırlığı kodlasın: zayıf bağ soluk, güçlü bağ koyu vurgu rengi. Negatif ilişki kesik çizgi ve uyarı rengi olarak kalsın.
- [ ] Renk tek başına anlam taşımasın: kalınlık + saydamlık + kesik çizgi birlikte kullanılsın (renk körlüğü).
- [ ] Gösterge (lejant): "ince = zayıf, kalın = güçlü", ağırlık aralığının sayısal değerleri.
- [ ] Eşik kaydırıcısı: "en güçlü N bağ" veya "ağırlık ≥ x"; varsayılan olarak en güçlü 40 bağ gösterilsin, gerisi isteğe bağlı açılsın.
- [ ] Bir ürünün üzerine gelince yalnız onun bağları vurgulansın, diğerleri soluklaşsın (karar stüdyosundaki davranışla aynı).
- [ ] Kenar etiketi (araç ipucu): iki ürün, ağırlık, birlikte alındığı fatura sayısı.
- [ ] Topluluklar (community) düğüm rengiyle ayrılsın; kenar rengi ağırlığa ayrıldığı için düğüm rengiyle çakışmasın.
- [ ] Aynı kurallar "Zaman içindeki değişim" ağına da uygulansın (`TemporalView.tsx`).
- **Kabul:** varsayılan görünümde kenar sayısı ≤ 40; en güçlü 5 bağ ilk bakışta seçilebilir; tasarım denetimi (`tools/design/audit.js`) ve kontrast kontrolü açık/koyu temada geçer.

### 1.2 Ülke filtresinden geri dönme (G4)
- [ ] Ülkeye tıklanınca filtre çubuğunda kaldırılabilir bir çip görünsün: "Ülke: Germany ✕".
- [ ] "Tüm ülkeler" seçeneği ve "Filtreleri temizle" düğmesi.
- [ ] Filtre durumu adres çubuğunda tutulsun; tarayıcının geri düğmesi önceki görünüme dönsün.
- [ ] Aynı davranış grafik stüdyosundaki ülke tıklamalarında ve sıralama listelerinde de olsun.
- **Kabul:** ülkeye tıkla → çip görünür → ✕ veya geri düğmesi → kartlar £10.666.684,54'e döner. Uç testi eklenir.

### 1.3 Dışlamaların denetimi (G5)
- [ ] Ekranda gösterilen her dışlamanın listesi çıkarılsın: iade/iptal, sıfır ve negatif fiyat, kısmi ay/hafta, "hariç" ülke, gizli `customer_id`.
- [ ] Her dışlama için doğruluk kontrolü yapılsın: kural doğru mu, sayılar tutuyor mu (11.805 satır, 9.288 iptal…). Yanlış olan düzeltilsin ve testi yazılsın.
- [ ] Her dışlamanın yanında "neden?" açıklaması: kaç satır ve ne kadar tutar dışarıda kaldı, hangi kurala göre.
- [ ] Dışlaması geçerli bir seçim olan durumlarda (kısmi dönem, posta/hizmet satırları, hariç ülke) "dahil et" anahtarı olsun. Değişiklik planın değişiklik çiplerinde görünsün.
- [ ] Veri tanımı gereği zorunlu dışlamalar (iptal ve iade brüt satışa girmez) anahtar almasın, gerekçesi gösterilsin.
- **Kabul:** her dışlamanın bir açıklaması ve sayısı var; "dahil et" ile toplamlar beklenen değere değişir ve testle doğrulanır.

---

## Faz 2 — Sade bilgi mimarisi: iki ana stüdyo (G8)

Hedef: kullanıcı nereye gideceğini düşünmesin. İki ana başlık olsun; her analiz bunlardan birinin içinde bulunsun.

| Yeni yer | İçine taşınan |
|---|---|
| **Genel bakış** (ana sayfa) | Kartlar, grafikler, veri tablosu (Faz 4), tek soru kutusu |
| **Grafik stüdyosu** | Grafik isteği, ilişki ağı, zaman içindeki değişim, SQL laboratuvarı ("Gelişmiş" sekmesi), koda aktar |
| **Karar stüdyosu** | Analiz asistanının soruları, haftalık projeksiyon, senaryo, öneri ve gerekçe ağacı, model stüdyosu ("Tahmin modeli" sekmesi), veri hazırlama |
| **Bulgularım** | Değişmez |

- [ ] Tek soru kutusu: kullanıcı ne yazarsa yazsın sistem doğru stüdyoya yönlendirsin. Sonuç hangi stüdyoda açıldıysa ekranda yazsın: "Bu bir grafik isteği; Grafik stüdyosunda açıldı".
- [ ] Analiz asistanı ayrı bir sayfa olmaktan çıksın; soruları ve kanıt paneli Karar stüdyosuna girsin. "Neden bu stüdyo?" bilgisi soru kutusunun altında görünsün.
- [ ] "Uzman araçları" ve "Model stüdyosu" ana menüden kalksın; ilgili stüdyonun içinde "Gelişmiş" olarak dursun.
- [ ] Kenar çubuğunda en fazla 4 madde kalsın: Genel bakış, Grafik stüdyosu, Karar stüdyosu, Bulgularım (+ Yönetim yalnız `ops` rolüne).
- [ ] ⌘K komut paleti yeni yerleri göstersin; eski bağlantılar yeni yerlere yönlendirsin (yer imleri bozulmasın).
- [ ] Kullanım rehberi ve README yeni yapıya göre yeniden yazılsın.
- **Kabul:** ilk kez gelen biri 10 tipik görevin her birini en fazla 2 tıklamayla başlatır. Görev listesi `docs/phases/TEST_GUIDE.md` içinde yazılı olur; yeniden müşteri testi yapılır.

---

## Faz 3 — Elle model seçimini kaldırma: ölçüme dayalı otomatik yönlendirme (G6)

Hedef: "Groq ile planla / modelle yorumla" kutuları kalksın. Her iş için ölçümde hangi yöntem iyiyse sistem onu
kullansın, ekranda da hangisini kullandığını söylesin.

- [ ] Bağımsız (held-out) değerlendirme seti: yerel planlayıcının yazılırken görmediği en az 60 yeni grafik isteği ve 40 yeni soru (TR+EN, yazım hatalı, açık uçlu, NATO tipi). Yerel ve model aynı setle ölçülsün.
- [ ] İş bazında yönlendirme tablosu `analysis/llm_routing.json`: her iş için (yönlendirme, grafik planı, anlatı, ağ soruları, tablo soruları) seçilen yöntem, ölçüm dosyası, ölçüm tarihi ve eşik değerleri yazılsın. Tablo elle değil, değerlendirme komutuyla üretilsin.
- [ ] Karar kuralı: model, yereli iş bazında en az 5 puan geçmiyorsa yerel kullanılsın (yerel ücretsiz, hızlı ve çevrimdışı çalışır). Eşitlikte yerel kazanır.
- [ ] Karma yol: yerel planlayıcı "anlamadım / desteklenmiyor" derse ve model o iş için güvenilirse modele sorulsun (NATO sorusu buradan geçer). Model geçersiz yanıt verirse yerel sonuç gösterilsin.
- [ ] Tikler yerine bilgi rozeti: "Planlayan: yerel yöntem" / "Planlayan: dil modeli (GPT-OSS 20B · Groq)". Üstüne gelince neden o yöntemin seçildiği (ölçüm sonucu) görünsün.
- [ ] Gizlilik: sağlayıcıya ne gönderildiği rozetin yanında yazmaya devam etsin. Yönetici "dış modele hiç gönderme" ayarını açabilsin; bu ayar her şeyi yerele zorlar.
- [ ] Kota: Groq günlük ücretsiz kotası (200.000 token) otomatik kullanımda yetmez. Yanıt önbelleği (aynı istek + aynı veri sürümü), günlük bütçe sayacı ve kota dolunca sessizce yerele düşme eklenmeli. Ücretli plana geçiş kararı ayrıca verilir.
- [ ] Değerlendirme CI'de çevrimdışı (kayıtlı yanıtlarla) koşsun; canlı ölçüm haftalık elle tetiklensin ve yönlendirme tablosunu güncellesin.
- [ ] DECISIONS AW-18: otomatik yönlendirme politikası.
- **Kabul:** arayüzde model seçme kutusu kalmaz; her sonuçta planlayan rozeti vardır; yönlendirme tablosu son ölçümle tutarlıdır (test); kota bitince ekran donmaz ve yerel sonuç gelir.

---

## Faz 4 — Genel bakışta veri tablosu (G3)

- [ ] Geçerli kapsamın (ülke, tarih filtresi) tablosu: iki görünüm. **Satırlar** (fatura satırı) ve **özet** (ülke/ay/ürün bazında toplamlar).
- [ ] 530 bin satır için sunucu tarafında sayfalama (sayfa başına 50/100/500); toplam satır sayısı görünsün.
- [ ] Sütuna göre sıralama (artan/azalan, çoklu sıralama Shift ile).
- [ ] Sütun filtresi: metin içerir, sayı aralığı, tarih aralığı, değer listesi. Filtreler genel bakıştaki filtre çiplerine bağlı olsun.
- [ ] Sütun gizle/göster, sütun sırası, sütun genişliği; seçim kullanıcı başına hatırlansın.
- [ ] "Düzenleme" kaynak veriyi değiştirmesin. Görünüm düzeyinde: sütun adı değiştir, hesaplanmış sütun ekle (ör. `adet × fiyat`), satıra not ekle. Kaynak veride gerçek düzeltme gerekiyorsa denetim kayıtlı ayrı bir "düzeltme katmanı" olarak tasarlansın (bkz. Açık sorular).
- [ ] İndirme: CSV ve Excel (.xlsx), görünen filtre/sıralama ile. Formül enjeksiyonu nötrleştirmesi (`= + - @`) Excel için de uygulanır. Büyük indirmeler sınırlansın (ör. 1 milyon hücre) ve kullanıcıya söylensin.
- [ ] **Tabloya sor:** tablonun o anki hali (filtre, sıralama, görünen sütunlar) bağlam olarak gitsin. Soru doğrulanmış salt-okunur SQL'e çevrilsin (`analysis/sql_lab.py` doğrulayıcısı), sonuç tablo veya grafik olarak dönsün, SQL'i görülebilsin. Hazır sorular: "en çok iade edilen ürün", "bu ülkede aylık değişim", "seçili satırların toplamı".
- [ ] Tablodan grafiğe: seçili sütunlarla "Grafik stüdyosunda aç".
- [ ] Erişilebilirlik: klavyeyle gezinme, ekran okuyucu için tablo başlıkları; telefonda yatay kaydırma.
- **Kabul:** 530 bin satırda sıralama + filtre ≤ 1 sn (yerel makinede); CSV ve Excel dosyası ekrandaki satırlarla birebir aynı (test); "tabloya sor" 20 vakalık sette ölçülür.

---

## Faz 5 — Referans bilgi katmanı (RAG), türetilmiş gruplar ve dönüşümler (G7, G9)

Hedef: dış bilgi gerektiren sorular (NATO üyeliği, döviz kuru, enflasyon, altın) çözülsün. Kural değişmez:
model yalnız plan önerir; sayılar her zaman yerelde, kaynağı ve tarihi belli referans verisiyle hesaplanır.

### 5.1 Referans veri deposu
- [ ] `analysis/reference/` altında sürümlü referans tabloları: her tabloda kaynak URL, lisans, çekiliş tarihi, geçerlilik aralığı ve SHA-256.
- [ ] İlk tablolar:
  - [ ] Ülke grupları: NATO (katılış tarihleriyle), AB, Euro bölgesi, G7, OECD, kıtalar. Veri setindeki ad farklılıkları eşlensin: "EIRE", "RSA", "Channel Islands", "European Community", "Unspecified".
  - [ ] Döviz kurları: GBP/TRY, GBP/USD, GBP/EUR günlük (ör. TCMB / ECB).
  - [ ] Enflasyon: İngiltere TÜFE (ONS), Türkiye TÜFE (TÜİK), aylık.
  - [ ] Altın fiyatı: GBP/ons, günlük (lisansı uygun bir kaynak seçilmeli).
- [ ] Çevrimdışı çalışma: referans tabloları depoyla birlikte gelsin; güncelleme komutu ayrı ve elle çalıştırılsın.
- [ ] Bilgi erişimi (RAG): model, soruya göre hangi referans tablosunun gerektiğini bu depodaki tablo kartlarından seçsin; serbest metinden sayı uydurmasın. Gerekli tablo yoksa "bu bilgi yok, şu kaynak eklenebilir" desin.

### 5.2 ChartSpec v2: türetilmiş grup boyutu (NATO sorusu)
- [ ] Yeni alan `group_by`: referans grup tablosuna göre ülkeleri "grupta / grup dışı" sınıflasın. Hesap yerelde yapılsın.
- [ ] "Hangi tarihteki üyelik?" seçimi: verinin dönemi (2010–2011) ya da bugün. Varsayılan verinin dönemi; ekranda yazsın. Örneğin bugün NATO üyesi olan Finlandiya ve İsveç, 2011'de üye değildi.
- [ ] Sonuç: grup başına tutar ve yüzde, pasta veya yığılmış çubuk grafik, hangi ülkenin hangi grupta sayıldığını gösteren tablo, eşleşmeyen ülkeler ayrı satırda.
- [ ] NATO sorusu ve benzerleri (AB/AB dışı, Euro bölgesi, kıta) değerlendirme setine eklensin.
- **Kabul:** "ülkeleri NATO / NATO dışı diye sınıfla, yüzdesini grafik yap" sorusu TR ve EN olarak doğru grafiği üretir; yüzdeler bağımsız bir Decimal hesabıyla tutar; eşleşmeyen ülkeler listelenir.

### 5.3 ChartSpec v2: dönüşümler (TL, enflasyon, altın)
- [ ] Yeni alan `transform`, sırayla uygulanan adımlar:
  - [ ] `convert_currency`: işlem tarihindeki kurla (dönem ortalaması değil) TL/USD/EUR'ya çevir.
  - [ ] `deflate`: TÜFE'ye göre seçilen baz aya sabitle ("2011 Ocak fiyatlarıyla").
  - [ ] `in_gold`: tutarı altın onsu cinsinden göster.
  - [ ] `index_100`: ilk dönem = 100.
- [ ] Aynı grafik üzerinde "şimdi TL'ye çevir", "enflasyona göre düzelt", "altına göre göster" adım adım çalışsın; her adım değişiklik çipinde görünsün ve geri alınabilsin.
- [ ] Hangi kur, hangi TÜFE serisi ve hangi baz ayın kullanıldığı grafiğin altında yazsın; Veri sekmesinde ham ve dönüştürülmüş değerler yan yana olsun.
- [ ] Koda aktar paketi dönüşümleri ve referans tablolarını da içersin; `--check` yine eşleşsin.
- [ ] Sınır: kâr veya marj gibi verinin desteklemediği şeyler dönüşümle "üretilmesin"; çekimser kalma kuralları korunsun.
- **Kabul:** brüt satışın TL karşılığı, kurun gün bazında uygulanmasıyla bağımsız oracle'la birebir tutar; enflasyon ve altın dönüşümleri için ayrı testler var; koda aktar `--check` geçer.

### 5.4 Karar
- [ ] DECISIONS AW-19 (referans veri katmanı) ve AW-20 (ChartSpec v2: `group_by`, `transform`).

---

## Faz 6 — İlişki ağı için soru-cevap (G2)

- [ ] Ağ sayfasında (Grafik stüdyosu içinde) soru kutusu.
- [ ] Hazır sorular:
  - [ ] "En güçlü 5 ürün çifti hangisi?"
  - [ ] "Şu ürünle en çok birlikte alınanlar?"
  - [ ] "Kaç topluluk var, her birinin öne çıkan ürünü ne?"
  - [ ] "Hangi ürün köprü görevi görüyor?" (aradalık merkeziliği)
  - [ ] "Seçili ay ile önceki ay arasında hangi bağlar koptu veya oluştu?"
- [ ] Açık uçlu sorular Faz 3'teki otomatik yönlendirmeyle cevaplansın. Model yalnız ağ sorgu planını önerir (hangi düğüm, hangi ölçüt, kaç sonuç); hesap yerelde ağ verisi üzerinden yapılır.
- [ ] Cevap ağı da güncellesin: ilgili düğüm ve kenarlar vurgulansın, geri kalan soluklaşsın.
- [ ] Ağın desteklemediği sorular (ör. "bu ürünü alan müşteri neden aldı?") çekimserlikle yanıtlansın.
- [ ] 25 vakalık ağ soruları değerlendirme seti; yerel ve model ölçülsün, yönlendirme tablosuna girsin.
- **Kabul:** 5 hazır soru da doğru ve vurgulu cevap verir; açık uçlu sette ölçülmüş doğruluk rapora yazılır.

---

## Faz 7 — Doğrulama ve teslim

- [ ] Tüm testler, CI'deki 5 kontrol, tasarım denetimi (160 ölçüm) yeşil.
- [ ] Canlı Groq ölçümü yeni setlerle yeniden koşsun; makbuz `docs/evidence/verification/` altına.
- [ ] README, kullanım rehberi, ekran görüntüleri ve GIF yeni yapıya göre yenilensin; manifest hash'leri güncellensin.
- [ ] Müşteri testi tekrarı: aynı kişi aynı senaryoyu yeni yapıyla yapsın; G1–G9'un her biri "çözüldü / kısmen / çözülmedi" olarak işaretlensin.
- [ ] Groq anahtarı yenilensin (sohbet geçmişinde göründü).
- [ ] v3 etiketi ve sürüm notu.

---

## Açık sorular (Selman'a)

1. **G5:** "Niye dışlamış?" derken hangi ekran ve hangi dışlama kastedildi? Grafikteki kısmi dönem mi, iade/iptaller mi, yoksa önerilen "İngiltere hariç" isteği mi? Bir ekran görüntüsü yeterli.
2. **G3 düzenleme:** tablodaki düzenleme görünüm düzeyinde mi kalsın (sütun adı, hesaplanmış sütun, not), yoksa kaynak veride gerçek düzeltme mi isteniyor? İkincisi denetim ve geri alma gerektirir.
3. **G9 kaynakları:** TL kuru için TCMB mi, ECB mi? Altın için hangi kaynak kabul edilir? Lisans uygun olmalı.
4. **G7 tarih:** grup üyeliği varsayılan olarak verinin dönemine göre mi (2011), bugüne göre mi hesaplansın?
5. **G6 maliyet:** otomatik kullanım ücretsiz Groq kotasını aşar. Ücretli plana geçilecek mi, yoksa günlük bütçe sınırıyla mı çalışılsın?
6. **G8:** ilişki ağı Grafik stüdyosu içinde mi dursun, yoksa Genel bakıştan doğrudan erişilen ayrı bir görünüm mü olsun?

## Önerilen sıra ve kabaca büyüklük

| Faz | Büyüklük | Neden bu sırada |
|---|---|---|
| 1 Hızlı düzeltmeler | Küçük | Müşterinin hemen gördüğü sorunlar |
| 2 İki stüdyo | Orta–büyük | Yeni özellikler son yerlerine eklensin, sonradan taşınmasın |
| 3 Otomatik yönlendirme | Orta | Faz 4–6'daki soru kutularının hepsi bunu kullanır |
| 4 Veri tablosu | Orta | Faz 3'ün yönlendirmesini "tabloya sor" için kullanır |
| 5 Referans veri ve dönüşümler | Büyük | Yeni veri kaynakları, lisans ve oracle testleri gerektirir |
| 6 Ağ soruları | Orta | Faz 3 ve 1.1 üzerine kurulur |
| 7 Teslim | Küçük | — |
