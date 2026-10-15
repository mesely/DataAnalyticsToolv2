# Aşama 5 — veri hazırlama

Sözleşme: `specs/analyst-workspace-phase5.md` (AW-8). Kapsam: herhangi bir CSV'yi güvenli profilleme; perakende analitiğine açık alan eşlemesi, değişiklik taslağı, kalite/tutar önizlemesi ve yeniden hesaplanan import makbuzu. Genel ML veri yükleme bu profili sonraki aşamada kullanır. Parquet ve keyfi metrik derleyici açık backlog; bitmiş sayılmaz.

Uygulama: `analysis/preparation.py`, `worker.py`, `core/src/workbench.ts`, `core/web/src/workbench/Preparation.tsx`; test `analysis/tests/test_preparation.py`, core workbench integration. UI mevcut dört ana görevi korur, içe aktarma diyalogunda kademeli ilerler.

Devam eden ajan: önce sözleşmeyi oku; önizlemenin kaynakla aynı dönüşümden hesaplandığını ve receipt'in tüm dönüşümleri bağladığını doğrula. Test raporu olmadan tamam yazma. Token/ham kullanıcı CSV'sini commit etme.

Yerel kabul: generic CSV → 7 alan eşleme → önizleme → dedup değişikliğiyle
receipt geçersizleşmesi → yeniden önizleme → gerçek dashboard import tarayıcıda
çalıştırıldı. 14 preparation testi geçiyor. Güncel geniş CI ve rapor ayrıca
PHASE_5_REPORT içinde; bunun yokluğunu tam kabul sanmayın.
