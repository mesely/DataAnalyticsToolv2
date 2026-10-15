# Aşama 3 — zaman içindeki satış ve ağ değişimi

## Şimdi oku

Kök progress.md, PHASE_2_REPORT.md, bu sözleşme, analysis/worker.py ve mevcut NetworkView. Kullanıcı tamamlanan aşamalardan sonra devamı istedi. Aşama 3'ün seçilen ürüne katkısı, gerçek zaman verisinden satış/ilişki değişimini güvenilir biçimde göstermektir. Veri/holdout görevi tanımlanmadan bir LSTM veya RF eğitip yararlı ürün özelliği diye sunulmaz; ML alt işi ayrı backlog olarak kalır.

## Kapsam (uygulamadan önce sabit)

- İlişki ağı bölümünde keşfedilebilir “Zaman içindeki değişim” paneli. Odak ayı ve önce/sonra pencere uzunluğu (1–3 ay), mevcut ülke/tarih kapsamı. Dönemler “önce / odak ay / sonra”; nedensel şok/etki iddiası yok.
- PoliEco build_economic_shock_study.py içindeki gerçek stage_months, owner_concentration_hhi, build_party_affinity, negative_edge_share gövdeleri ayrı saf modüle çıkarılacak. Siyasi IO/ideoloji/iki kutup etiketleri taşınmaz; retail adapter açık eşleme yapar. Source hash/commit/symbol ledger güncellenir.
- Her dönem için sales/orders/AOV, ürün satış HHI, ülke profili benzerliğinde negatif ağırlık payı; anlamsız/boş profilde null. HHI bütün ürünlerin satış paylarıyla hesaplanır. Benzerlik ilk24 ortak ürünle sınırlıdır.
- Aynı seçilmiş 24 ürün evreninde, aynı invoice co-purchase tanımı/eşik ile üç dönem ağı; kenar sayıları, önce/sonra Jaccard, yeni/kaybolan bağlantı sayısı. En fazla276 çift; ağ seçimi dönemlere göre yeniden sıralanmaz. Böylece seçilim artefaktını azaltır. Bu tüm ürün ağı değildir.
- İsteğe bağlı değil, açık betimleyici belirsizlik: invoice toplamlarından AOV için seed47,200 tekrarlı bootstrap yüzde95 aralık. En az20 sipariş; tekil invoice varsayımı ve zaman/cluster bağımlılığı sınırı görünür. Tahmin/causality/istatistiksel etki testi değildir. En fazla50.000 invoice veya veri yoksa aralık hesaplanmadığı açık döner; performans sınırı nedeniyle veri sessizce örneklenmez.
- Veri ay kapsaması, veri sınırındaki eksik ilk/son ay, filtre kesilmesi ve farklı dönem uzunluğu uyarıları. Satış olmayan ayın 0 olması, verinin o ayı kapsamadığı iddiasıyla karıştırılmaz; kapsam metadata ve filtre sınırlarıyla değerlendirilir.
- Aynı OIDC/CSRF/owner ve actor/global worker admission. Snapshot JSON / input-output digest indirilebilir. Başka dataset veya owner seçilemez. Kalıcı model eğitimi/LLM maliyeti yok.

## Teknik hedefler

analysis/adapted/temporal.py: dört kaynak fonksiyon + zscore_frame importu.
analysis/temporal.py: bounded data/graph/windows/bootstrap, JSON-safe null, kanıt.
analysis/worker.py: temporal action; core/src/workbench.ts: /temporal guarded route.
core/web/src/workbench/TemporalView.tsx: panel, dönem kartları/tablo, coverage/evidence.
analysis/tests/test_temporal.py + core/test/workbench.test.ts: bağımsız invoice/window/HHI/edge oracle, seed/null/coverage/input/ownership; browser gerçek demo+UCI, mobil, JSON export.

## Kabul / bitiş kapısı

Önce yukarıdaki fonksiyonları kaynaktan oku, sonra uygula. Matematik testleri bağımsız CSV/stdlib oracle ile doğrulansın; HHI'nin alt/üst sınırı, graph aynı universe/eşik, Jaccard boş durum, AOV aralığı seed ve sample limitleri testli olsun. Core/web build ve ilgili testler geçsin; browser paneli hesaplayıp gerçek değerleri göstersin. PHASE_3_REPORT.md, TEST_GUIDE, REUSE_LEDGER ve progress güncellensin. Bütün alt işler doğrulanmadan tamam denmesin.

## Sonraki ajan örnekleri

“Aşama 3 devam”: bu kabul listesindeki ilk gerçek eksik işi tamamla, bitmiş Aşama 1/2'yi yeniden yazma.
“ML ekle”: önce veri/target/grain/time/group split/holdout sözleşmesi; Influencer kaynağının notebook hücre30/33 fold öncesi SMOTE ve hücre63 scaler fit sorunlarını aynen taşıma. Training fold dışında fit yok; sonuçlar gerçek ölçülmeden başarı iddiası yok.
“LLM bağla”: açık provider/key/consent/config ve claim-evidence eval işi; mevcut deterministic açıklamayı model yanıtı diye yeniden etiketleme.
