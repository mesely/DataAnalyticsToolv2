# Ürün sözleşmesi ek kararı — Aşama 1

Kullanıcı yetkisi 15 Ekim 2026: Context Layer dış MCP profil/skill modelini koruyarak aynı kimlik alanında first-party analist çalışma alanı eklenir. Bu, HLR §2 no-LLM kararının yerel opt-in ürün uzantısıdır. Deterministik generator değişmez. Provider model üretimi opsiyonel; kaynak faktörler ve sayısal sonuçlar deterministik kalır. Model çıktısı yetki veremez ve SQL'i kendisi serbestçe çalıştıramaz.

Aşama 1 yalnız açık demo veri setlerine erişen sınırlı, parametreli analiz yetenekleri sunar; execute_sql/validation token sözleşmesi canlı kaynaklarda aynen korunur. Dataset/run erişimleri aynı session/CSRF ve sunucudaki rol/owner denetimiyle sınırlandırılır. Yeni iş grafiği ayrı GraphArtifact'tır; mevcut lineage graph formatı değişmez.

analysis_result artifact: dataset id/input hash/recipe version/metric definition/filters/canonical output digest/run actor/time. Veri örneği ile bütün veri ayrılır; currency GBP, kaynak tarih aralığı tarihsel; güncel iş sonucu diye sunulmaz.
