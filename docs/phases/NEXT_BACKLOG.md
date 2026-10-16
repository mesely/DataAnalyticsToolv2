# Sonraki işler — beklenen katkıya göre

16 Ekim devam güncellemesi: Aşama11 doğruluk ve gerçek tarayıcı kabulü tamamlandı (PHASE_11_CONTINUATION.md); Aşama5 CSV hazırlama ve Aşama6 ML deneyi uygulandı; bunların dar sözleşmeleri ve kalmış geniş kapsam aşağıda ayrıdır. Bu liste hâlâ açık işleri sıralar. Aşama 4 provider/üretim dış kabulü açıktır. Tarihsel T01–T26 listesinin tamamının kapandığı anlamına gelmez. Katkı aralıkları uzman öncelik tahminidir; toplamsal garanti veya ölçülmüş puan değildir. Her iş kendi sözleşme/test/QA raporuyla kapanır.

| Öncelik | İş | Beklenen toplam puan katkısı | Somut uygulama ve kabul |
|---:|---|---:|---|
| 1 | Gerçek LLM ve kanıt-iddia değerlendirmesi | +3–6 | HF yapılandırması ve strict intent planı uygulandı; gerçek HTTP402 kredi kapısını çöz, başarılı canlı model doğrulamasını ve geniş structured plan schema işini tamamla; numeric claims sadece hesap artifact'ından; source-linked citations; en az50 golden soru + ret/ambiguity/OOD/PII/injection; gerçek provider usage/deadline/charge raporu. Anahtar arama veya model cevabı taklidi yok |
| 2 | Gerçek kullanıcıyla görevli kullanılabilirlik turu | +3–5 | İlk bulgu süresi, görevi tamamlama, hata/geri dönüş ve memnuniyet; yeni/uzman kullanıcı 5–8 kişi; ekran okuyucu/keyboard/zoom/contrast matrisi; bulguya göre UI düzeltmesi ve tekrar ölçüm |
| 3 | Üretim kimliği/tenant izolasyonu/retention | +3–5 | Gerçek IdP rol eşlemesi; tenant+subject predicates/RLS; query/import/run retention ve owner-visible lifecycle; secret referansları; export audit; yeni yetki gerektiren gerçek deployment ayrı |
| 4 | Genel dataset/semantik genişletme (CSV profili ve retail mapping tamam) | +2–5 | Parquet primitive sütun alımı tamam; kalan retail dışı semantik eşleme; grain/unit/denominator; nullable/type/uniqueness/profile; transform preview/undo/recipe; approved metric compiler ve fanout testleri |
| 5 | ML ileri değerlendirme (ilk stüdyo tamam) | +2–5 | İlk sürüm train-only preprocessing + RF/linear/baseline + group/time/random + optional SMOTE + owner kart çalışıyor; kalan OOF stacking ve calibration, PR-AUC/error slices, uygun real target ve as-of join; train-fold-only preprocess/SMOTE; class_weight/RF baseline + OOF stacking; model card ve gerçek bağımsız holdout |
| 6 | Ölçek, kuyruk, cache ve p95 kanıtı | +2–4 | 0.5M/5M/50M satır için kaynak bütçesi; owner/visibility/dataset/metric sürümlü cache; tüm worker yolları admission ve PG advisory permits uygulandı; HTTP yük/cancel ve dead-client stres testleri; subprocess memory/CPU hard limit; 3+ eşzamanlı kullanıcı p95 ve hata/geri basınç |
| 7 | Zaman/ağ sağlamlık paketi | +1–3 | Müşteri/time cluster bootstrap, pencere/eşik hassasiyeti, aynı graph universe, geçmişe dönük kararlılık, baseline network karşılaştırması; yeni istatistiksel iddialar ayrıca testli |
| 8 | BI export ve rapor tasarımcısı | +1–3 | Alper'in governed Power BI deliver/attest zincirini yeni analytic artifact'a bağla; bağlantı/rol/token kontrolleri; gerçek BI publish ayrı yetki gerektirir |
| 9 | Konuşma referansı ve tutarlı özetleme | +1–2 | adviSU conversation_memory/response_formatter saf fonksiyonları; Mongo yerine mevcut owner Postgres; dataset/run/metric referansı; sınırlı history/retention/PII; çok anlamlı “bunu” açıklığa kavuştur |
| 10 | Gelişmiş arama/rerank ve kaynak yaşam döngüsü | +1–2 | adviSU source indexer/file_lifecycle/retrieval_policy; authorized corpus, visibility invalidation; vector retrieval yalnız kanıtlanmış ihtiyaçta; hash tek başına embedding altyapısı değildir |
| 11 | Analytics intent için LSTM | +0–2 | SNIPS sınıfları yeniden eğitim; train-only vocab ve padding-invariance; basit TF-IDF baseline'dan ölçülmüş fayda yoksa ürüne ekleme |
| 12 | Özel görsel varlıklar ve ileri polish | +0–1 | Mevcut işlevsel ikon dilini koru; gerekirse marka illüstrasyonu üret. Ulaşılabilirlik ve veri anlamını dekorla zayıflatma |

