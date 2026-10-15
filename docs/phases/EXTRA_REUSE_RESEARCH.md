# İlave kaynak kod araştırması

15 Ekim 2026; yalnız aday keşfi, taşınmış kod değildir. İncelenen fonksiyon/import envanteri EXTRA_REUSE_RESEARCH.json içinde. adviSU pinned e1e2241 commit.

| Kaynak ve somut semboller | Değer / uygun aşama | Gerekli adaptasyon |
|---|---|---|
| export_utils.py rows_to_csv, rows_to_xlsx | Gerçek tablo export, Aşama 2 | Course/audit row builder'larını çıkar; genel kolon schema, CSV/XLSX formula-injection escaping ve kontrol karakteri politikası ekle. Kaynak stdlib/openpyxl, düşük bağımlılık |
| source_of_truth.py content_hash_bytes/text, source_id_for, embedding_cache_key | Input identity/cache invalidation, Aşama 2 | Saf hash fonksiyonlarını çıkar; Mongo/config importlarını taşıma. Dataset/metric/visibility version cache anahtarına katılmalı |
| response_formatter.py split_summary, compact_summary, ensure_summary_section, merge_structured_content | Uzun açıklamayı özet/kanıt panellerine bölme, Aşama 2 | Academic terminology silinir; mevcut veri/metric/graph card schema'larına adapter. Regex sanitizer güvenlik tekeli değil |
| logging_utils.py Timer, time_block, estimate_cost_usd | T16 telemetry ve model maliyet ölçümü | Süre yardımcıları doğrudan çıkarılabilir. Token tahmini gerçek provider usage diye sunulamaz; hardcoded fiyat güncel sanılmaz |
| conversation_memory.py resolve_reference, recent_turns, _summarise | “Bunu geçen ayla karşılaştır” takip sorusu, Aşama 2/3 | Course reference -> dataset/run/metric reference; Mongo owner-query -> mevcut Postgres owner-query. Silme/retention/PII policy gerekir; tüm modülü kopyalayıp Mongo ekleme |
| retrieval_policy.py build_metadata_filter, check_profile | Yetki/dataset/metric scope, Aşama 2 | Curriculum/major sınıfları çıkarılır, core server identity/visibility authority olarak kalır. Aday filtre nesnesi kendi başına yetki vermez |
| file_lifecycle.py _safe_filename, _save_bytes, cascade_delete_source | Upload version/delete lifecycle | Akademik/WhatsApp veri yolları taşınmaz; FastAPI UploadFile yerine core upload sınırı. Aktif run'ın veri sürümü silinmeden tombstone/referans denetimi gerekir |

PoliEco ek adayları daha önce okunan build_economic_shock_study.py içinde stage_months/build_axis_validation ve step6 sağlamlık yardımcılarıdır. Bootstrap/placebo domain IO ve global RNG'den ayrılmalı. Signed gatekeeper iki kutup varsayar; genel ilişki skoruna sessizce dönüştürülmez. LSTM ve RF kodları sonraki aşamada problemin veri/split/test koşullarıyla modülleştirilecek.
