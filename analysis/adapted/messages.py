def message(key, language="tr", **kwargs):
    return "İstek güvenli analiz sınırlarının dışında." if language == "tr" else "The request is outside safe analytics boundaries."
