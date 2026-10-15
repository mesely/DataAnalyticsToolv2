# Sonraki işler — beklenen katkıya göre

Bu liste Aşama 1/2/3 ve Aşama 4 yerel paketinden sonraki açık işleri sıralar. Aşama 4 provider/üretim dış kabulü açıktır. Tarihsel T01–T26 listesinin tamamının kapandığı anlamına gelmez. Katkı aralıkları uzman öncelik tahminidir; toplamsal garanti veya ölçülmüş puan değildir. Her iş kendi sözleşme/test/QA raporuyla kapanır.

| Öncelik | İş | Beklenen toplam puan katkısı | Somut uygulama ve kabul |
|---:|---|---:|---|
| 1 | Gerçek LLM ve kanıt-iddia değerlendirmesi | +3–6 | HF yapılandırması ve strict intent planı uygulandı; gerçek HTTP402 kredi kapısını çöz, başarılı canlı model doğrulamasını ve geniş structured plan schema işini tamamla; numeric claims sadece hesap artifact'ından; source-linked citations; en az50 golden soru + ret/ambiguity/OOD/PII/injection; gerçek provider usage/deadline/charge raporu. Anahtar arama veya model cevabı taklidi yok |
| 2 | Gerçek kullanıcıyla görevli kullanılabilirlik turu | +3–5 | İlk bulgu süresi, görevi tamamlama, hata/geri dönüş ve memnuniyet; yeni/uzman kullanıcı 5–8 kişi; ekran okuyucu/keyboard/zoom/contrast matrisi; bulguya göre UI düzeltmesi ve tekrar ölçüm |
| 3 | Üretim kimliği/tenant izolasyonu/retention | +3–5 | Gerçek IdP rol eşlemesi; tenant+subject predicates/RLS; query/import/run retention ve owner-visible lifecycle; secret referansları; export audit; yeni yetki gerektiren gerçek deployment ayrı |
| 4 | Genel dataset keşfi/hazırlama ve semantik metrik sözleşmesi | +2–5 | Retail dışı CSV/Parquet şema eşleme; grain/unit/denominator; nullable/type/uniqueness/profile; transform preview/undo/recipe; approved metric compiler ve fanout testleri |
| 5 | Sızıntısız ML stüdyosu | +2–5 | ML_REUSE_RESEARCH.md gerçek kaynak sembolleri; hedef/split/holdout sözleşmesi; train-fold-only preprocess/SMOTE; class_weight/RF baseline + OOF stacking; model card ve gerçek bağımsız holdout |
| 6 | Ölçek, kuyruk, cache ve p95 kanıtı | +2–4 | 0.5M/5M/50M satır için kaynak bütçesi; owner/visibility/dataset/metric sürümlü cache; tüm worker yolları admission ve PG advisory permits uygulandı; HTTP yük/cancel ve dead-client stres testleri; subprocess memory/CPU hard limit; 3+ eşzamanlı kullanıcı p95 ve hata/geri basınç |
| 7 | Zaman/ağ sağlamlık paketi | +1–3 | Müşteri/time cluster bootstrap, pencere/eşik hassasiyeti, aynı graph universe, geçmişe dönük kararlılık, baseline network karşılaştırması; yeni istatistiksel iddialar ayrıca testli |
| 8 | BI export ve rapor tasarımcısı | +1–3 | Alper'in governed Power BI deliver/attest zincirini yeni analytic artifact'a bağla; bağlantı/rol/token kontrolleri; gerçek BI publish ayrı yetki gerektirir |
| 9 | Konuşma referansı ve tutarlı özetleme | +1–2 | adviSU conversation_memory/response_formatter saf fonksiyonları; Mongo yerine mevcut owner Postgres; dataset/run/metric referansı; sınırlı history/retention/PII; çok anlamlı “bunu” açıklığa kavuştur |
| 10 | Gelişmiş arama/rerank ve kaynak yaşam döngüsü | +1–2 | adviSU source indexer/file_lifecycle/retrieval_policy; authorized corpus, visibility invalidation; vector retrieval yalnız kanıtlanmış ihtiyaçta; hash tek başına embedding altyapısı değildir |
| 11 | Analytics intent için LSTM | +0–2 | SNIPS sınıfları yeniden eğitim; train-only vocab ve padding-invariance; basit TF-IDF baseline'dan ölçülmüş fayda yoksa ürüne ekleme |
| 12 | Özel görsel varlıklar ve ileri polish | +0–1 | Mevcut işlevsel ikon dilini koru; gerekirse marka illüstrasyonu üret. Ulaşılabilirlik ve veri anlamını dekorla zayıflatma |

## İlk devam komutu

“progress.md'yi oku ve Aşama 4'e başla” denirse önce PHASE_3_REPORT.md'nin kapılarını kontrol et. Aşama 4'ü yerel üretim hazırlığı ve gerçek deployment olarak ayır; provider/live source bilgisi eksikse bağımsız yerel hardening/test işlerini tamamla ve kalan yapılandırmayı açık kaydet. Production veya ücretli servis sonucunu varmış gibi işaretleme.

## Teslimlerden sonra aşama haritası

- **Aşama 4 açık dış kapılar:** HF çıkarım kredisi ve başarılı canlı Llama eval; gerçek IdP/tenant/RLS/retention; geniş Docker regresyonu, 5M/50M yük ve görevli kullanıcı pilotu. Yerel arşiv/fingerprint/admission/asset/README işi tamamlanınca bunlar otomatik kapanmaz.
- **Önerilen Aşama 5:** genel CSV/Parquet hazırlama, grain/unit/metric mapping ve sızıntısız ML stüdyosu; Influencer kodunun gerçek modüler adaptasyonu ve bağımsız holdout. Henüz başlanmadı.
- **Önerilen Aşama 6:** BI entegrasyonu, çok kullanıcılı pilot, üretim ölçümü ve sürüm operasyonları. Henüz başlanmadı. SNIPS/LSTM ölçülmüş baseline kazancına bağlı isteğe bağlı alt iş.
