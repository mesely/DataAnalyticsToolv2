// Language-model isolation for every test file: the analysis worker inherits this environment, so an empty
// credential directory and no provider variables mean every model request falls back to the local planner.
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";

for (const name of ["GROQ_API_KEY", "GROQ_MODEL", "HF_TOKEN", "HF_MODEL", "LLAMA_BASE_URL", "LLAMA_MODEL", "LLAMA_API_KEY"])
  delete process.env[name];
process.env.CONTEXT_LLM_DIR = mkdtempSync(path.join(tmpdir(), "cl-llm-empty-"));
