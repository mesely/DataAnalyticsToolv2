# Aşama 2 — güvenilir uzman keşfi ve karşılaştırma

## Yürütme kartı

Önce progress.md, PHASE_1_REPORT.md, bu dosya; sonra ilgili kod/test. Kullanıcı Aşama1 sonrası devamı açıkça istedi. Tek repo /Users/selmanyilmaz/Projects/context-layer. Aynı OIDC/CSRF/owner sınırları. Üretim verisi veya ücretli model yok.

## Önceden sabitlenen kapsam

1. Analiz bölümünde keşfedilebilir **SQL laboratuvarı** (ana navigasyonu artırma). Alper'in `sqlval.validate_statement` gerçek çağrılacak; materyalize retail şemasına çözümlenen tek SELECT/CTE. Buna ek dar AST/function allowlist, join/fanout ve recursive reddi, dosya/network/extension/system erişimi reddi. SQL sadece seçilen owner dataset üzerinde; müşteri kimlikleri view'dan çıkarılmış. Ekrandaki ülke/tarih filtreleri sorgunun `transactions` view'una uygulanır, kanıtta ayrı parametreler görünür. 500 sonuç satırı, 128MB, 1 thread, 5s query deadline; worker toplam45s. Bu canlı execute_sql token yolunun alternatifi değildir.
2. adviSU `_BM25` ile **metrik/şema/kaynak bağlam arama**: başlık/formül/not/şema dokümanları, query tokenları aynı normalization, skoru olmayan hit gösterme. Yetkili dataset dışında belge arama yok. UI'da arama ve tıklanabilir context sonuçları; embedding veya RAG diye yanlış adlandırma.
3. adviSU export_utils `rows_to_csv/rows_to_xlsx` ve saf source_of_truth hash fonksiyonlarını gerçekten adapte et. CSV/XLSX formula injection engeli; satır limiti ve kapsam açık, çalıştırılmış sorgu sonucu export. Numeric hücreleri numeric tut; müşteriid yok. Source commit/hash/symbol ledger.
4. **İki kayıt karşılaştırma**: yalnız subject-owned runlar; aynı metric version/currency; dataset hash ve filtre farkı açık. Delta/percent, sıfır payda için null; farklı kapsam nedensellik kanıtı değil. Recipe/result digest summary+series+rankings+preview+graph çıktılarını kapsar (time/runid hariç); başlangıç v1 kayıtlarına eskihash anlamı korunur.
5. Metrik kontrolleri: Brüt satış ve adet toplamlarda/kırılımlarda reconcile; distinct sipariş her aynı grain için bağımsız oracle ile kontrol edilir (ürün/dönem grupları arasında her zaman toplamsal değildir); custom SQL otomatik tanımlı revenue metriği sanılmaz. Invoice distinct grain açıklaması ve joins reddi görünür. Şema UI'da araştırma kolaylığı.

## Teknik dosya haritası

analysis/sql_lab.py: SQL validation/safe view/execution + result/evidence.
analysis/context.py: BM25 dokümanları/normalization.
analysis/adapted/exports.py ve identity.py: pinned extraction/adaptation, SOURCE_LEDGER additions.
analysis/worker.py: sql/context/export/diff bağımsız action integration; önce mevcut tests oku.
core/src/workbench.ts: authenticated sql/context/export/compare endpoint; aynı actor/global admission, owner kontrol, audit.
core/web/src/workbench/ExpertTools.tsx: progressive SQL/context panel ve source-safe export. Findings comparison: separate component if necessary. types/CSS/locale uyumlu.
analysis/tests/test_phase2.py ve core/test/workbench.test.ts: anlamlı oracles/reddetme/ownership cases.

## Kabul kapıları

- Bağımsız demo oracle ile aggregate query, filtreli view ve result cap doğrulanır. DDL/DML/multistatement/file/HTTP/tablefunction/unknowncolumn/customerid/join/recursive reddi; sonradan dataset değişmediği hash testi.
- Aynı auth/CSRF/owner kuralları yeni endpointlerde testli; export formül hücreleri gerçek CSV/XLSX okunarak doğrulanır; private run compare başka kimlikten404.
- BM25 exact match/unknownquery/normalization, diff compatible/incompatible/zero baseline ve result full digest sensitivity testli.
- Core/web build/typecheck, ilgili Phase1+2 testler; desktop/mobile/keyboard SQL→result→download, context search ve compare browser QA.
- PHASE_2_REPORT.md önce/sonra, gerçek test sayıları ve kalanlar; TEST_GUIDE/progress/REUSE_LEDGER güncel. Servis test için açık.

## Örnek devam

“Aşama2 devam”: önce rapordaki/üst progress kartındaki ilk eksik DoD; varsa çalışan kodu tekrar yazma.
“SQL hata”: minimal sorguyu tekrarla; parser finding mi engine error mı ayır; güvenlik kontrolünü kaldırarak geçirme.
“LLM nerede”: şu an provider code adapte/testli, key yok; gerçek çağrı/eval olmadan bağlı veya kaliteli diye raporlama.

## Bitiş sonrası

Aşama3 problem/holdout sözleşmesi ve bağımsız ML/temporal eval kapısı ister. Phase2'yi tamamlama eşiğini kalite/bütçe için sonradan daraltma. Eksik varsa partial diye yaz ve tam nerede kaldığını bırak.
