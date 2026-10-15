# Aşama 6 — sızıntı kontrolleri olan ML deneyi

AW-9 kapsamı: açık CSV hedef/özellik/split/karar-anı seçimi; train-fold preprocessing, baseline/RF/linear adayları, isteğe bağlı yalnız sayısal SMOTE, eğitim CV'siyle seçim, bağımsız holdout, owner model kartı ve JSON kanıtı. Bu aşama orijinal NEXT_BACKLOG içindeki ML işinin uygulanabilir ilk paketidir; OOF stacking, model serving, kalibrasyon/predictive intervals ve üretim BI/pilot ayrı açıktır. Rapor testler/gerçek veri çalışmaları bitince doldurulur.

Kaynak: Influencer notebook cell63 ve66. Runtime adapter `analysis/adapted/ml_preprocessing.py`; yeni orchestrator `analysis/ml.py`; ekran `core/web/src/workbench/ModelStudio.tsx`; migration0020. Önce `specs/analyst-workspace-phase6.md`, ardından adapter/orchestrator/test oku. Gelecek bilgi/proxy leakage tamamen otomatik saptanıyor iddiası yasak. Kaynak notebook'un eski başarı sayıları bu ürüne taşınmaz.