## Güncel aşama haritası ve açık kapsam

A1–6 uygulanmış ürün korunuyor.16Ekimde A7–10'a forecast/decision/XML/report/appearance **ek paketleri** eklendi (AW-10–13); ayrıntı PHASE_7..10_REPORT. Bu ek paketler aşağıdaki orijinal işlerin kapandığını göstermez. Kullanıcının tüm aşamaları tamamlama amacı sürer; eksik yerel kabul veya açık orijinal görevden devam et.

| Sıra | Kalan iş | Önce okunacak gerçek giriş |
|---:|---|---|
|1| Mevcut HEAD’in CI kapısını doğrula; **A11 tarayıcı kabulü tamam (16/16)**. **Ölçü/dönem bağı eklendi (AW-14 binding amendment, 274 test)**; kalan: sayıdan sonra yazılan tanımlar, eş anlamlılar ve gerçek anlamsal entailment | progress güncel devir; phase11-browser-qa.json; narrative.py ve llm_eval; valid-ID precision anlamsal entailment değildir |
|2| Gerçek model erişimi + dondurulmuş TR/EN karar/intent golden/OOD/injection/citation eval (**harness v2 hazır: plan/decide/claims/narrate; tipli anlatı doğrulayıcısı mekanik**) | llm.py,decisions.py,narrative.py,llm_eval; gerçek402; accuracy null. Hesap/ödeme değişikliği otomatik yok |
|3| Tahmin kalitesi — **v2 protokolü (16 Ekim gece) + v3 bant geçerliliği (16 Ekim öğleden sonra)**: kayıtlı adaylar, geliştirme-only seçim, ayrı final pencere, MASE/sMAPE/bias, teşhisler; bant ölçeği yalnız geliştirme yuvarlanan kapsamasıyla seçilir, sonlu-örneklem conformal kuantil; UCI %90 bandı geliştirmede 0,85, final 0,70 (kalibre değil). Ülke dilimleri tamam (UK/NL/EIRE); genişlik raporu ve son test eksik-kapsama uyarısı tamam. Kalan: dönem hata dilimleri, ≥2 sezon veriyle seasonal naive; final pencere üstünde tuning yapma |
|4| A7 orijinal: generic metric/explicit schema ve OOF stacking (**Parquet, ondalık virgül/tarih biçimi seçenekleri ve olasılık metrikleri 16 Ekim'de eklendi — AW-14**) | preparation.py,ml.py,FoldPreprocessor; metricgrain/unit, group/time-safe nestedOOF; trainfoldSMOTE; modelserving ayrı |
|5| A8 orijinal: tenant+subjectRLS,retention,tombstone,hardresource | core/src/workbench.ts,migrations0017–0021; existingauth/PGpermits; kayıtrefleri silinmeden lifecycle;5MHTTPcancel/backpressurestress; prodIdP/dışdeployment ayrı |
|6| A9 orijinal: governedBI ve conversationreference | core/src/publish*.ts, lineage/reportformats spec; adviSU conversation_memory/sourceindexer/retrievalpolicy adayları; ownerUUIDarchive genelmemory değildir |
|7| A10 orijinal:5–8gerçek kullanıcı pilotu, accessibility/production ölçüm | TEST_GUIDE; görev/consent/observedtime/errors, ekranokuyucu/zoom/contrast; sahte katılımcı yok |
|8| Veri ve iş kararının geçerliliği | iade/marj/stok/elastikiyet/capacity, kontrollüpilot; supportbusinessvalidationşuanda0; nedensel etki/ROI yalnız veriyle |
|8b| Worker soğuk başlangıcı: DuckDB parametreli sorgular pandas'ı yükler (~1 s); filtreli overview/forecast ve decisions (~2,1 s) için katalogla doğrulanmış güvenli bağlama veya kalıcı worker süreci; ölçümle kapat | `analysis/worker.py filters_for`, `forecast.py`, `evaluate_decisions.py`; phase11-performance.json |
|9| SNIPS/LSTM ve ileri rerank | önce realanalytics intentcorpus+TFIDFbaseline; ölçülmüşkazanç yoksa ekleme; vocabularyfit/paddinginvariance |

Yeni ajan: repo /Users/selmanyilmaz/Projects/context-layer. Önce progress → bu sıra → authoritative spec → kod → anlamlı test → gerçek browser → receipt/report/mirror/README → secret/diff → aynı açık PR'a push. Eski çalışan modülü yeniden port etme; port_sources.py adaptasyonları overwrite eder. Proje tokenı yalnız ignoredserver0600; loglama/commitleme.
