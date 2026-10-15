# Aşama 1 teslimi — 15 Ekim 2026

**Durum: Aşama 1'in yerel ürün kabul kapıları tamamlandı.** Çalışan uygulama: http://127.0.0.1:8123/app/ . `selman` / `analiz-demo`. Başlatıcı: `deploy/phase1/start.sh`. Bağımsız `.venv`, Node24 ve yalnız 127.0.0.1'e bağlı PostgreSQL16:5549 + IdP:8188. Kod kökü `/Users/selmanyilmaz/Projects/context-layer`.

## Önce / sonra

| Alan | Önce: 0aaac741 | Aşama 1 sonrası | Kanıt / sınır |
|---|---|---|---|
| Ürün akışı | Metadata/governance yönetim ekranları, dış MCP istemcisi | Genel bakış → analiz → ürün ağı → kişisel bulgu | Aynı oturum; eski yönetim erişimi korunur |
| Veriyle deneme | Hazır analist veri çalışma alanı yok | Kaynak bilgili UCI + seed47 demo + sınırlı özel CSV | 541.909 ham / 530.104 dahil UCI satırı; retail şeması |
| Hesap doğruluğu | Güçlü snapshot/SQL kontrol altyapısı | Satır kuruşu, metrik tanımı, tarih/ülke filtreleri, bağımsız oracle | Demo £21.405,00 / 180 sipariş / 1.639 adet; kâr/net gelir değil |
| Açıklama | Dış model/MCP akışı | adviSU guardrail + confidence ile sınırlı yerel açıklama | Provider adapte/testli; gerçek LLM bağlı değil |
| İş grafiği | Veri lineage | Invoice birlikte alım + PoliEco satış profili benzerliği | 24 ürün/150 kenar sınırı, iki farklı anlam; nedensellik değil |
| Kayıt | Governance/audit kayıtları | Owner-scoped recipe/sonuç/kanıt kaydetme, açma, yeniden çalıştırma | İkinci kimlik erişimi 404; CSV önizleme ilk30 satır |
| UI/UX | Yönetim odaklı yapı | 4 görev, komut arama, örnek sorular, metrik/kanıt diyalogları, mobil düzen | Screenshot/klavye kontrolü; kullanıcı çalışması ve tam WCAG denetimi yapılmadı |
| Tekrar kullanım | Ayrı projeler | Gerçek provider/guardrail/confidence/language/BM25/graph/UI gövdeleri | REUSE_LEDGER.md; taşınan ama kullanılmayan semboller ayrı |

## Kabul kanıtları

- Yeni Python analitik testleri: **19 geçti** (`/tmp/context-phase1-final-analytics-tests.log`). Bağımsız Decimal oracle, filtre, boş/yanlış input, graph basket oracle, similarity seed/symmetry, guardrail, provider MockTransport, UCI ve privacy.
- Yeni core entegrasyonu: **6 geçti**, en son geniş core koşusunda da geçti. Gerçek OIDC/CSRF/role revocation, run/save, guessed owner dataset/run izolasyonu.
- Python geniş regresyonu: **856 geçti / 17 atlandı**, `/tmp/context-phase1-full-python.log`.
- Core/web build + web TypeScript + diff whitespace: geçti. Bundle minified ~660 KB; lisanslar inline korunur. Bu ölçüm yük/latency benchmark'ı değildir.
- Geniş core ilk koşu: **438 geçti / 19 atlandı / 8 başarısız**, iki suite setup başarısız; toplam465 test. Başarısızlıkların tamamını gizleyerek “tüm testler geçti” denmez.
- Düzeltme/doğrulama: UTC test DB ile dashboard-extract **7/7**, lisans path index yanlış alarmını düzelten build ile kbhealth **13/13**, D-106.2'nin değişmiş normatif coalesce davranışına güncellenen eski property testi **4/4** geçti. Queue production kodu değiştirilmedi. Loglar `/tmp/context-phase1-regression-recheck*.log`, `/tmp/context-phase1-property-recheck.log`.
- **Açık ortam sınırı:** sync-drill, sync-run ve mcp-execute içindeki snapshot-advance testi Docker ephemeral PostgreSQL gerektiriyor; Docker daemon yanıt vermediği için PR/snapshot/timeouts oluştu. Geniş suite bu ortamda bütünüyle yeşil değildir. Bu yolların uygulama kodu değiştirilmedi. Docker yeniden hazır olunca bu üç dosyayı çalıştır; ilgisiz kullanıcı konteynerlerini yeniden başlatma. Yerel analitik app Docker kullanmaz.

