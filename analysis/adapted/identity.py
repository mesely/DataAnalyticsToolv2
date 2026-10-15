"""Adapted from adviSU pinned e1e2241 server/modules/source_of_truth.py; see SOURCE_LEDGER.json."""

from hashlib import sha256

def content_hash_bytes(content: bytes) -> str:
    return sha256(content).hexdigest()

def content_hash_text(text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()

def source_id_for(document_type: str, content_hash: str) -> str:
    return f"{document_type}:{content_hash[:24]}"

def embedding_cache_key(provider: str, model: str, text: str) -> str:
    safe_provider = (provider or "unknown").strip().replace(":", "_")
    safe_model = (model or "unknown").strip().replace(":", "_")
    return f"{safe_provider}_{safe_model}_{content_hash_text(text)}"
