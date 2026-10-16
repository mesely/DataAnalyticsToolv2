"""Deterministic LLM evaluation harness (benchmark cases, scripted providers, scoring, report).

Scores three things the product actually delegates to a model or guards locally:
  plan   — question routing (intent + scope) through analysis.llm.plan_question
  decide — candidate selection over the decision XML packet through analysis.decisions.validate_selection
  claims — numeric claim resolution against computed artifacts through analysis.claims
Scripted providers validate the evaluator itself; `local` scores the product's deterministic fallback; `hf`
is the real provider and is reported as BLOCKED whenever no successful live answer exists. Nothing here
fabricates a real-model number."""
