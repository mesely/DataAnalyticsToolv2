# Aşama 2 — teslim raporu

**Durum: yerel kabul tamam.** 15 Ekim 2026. Kod: `/Users/selmanyilmaz/Projects/context-layer`. Uygulama: http://127.0.0.1:8123/app/ ; `selman` / `analiz-demo`. Sözleşme PHASE_2.md, sınırlar specs/analyst-workspace-phase2.md içinde.

| Yetenek | Aşama 1 | Aşama 2 |
|---|---|---|
| Uzman sorgu | Sabit ve parametreli hesaplar | Alper sqlval + filtre kapsamlı, salt okunur DuckDB SQL laboratuvarı |
| Sorgu sınırları | Rol/CSRF/owner, worker limiti | Ek AST/fonksiyon izin listesi; dış erişim, müşteri kimliği, join ve recursive reddi; 128 MB / 1 thread / 5 saniye / 500 satır / 30 kolon |
| Bağlam keşfi | Statik metrik sözlüğü | Gerçek adviSU BM25, normalizasyon, açılabilir metrik/şema/kaynak sonuçları |
| Tablo çıktısı | İlk 30 satır CSV + JSON | Çalışmış SQL'in CSV/Excel çıktısı; güvenli hücre ve başlıklar, sayısal türler, sorgu kolon sırası, boş sonuç başlıkları |
| Tekrar üretim | Summary ve recipe v1 hash | v2 digest; seri, sıralama, önizleme, graph ve açıklama da kapsama alınır |
| Karşılaştırma | Kayıt açma ve yeniden çalıştırma | İki owner-scoped run için fark/yüzde; metrik/para birimi kapısı, kapsam farkı, sıfır başlangıçta tanımsız yüzde |
| Bulunabilirlik | Dört görev ve komut arama | Aynı dört görev; Analiz'de Uzman araçları, Bulgular'da karşılaştırma, komut aramasından erişim |

## Test ve görsel kabul

- Phase 1 + 2 Python: **47 geçti** (`/tmp/context-phase2-python.log`). Bağımsız oracle, filtreli view, 19 tehlikeli/yanlış SQL varyantı, veri dosyası bütünlüğü, satır sınırı, müşteri kolonunun gizliliği, gerçek CSV/XLSX tekrar okuma, formül/başlık/sıra/boş sonuç, BM25, digest ve fark kontrolleri.
- İlgili core regresyonu: **38 geçti / 4 dosya** (workbench 9, KB Health 13, auth 12, property 4), `/tmp/context-phase2-core.log`. Son export sıralama düzeltmesi sonrası workbench **9/9 yeniden geçti**, `/tmp/context-phase2-core-final.log`.
- Core/web build, web TypeScript ve diff kontrolü geçti. Minified JS yaklaşık 673 KB; kullanıcı yükü veya p95 benchmark'ı değildir.
- Tarayıcıda demo SQL üç ülkeyi doğru döndürdü. Bağlam araması metrik ve formülü açtı. Excel indirildi ve dosya tekrar okunarak sayılar ve hücre türleri doğrulandı.
- İlk Excel kontrolünde Postgres JSONB'nin kolon sırasını değiştirdiği görüldü. Explicit query columns ile düzeltildi; yeniden indirilen dosyada country / gross_sales_gbp / orders sırası doğru. Boş sonuç ve güvenli başlık çakışması testleri eklendi.
- Tüm veri ile France karşılaştırması −£14.373,90 brüt satış ve −120 sipariş döndürdü; farklı filtre kapsamı görünür. Bu aynı kapsamda satış düşüşü veya nedensellik iddiası değildir.
- SQL ve karşılaştırma 390 px mobil ekranda incelendi; belge genişliği 390 px. Görseller `analytics_tool_review/evidence/phase2/` altında; dosyalar ayrıca açılıp incelendi.
- Geniş Python 856 pass / 17 skip önceki Aşama 1 kanıtıdır. Docker'a bağlı üç core dosyasının sınırı PHASE_1_REPORT içinde sürer; bütün repo yeşil diye raporlanmaz.

## Açık sınırlar

Retail şeması ve tek dataset SQL. Join ve harici dosya/ağ erişimi kapalı; kullanıcı bu sınırları görür. Tablo/export en fazla 500 satır. Üretim retention, tenant RLS ve yük QA henüz yok. Provider kodu hazır, gerçek LLM bağlı değil. Hash/cache yardımcıları embedding kullanıldığı anlamına gelmez. Query result saklanır; ayrı SQL geçmiş ekranı henüz yok. İngilizce arayüz var, bazı veri metinleri ve metrik notları Türkçe; tam yerelleştirme denetimi yapılmadı.

Muhafazakâr uzman yeniden değerlendirmesi yaklaşık **76/100**; ölçülmüş pazar sıralaması değildir. Pilot kullanıcı, gerçek LLM eval, daha geniş istatistik/ML ve üretim kanıtları puanı sınırlar.
