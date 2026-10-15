# Aşama 1 — çalışan analist çalışma alanı

Yetki: 15 Ekim 2026 kullanıcı açıkça kodlama, yerelde ayağa kaldırma, güvenilir test verisi, UI/UX geçişi ve önce/sonra karşılaştırması istedi. Soru sormadan rutin kararlar alınacak. GitHub yayınlama/production deploy bu aşamanın parçası değil.

## Teslim sözleşmesi

Mevcut Context Layer sunucusu/OIDC/CSRF/Postgres kimliği korunur. Aynı uygulamaya Keşfet, Analiz, Ağlar, Bulgular akışı eklenir. Canlı müşteri sistemine bağlanılmaz. Seed'li açık etiketli sentetik fixture ve UCI Online Retail gerçek açık veri seti, kaynak/tarih/hash/dönüşüm kayıtlarıyla sunulur. Veri filtreleri sayıları gerçekten değiştirir; kanıt SQL/recipe/input hash/çıktı/run id içerir. CSV içe aktarımı retail şemasında sınırlandırılır. Gelişmiş seçenekler keşfedilebilir, klavye kısayolları görünürdür.

adviSU provider/guardrail/confidence ve seçilmiş UI kodu, PoliEco graph çekirdeği gerçekten adapte edilir; kaynak sembol/commit/test eşleştirmesi REUSE_LEDGER.md içinde. Sağlayıcı anahtarı olmadığında gerçek LLM çağrısı yapılmış gibi davranılmaz; aynı sonuçları doğrulanmış yerel açıklama sunar. Opsiyonel provider adapter'ı testlidir. Üretim multi-tenant RLS, genel sınırsız SQL/AutoML, model eğitimleri ve canlı BI publish Aşama 1 dışıdır; mevcut yetenekleri silme.

## Kabul kapıları

1. Kullanıcı yerel URL'den mevcut OIDC ile girer, iki veri setini seçer, kalite/şema/kaynak bilgisini görür.
2. Dönem/ülke filtresi, tanımlı metrikler, zaman/ülke/ürün kırılımı ve veri satırı önizlemesi çalışır. İade hariç brüt satış açıkça tanımlı; boş sonuç hata üretmez.
3. Soru -> sınırlı deterministik plan -> read-only parameterized calculation -> source-linked evidence; bilinmeyen/ambiguous soru açık sınırlama/clarification döndürür.
4. Ürün birlikte-alım ağı gerçek invoice ilişkilerinden hesaplanır; affinity analizi PoliEco'dan alınan kodu kullanır. Edge anlamı/co-purchase ile similarity ayrıdır; tablo alternatifi vardır.
5. Analiz kaydet/yeniden aç/yeniden çalıştır ve CSV/JSON export gerçek çalışır. Başka öznenin kaydı okunamaz; cookie write CSRF gerektirir.
6. Deterministik fixture beklenen sonuçları bağımsız oracle ile doğrulanır; import, veri sınırı, izolasyon, injection/ret, graph ve UI build testleri geçer.
7. Desktop/mobile ekranlar ve ana akış browser ile incelenir; boş/hata/focus/keyboard/diyalog davranışı kontrol edilir. Kullanıcı araştırması yapılmadan Hick/Fitts veya tam WCAG uyumu ölçülmüş sayılmaz.
8. TEST_GUIDE.md, PHASE_1_REPORT.md, REUSE_LEDGER.md ve progress.md gerçek durumla güncellenir; yerel servis test edilebilir kalır.

## UI/UX kuralları

Hick–Hyman: 4 ana görev; birincil eylem belirgin; gelişmiş kontroller açılır ama görünür etiket/komut aramasıyla erişilir. Fitts: ana butonlar >=44px, yakın eylemler gruplanır, her icon-only buton accessible label/title taşır. Recognition: örnek sorular/metric sözlüğü. Progressive disclosure: SQL/kanıt ayrı drawer. Tasarım dili: navy navigation, açık nötr çalışma yüzeyi, tek cobalt accent, tutarlı 4/8px spacing, tabular sayılar, kontrollü radius/border, yeterli contrast, responsive grid. Standart işlev ikonları tutarlı bir profesyonel aileden; AI görseli işlevin anlamını bulanıklaştırmak için kullanılmaz.

## Uygulama dosyaları

analysis/: worker, data import, deterministic metrics/graph, adapted source modules, fixtures/tests.
core/src/workbench.ts: authenticated routes + bounded subprocess + Postgres owner-scoped runs.
core/web/src/workbench/: React çalışma alanı + CSS + locale + kullanım göstergesi.
core/src/server.ts ve spa.ts: aynı session'a kayıt ve modül haritası.
deploy/phase1/: fixture launcher ve başlangıç komutu; gerçek credential içermez.

## Sonraki ajan için kısa komut

Önce progress.md güncel durumu, bu sözleşmeyi ve REUSE_LEDGER.md'yi oku. Mevcut modülleri ve testleri incele. Eksik kabul kapısından devam et; tamamlanan işi yeniden başlatma. Başarı/uyarı/sınırı ayır; mock'u gerçek diye etiketleme; anahtarsız LLM'i çalıştı diye gösterme.
