# AW-10: Prediction and visual foundations

2026-10-16 · User-authorized additive workbench amendment.

Additive retail prediction service /forecast: same viewer, CSRF, permitted dataset, shared bounded worker. Daily positive gross GBP. Require >=16 complete covered calendar weeks for development plus holdout; trim incomplete boundary weeks, aggregate complete Monday–Sunday weeks, <=260 weeks. Missing dates within recorded coverage treated as zero observed sales, not a claim of complete collection. Forecast ONE next complete week; compare last-week naive and mean4 via rolling-origin training-only selection, keep final four origins untouched as holdout. MAE/RMSE/WAPE and per-origin records; no invented percentage accuracy. Empirical absolute-error band from development residuals, >=8 residuals, no calibrated coverage guarantee. Explicit insufficient-data state. Recipe/data/code fingerprint and stable hash bind outputs. UI opens inside Analysis; four primary navs unchanged. Theme defaults OS preference with in-memory explicit toggle, no client persistence (D103.1). Semantic surfaces in light and navy/charcoal, visible focus, reduced motion, custom Gemini geometry icons; provenance plain text.

## Scope amendment
The latest request prioritizes predictive/prescriptive evidence and visual identity for phases7–10. The earlier provisional Parquet/generic semantic compiler/OOF stacking/tenant RLS/resource-hardening/live BI/user-pilot tasks remain in NEXT_BACKLOG; stage labels do not declare these complete. Platform deterministic generator and governed execute/publish unchanged.