## Görsel ve etkileşim kanıtları

`/Users/selmanyilmaz/Desktop/guncel_cvler/analytics_tool_review/evidence/phase1/`:

- 01-before.png: gerçek eski Connections ekranı; yerel KB yapılandırılmamış boş bağlam. Bu ekran tek başına bütün eski ürünün özellik yokluğu kanıtı değildir.
- 02-after-overview.png: seed47 demo genel bakış; 03-analysis.png; 04-network.png.
- 05-uci-real-data.png: gerçek UCI sonucu; 06-evidence.png: SQL/hash/parametre.
- 07-mobile.png: 390px mobil kontrol; 08-saved-findings.png: gerçek kayıt.

Browser ile login, veri seçimi, kaynak/kanıt, Esc/focus, kayıt/açma ve CSV seçimi/ithali kontrol edildi. 390px'de documentWidth=390; isimsiz button=0. Grafik animasyonu kapatılarak resize/screenshot geçişi kararlı hale getirildi. Tabloların yatay kayması kendi konteynerinde. Grafik düğümleri klavye ve tablo alternatifi taşır; tam ekran okuyucu test matrisi değildir.

## Dürüst yeniden puanlama

Aynı eski ağırlıklar ve uzman ölçeği; **73/100 geçici** (başlangıç60,78). Üretim ve pazar kanıtı puanı sınırlar. UI akışı gözlendi; öğrenilebilirlik/süre ölçülmedi. Puan farkı deneysel etki büyüklüğü değildir.

| Kriter | Ağırlık | Önce | Aşama1 | Sonraki kapı |
|---|---:|---:|---:|---|
| Veri bağlantıları/hazırlama |12|76|80|Genel şema keşfi ve dönüşüm recipe |
| Semantik/lineage/tutarlılık |12|80|83|Metrik sözleşmesi/sorgu grain kontrolü |
| Analitik/istatistik/ML |12|45|60|Güvenli uzman SQL, istatistik ve leakage-safe ML |
| LLM/yanıt doğruluğu |10|58|64|Gerçek sağlayıcı + claim/evidence eval; henüz yok |
| İş ağı analizi |8|25|72|Temporal robustness ve ölçek |
| Analist/UI akışı |12|50|78|Gerçek görevli kullanıcı testi ve erişilebilirlik matrisi |
| Güvenlik/yönetişim |12|78|81|Prod IdP/tenant/RLS/retention/load |
| Test/tekrar üretim |10|78|84|Docker bağımlı kalan regresyon ve kalite golden seti |
| Performans/maliyet/işletim |6|45|54|Hedef yük p95/memory ve gerçek inference cost |
| Farklılaşma/pazar |6|50|56|Pilot kullanıcı/tekrar kullanım/rakip görev karşılaştırması |
| **Ağırlıklı toplam** |100|**60,78**|**73,00**|92 hedef; elde edilmiş sonuç değil |

## Devam

Aşama2 için PHASE_2.md sözleşmesini yaz/oku: read-only yerel SQL, gerçek BM25 context araması, güvenli tablo export, run karşılaştırma ve metrik tutarlılığı. LLM anahtarı ve model eğitimi ayrı doğrulama kapısı. Aşama1 açık kapsam sınırları sonraki aşama bitti diye sessizce tamamlanmış sayılmaz.
