# SNIPS ve Influencer: somut yeniden kullanım araştırması

15 Ekim 2026. Bu dosya **araştırma ve sonraki uygulama sözleşmesidir**; aşağıdaki ML kodları mevcut ürün runtime'ına henüz taşınmadı. Pinned notebook kaynaklarının SHA ve seçilmiş kod hücreleri ML_SOURCE_INVENTORY.json içinde; hücre numaraları sıfır tabanlıdır. Çıktı grafikleri/eskiden kaydedilmiş başarı sayıları yeni ürünün ölçümü sayılmaz.

## SNIPS

Repo: https://github.com/mesely/NLP-Intent-Detection-with-SNIPS-Dataset.git
Commit: 74deda2b6f6d188e590045c4f922d6491881726c
Dosya: intent-prediction.ipynb

| Hücre / sembol | Gerçekten alınabilecek parça | Hedef ve zorunlu adaptasyon |
|---|---|---|
| 4 load_data_from_splits / shuffle_and_split_data / save_data_to_new_splits | Ayrılmış veri dosyası okuma ve tekrar üretilebilir split araçları | analysis/ml/intent_data.py; Colab/Drive path çıkar, analytics label/manifest/group/template split ekle |
| 13 clean_text, 14 preprocess_text | Temizleme ve normalizasyon gövdeleri | Soru içindeki tablo adı/tarih/sayı/negasyonu silmemeli; TR/EN token testleri. NLTK download'ı request sırasında çalışmaz |
| 17 TF-IDF, 24 SVD, 47/49/56 evaluate/prepare helpers | LSTM öncesi ucuz sparse baseline ve raporlar | sklearn Pipeline; vectorizer/SVD fit yalnız train; sparse memory limit, macro-F1 / per-intent recall / OOD ret |
| 66 SimpleTokenizer / IntentDataset / LSTMIntentClassifier | Küçük PyTorch intent sınıflandırıcısının sınıf gövdeleri | analysis/ml/intent.py; tokenizer yalnız train, versioned vocab/label map, length-aware packed sequence, fixed PAD/OOV, inference timeout/CPU cap |
| 37 SlotGatedModel | Intent + slot extraction modeli | Analytics entity/metric/date label seti varsa alternatif deney. SNIPS label/weights doğrudan analytics'e ait değildir |

**Taşımadan düzeltilecek:** hücre35 tokenizer ve maksimum sequence uzunluğunu train+valid+test üzerinden belirliyor. Vocab/length politikası train üzerinde kurulmalı, valid/test yalnız transform olmalı. Hücre66 forward() son hidden state'i pad uzunluğu hesaba katılmadan alıyor; embedding padding_idx LSTM recurrent güncellemelerini kendiliğinden durdurmaz. Gerçek uzunluklarla pack_padded_sequence veya son geçerli state seçimi ve padding-invariance testi gerekir. Bu bulgular notebook'taki bütün sonuçların yanlış olduğunu kanıtlamaz; yeni ürün için sızıntısız/kararlı bir sözleşme gerektirir.

## Influencer

Repo: https://github.com/mesely/Influencer-Category-and-Like-Prediction-Stacking-SMOTE-RF.git
Commit: b217890ec18c35180c7ac7bc3a8dcd28a6c1794e
Dosya: influencer_classification_and_like_count_regression.ipynb

| Hücre / sembol | Gerçekten alınabilecek parça | Hedef ve zorunlu adaptasyon |
|---|---|---|
| 52 count_hashtags / count_emojis | Saf metin sayımları | Social analytics connector geldiğinde analysis/features/social.py; missing/unicode fixture testleri. Retail'e zorla eklenmez |
| 53 extract_group_features / 55 extract_group_features_test | Profil + geçmiş paylaşım özellik çıkarımı | Tek fit/transform adapter; feature schema ve zaman cutoff. avg_like/comment yalnız hedef gönderiden ÖNCE bilinen geçmişten |
| 60 create_features | Ratio, segment ve interaction dönüşümleri | sklearn TransformerMixin; zero/missing/negative policy, input copy, OneHotEncoder(handle_unknown) ile train-fit kolon schema |
| 30/33 SMOTE + RF / LogisticRegression stacking | Dengesiz sınıflama model fabrikası | imblearn Pipeline içinde fold-içi SMOTE; class_weight baseline; OOF stacking ve untouched group/time holdout. Kategorik veride vanilla SMOTE otomatik seçilmez |
| 63 apply_log_transform / preprocess_features | Skew dönüşüm ve normalization gövdeleri | fit ve transform ayrılır. Mevcut kod verilen scaler'a da fit_transform uyguluyor; valid/test'te yalnız transform |
| 66 log_mse_like_counts | Log alanında regresyon değerlendirme fonksiyonu | analysis/ml/metrics.py; y_true/y_pred negatif/prediction policy, hedef zaten log ise ikinci log uygulanmaz |
| 67 backward_elimination / 70 randomized RF tuning | Özellik seçme ve tuning iş akışı | Yalnız training/nested CV içinde; holdout feature seçiminde kullanılmaz; compute budget |
| 71 evaluate_rounding | Yuvarlama sonrası rapor karşılaştırması | Yuvarlama stratejisi validation'da sabitlenir; test üzerinde en iyisini seçmek yasak |

**Taşımadan düzeltilecek:** hücre30'da bütün train matrisi SMOTE ile çoğaltılıyor; hücre33 bu resampled matris üzerinde fold kuruyor. Yeni uygulamada oversampling her eğitim fold'unun içine alınır. Hücre53'te kullanılan user_posts_data'nın kapsamı açık değilse avg_like/comment hedefi veya geleceği kapsayabilir; as-of join ve group/time split zorunlu. Hücre60 ayrı dummy üretim/sonradan kolon tamamlama yerine fit edilmiş tek schema kullanmalı. Eski CV accuracy'nin yeni ürün genellemesi olarak aktarılması doğru olmaz.

## Uygulamaya giriş kapısı

Önce gerçek hedefi seç: sınıflandırılan/tahmin edilen şey, karar anı, kullanılabilir özellikler, gözlem grain'i, kullanıcının faydası ve maliyet. Sonra frozen dataset hash + split ids + baseline + macro-F1/PR-AUC veya MAE/RMSLE + kalibrasyon + hata dilimleri + eğitim süresi/bellek kaydı. Basit model yeterliyse LSTM zorunlu değil. Model çıktısı kimlik/yetki/SQL güvenliği kararı vermez. Kaynak fonksiyon → hedef → değişiklik → test kaydı olmadan “adapte edildi” denmez.
