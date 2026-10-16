"""Model stand-ins with the same surface the product uses (invoke + get_last_telemetry)."""
from __future__ import annotations
from types import SimpleNamespace


class ScriptedModel:
    def __init__(self, reply_for):
        self._reply_for = reply_for
        self.calls = 0

    def bind(self, case, mode):
        self._case, self._mode = case, mode
        return self

    def invoke(self, messages):
        self.calls += 1
        return SimpleNamespace(content=self._reply_for(self._case, self._mode))

    def get_last_telemetry(self):
        return {"effective_provider": "scripted", "effective_model": self._mode, "latency_ms": 0,
                "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "cost_usd": 0.0}
