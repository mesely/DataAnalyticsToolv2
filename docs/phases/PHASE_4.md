# Aşama 4 — kontrollü üretim hazırlığı ve yerel teslim

Güncel durum: yerel uygulama paketi tamam; canlı HF çağrısı HTTP402, dış kabul kapıları açık. Kesin sonuç PHASE_4_REPORT.md içinde. Kullanıcı ayrıca Gemini asset üretimi ve GitHub push yetkisi verdi.

Önce progress.md, PHASE_3_REPORT.md, NEXT_BACKLOG.md ve mevcut test/route kodları. Kullanıcı yerelde uygulama ve devam aşamalarını yetkilendirdi; GitHub yayın, canlı müşteri sistemi veya production deploy ayrıca yetki ister. Rutin yerel hazırlık/fix/test için tekrar izin isteme.

## Bağımsız yerel iş paketi

1. Bütün worker yollarını aynı admission/timeout/cancel sınırına al; catalog/import ve birden fazla core process durumunu incele. Bugünkü process-local sayaç production dağıtık kuyruk değildir.
2. Job/run/query/dataset yaşam döngüsünü tasarla: referanslı immutable veri sürümü, owner-visible kayıtlar, reversible archive, retention konfigürasyonu ve audit. İlgisiz dosya veya müşteri kaydı silme.
3. Source-code/build/dependency fingerprint ve metric/recipe sürüm sözleşmesi; replay golden seti. Eski v1/v2 artifact'ları sessizce yeni anlamla overwrite etme.
4. Tenant+subject izolasyonu/RLS için fixture ve negatif testler; gerçek IdP/Vault/roles mapping olmadan fixture'ı production diye sunma.
5. 0.5M/5M veri ve eşzamanlılık için yük planı, p50/p95/error/memory; gerçek ölçüm. Worker/DuckDB sınırı tüm Python process belleğine hard limit değildir. Cache anahtarına dataset+metric+visibility+owner sürümü girer.
6. Docker daemon hazırsa PHASE_1_REPORT'ta kalan sync-drill/sync-run/mcp-execute snapshot testlerini çalıştır. Kullanıcının başka konteynerleri nedeniyle daemon'u gelişigüzel restart etme. Bilinen baseline property beklentisi D-106.2'ye göre düzeltildi; üretim queue kodu değiştirilmedi.
7. Gereken gerçek görevli UX pilotu ve klavye/ekran okuyucu/zoom/contrast matrisi planı; ölçülmüş sonuç olmadan Hick/Fitts başarı yüzdesi yazma. İngilizce veri metinleri ve local fixture login ekranı polish backlog'unda.

## LLM alt paketi

Güncel durum: adviSU transport gerçek HF Llama plannerına bağlandı; server-side secret mevcut, gerçek inference HTTP402. Anahtar arama veya yeni token isteme; yapılandırılmış olmak başarılı model yanıtı değildir. Strict allowlist plan + local executor + numeric artifact yolu uygulanmıştır; başarılı canlı model/eval kredili hesap gerektirir. Model hiçbir zaman ham serbest Python veya kontrolsüz SQL çalıştırmaz. Generic OpenAI API entegrasyonuna girerken ilgili openai-docs becerisini oku. Key arama/varsayma; fiyat ve usage'ı uydurma. Serbest metindeki beyan edilmemiş yanlış iddialar mevcut numeric claim resolver tarafından otomatik yakalanmış sayılmaz.

Eval: en az50 kullanıcı görevi; golden numeric oracle, net/gross/currency/denominator, grain, OOD/ambiguity/injection/secret, multi-turn reference; actual tokens/cost/deadline, provider failure/circuit/retention. Replay verisi owner/visibility sınırında. Anahtarsız golden/sandbox testlerini bağımsız tamamla; gerçek sağlayıcı doğrulaması eksikse partial de.

## ML alt paketi

ML_REUSE_RESEARCH.md ve ML_SOURCE_INVENTORY.json somut dosya/hücre/sembol haritasıdır. Önce target/decision time/features/grain/group-time split/untouched holdout sözleşmesi. Influencer SMOTE/scaler/as-of feature sorunlarını ve SNIPS train+valid+test tokenizer/padding sorunlarını aynen taşıma. Baseline faydası yoksa LSTM zorunlu değil. Kaynak → hedef → adaptasyon → test kaydı ve model card gerekir.

## Kabul

PHASE_4_REPORT.md'de her madde gerçek pass/fail/pending ve somut kanıtıyla yer alır. Gerekli gerçek kimlik/model/pilot bilgisi olmadan tamamlanmış veya üretime hazır denmez. Kalanları yol/komut/son hatayla progress üst kartına ve son satırına işle; sonraki ajan baştan başlamasın.
