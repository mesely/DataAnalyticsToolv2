# Aşama8 — kanıta bağlı karar ek paketi

AW-11 uygulanmıştır; eski tenantRLS/hardresource/retention/5MHTTPstres işleri
açık kalır. Tam kabul durumu PHASE_10_REPORT ve progress üst/son karttadır.

`analysis/decisions.py` ve `knowledge/business-methods.json`:

1. Mevcut owner/filtre kapsamında overview+copurchase+forecast yeniden hesaplanır.
2. Ölçüm, pazar yoğunlaşması, birlikte-alım deneyi, tahmin ve isteğe bağlı
   senaryo için yerel adaylar; gözlemi nedensel etkiye dönüştürmez.
3. Trace40 +30sipariş20 + bağımsız dönemlerde naiften düşük hata20 +
   iş doğrulaması20. Son bileşen henüz0; doğruluk olasılığı/ROI değildir.
   UCI mevcut adayları60/100; skor yükselsin diye kanıt uydurulmadı.
4. Önce skor azalır; eşitlikte balanced/growth/resilience görev önceliği.
5. Fiyat/hacim -50..100%, bütçe0..£1m; Decimal ROUND_HALF_UP.
   Son tam hafta baz, bağımsız varsayımlar; brüt fark bütçeden ayrı, kâr değil.
6. Gerçek adviSU BM25 çekirdeği üç sürümlü yöntem notunu seçer. XML
   trust_boundary / computed_evidence / methodology_documents / allowed_candidates /
   output_contract. Serializer escaping,16KB bütçe, iki uçta talimat, few-shot.
7. Llama yalnız açık opt-in ile sayısal özetleri ve statik yöntemleri alır.
   Ham satır/ürün/ülke adı/özel başlık gitmez. Yalnız mevcut actionID +
   izinli reason JSON dönebilir; serbest metin/sayı/SQL/referans reddedilir.
8. Başarılı model seçimi yalnız odak işareti ekler. Sıralama, puan, açıklama,
   adımlar ve kaynaklar yerel hesap motorunda kalır. HTTP402 yerel özeti bozmaz.

Bu sınırlı sürüm genel amaçlı danışman veya nedensel/prescriptive optimizer
olarak sunulmaz. Arbitrary business document upload, maliyet/kısıt optimizer,
serbest LLM prose entailment ve gerçek model doğruluğu henüz yok.
