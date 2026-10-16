# Aşama9 — karar kaydı ve rapor ek paketi

AW-12 yerel kayıt/rapor bölümü uygulanmıştır. Governed liveBI publish ve
genel konuşma referansı/Mongo→PG memory adaptasyonu kapanmadı.

- Migration `core/migrations/0021_workbench_decisions.sql`: immutable UUID,
  subject,dataset_id,recipe,result,created_at; owner/time index. Eskileri değiştirme.
- `core/src/workbench.ts`: POST `/forecast`, POST `/decisions` aynı viewer,
  CSRF, datasetpermission, bounded worker/PGpermit/cancel/audit. GET `/decisions`
  son50owner kaydı; GET `/decisions/:id` other-owner404 ve rol iptalinde403.
- Kaydedilen hesap kendi source/filter/build/method/doc hash'lerini taşır.
  Arşivden açma snapshot okumasıdır; mevcut veriyle sessizce yeniden hesaplamaz.
- Gerçek adviSU `response_formatter.py` `_plain_text/split_summary/compact_summary`
  gövdeleri `analysis/adapted/formatting.py` içinde çalışır. Başka model çağrısı
  olmadan mevcut sabit aday metninden kısa özet çıkarır; Mongo veya akademik audit yok.
- Kaynak commit e1e224134a3ce9a52c758c35ce517b1d42c9b75a,
  dosyaSHA57f89f2e7386b0410fc8625bab11d0f31138d5de93c5bf6fbe1ff6382eba5b5e;
  SOURCE_LEDGER12pinli upstream dosyası read-only doğrulandı.
- Her öneride veri/grafik dayanak düğmesi; source artifact path, birim ve
  gerçek ülke/ürün çifti tablosu, haftalık grafik+erişilebilir testtablosu.
- JSON, Markdown rapor ve XML bağlam indir. Ham CSV/fitted model/canlı token yok.
- Aynı kaydı yeniden açmada revision key ile scroll0 ve kapalı disclosure reset;
  CmdK kararstüdyosu eylemi; native dialog/Esc ve responsive grid.

Raporlar owner-visible yerel artifact'tır, yeni kamu paylaşım/publish yetkisi
vermez. Retention/tombstone/RLS ve role eşlemeli gerçek üretim deployment ayrı
kapılardır; subject predicate'i tenantRLS diye anlatma.
