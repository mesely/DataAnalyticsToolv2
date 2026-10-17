"""Shared test isolation: no test may read the developer's saved provider keys or provider environment."""
import pytest

PROVIDER_ENV = ("GROQ_API_KEY", "GROQ_MODEL", "HF_TOKEN", "HF_MODEL", "LLAMA_BASE_URL", "LLAMA_MODEL", "LLAMA_API_KEY")


@pytest.fixture(autouse=True)
def _no_saved_provider(monkeypatch, tmp_path_factory):
    monkeypatch.setattr("analysis.llm.LOCAL", tmp_path_factory.mktemp("llm-local"))
    for name in PROVIDER_ENV:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("LLM_EVAL_PAUSE", "0")
    monkeypatch.setattr("analysis.llm_eval.evaluate.LIVE_PAUSE", 0.0)
