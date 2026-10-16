# Context Layer · Decision brief

Ölçüm sözleşmesini onaylayın. Haftalık tahmini planlama öncesi gözden geçirin.

## Scope

Dataset SHA-256: f6003ea90b31435e94afdb17facc703aedeb4f85a3a992ab7cb1586e21c3c636
Filters: {}
Metric: positive invoice-line gross GBP; not net revenue or profit.
Kalite sayıları kaynak veri setinin tamamına aittir; satış sayıları mevcut filtrelere aittir.

## Ranked investigations

### 1. Ölçüm sözleşmesini onaylayın — 60/100

Dışlanan satırları ve korunan tekrarları inceleyin; brüt satışın iş hedefinizle uyumunu kontrol edin.

- excluded: 11805 rows (artifacts.quality.excluded_rows)
- duplicates: 5268 rows (artifacts.quality.duplicate_rows)

Missing / limitations:
- İade, maliyet ve marj verisi yok.
- Kalite sayıları kaynak veri setinin tamamına aittir; satış sayıları mevcut filtrelere aittir.

Decision sequence:
1. Kaynak ve kalite panelini inceleyin.
2. Tekrar ve iade politikasını veri sahibiyle onaylayın.
3. Onaydan sonra aynı filtrelerle yeniden hesaplayın.

### 2. Haftalık tahmini planlama öncesi gözden geçirin — 60/100

Son dört geçmiş test noktasındaki hatayı referans yöntemle karşılaştırın. Tahmin, mevcut geçmişin devamına ilişkin sınırlı bir projeksiyondur.

- forecast_mae: 55787.19 GBP (forecast.holdout.selected.mae_gbp)
- baseline_mae: 41723.39 GBP (forecast.holdout.naive.mae_gbp)

Missing / limitations:
- Mevsimsellik, tatiller ve gelecekteki ticaret rejimi doğrulanmadı.

Decision sequence:
1. Tahmin ve test tablosunu inceleyin.
2. Operasyon takvimiyle karşılaştırın.
3. Gerçekleşen yeni haftayı ayrı ölçün.

### 3. Pazar yoğunlaşmasını inceleyin — 60/100

En yüksek satışlı ülkenin payını inceleyin. Pay, tek başına büyüme veya risk nedeni değildir.

- country_share: 0.846113 ratio (derived.leading_country_share)
- gross: 1066668454 pence (artifacts.summary.gross_pence)

Missing / limitations:
- Pazar büyüklüğü, stok ve marj bilinmiyor.

Decision sequence:
1. Ülke sıralamasını açın.
2. Kapasite ve marjı doğrulayın.
3. Küçük bir pazar deneyi planlayın; etkiyi ayrıca ölçün.

### 4. Birlikte alım için kontrollü deney tasarlayın — 60/100

Görülen birlikte alımı, kampanya etkisi olarak yorumlamadan test adayı olarak kullanın.

- basket_support: 825 distinct_invoices (artifacts.graph.edges.0.weight)

Missing / limitations:
- Nedensel etki, stok, ürün/hizmet sınıfı ve marj bilinmiyor.

Decision sequence:
1. İlişki ağındaki ürün çiftini inceleyin.
2. Stok, hizmet kalemleri ve marjı kontrol edin.
3. Kontrol grubu ve başarı ölçütü belirleyin.

### 5. Senaryo varsayımlarını doğrulayın — 60/100

Hacim ve fiyatı bağımsız değiştiren varsayımsal hesabı değerlendirin. Hesap, talep tepkisini veya kârlılığı tahmin etmez.

- scenario_base: 32437083 pence (scenario.baseline_pence)
- scenario_delta: 1621854 pence (scenario.gross_delta_pence)

Missing / limitations:
- Esneklik, maliyet ve gerçek kampanya etkisi ölçülmedi.

Decision sequence:
1. Varsayımları iş sahibiyle teyit edin.
2. Bütçeyi ve kapasiteyi ayrıca kontrol edin.
3. Önce küçük ve ölçülebilir bir pilot uygulayın.

## Score interpretation

Dayanak skoru bir kontrol listesi puanıdır; doğruluk olasılığı veya beklenen getiri değildir. 30+ sipariş yalnız açıklanan örnek yeterlilik eşiğidir. İş doğrulaması yapılmadığı için bu bileşen 0.

## Forecast

Status: ready
Untouched four-origin holdout: {"mae_gbp": 55787.19, "n": 4, "rmse_gbp": 68309.8262435482, "wape": 0.15945456873641253}
Naive benchmark: {"mae_gbp": 41723.39, "n": 4, "rmse_gbp": 50662.65895022635, "wape": 0.11925650240980316}
Positive invoice-line gross GBP; excludes returns/cancellations and is not net revenue or profit.
Only complete Monday–Sunday weeks; boundary fragments excluded. Dates without observed rows count as zero; collection completeness is not established.
One-step rolling origins use only earlier observations. Final four origins never select the method.
Residual envelope is empirical, not a guaranteed or calibrated prediction interval. Historical records may not represent future trading.

## Declared scenario

{"assumed_gross_pence": 34058937, "assumptions": {"budget_gbp": 100.0, "price_pct": 0.0, "volume_pct": 5.0}, "baseline_pence": 32437083, "budget_pence": 10000, "gross_delta_pence": 1621854, "note": "User assumptions, not predicted causal effects. Price and volume vary independently; demand elasticity, margin, capacity, returns and campaign effectiveness are unknown. Budget is shown separately; gross delta is not profit or ROI."}

## Methodology guidance

association-limits: https://otexts.com/fpp3/regression.html · SHA-256 8e8744b51eac9b38be10cbe0a1ea5b996c4d0094cd261e7b08ce03f8ec6949f1
measurement-contract: https://archive.ics.uci.edu/dataset/352/online+retail · SHA-256 ec05f2caaa73f8f300ef56c45ac8d9788481c3c542d325e42b3e7600b8d740da
forecast-validation: https://otexts.com/fpp3/toolbox.html#time-series-cross-validation · SHA-256 856f99cd0deb4ee662b52a983ca125baef1124487e3affc6fdcc6b83bbf60ae6

## Provider

Status: not_requested
No causal impact, profit or model accuracy is implied by this brief.
