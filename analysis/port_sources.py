"""Reproduce the pinned, attributable source extraction used in this extension."""
from pathlib import Path
import ast, hashlib, json, urllib.request
ROOT=Path(__file__).resolve().parent
SOURCES={
 'advisu':('mesely/adviSU','e1e224134a3ce9a52c758c35ce517b1d42c9b75a'),
 'polieco':('mesely/PoliEcoTRNetSci','c1705e76a9e2c36ddda36c95d03bd733cf52a17a'),
}
ledger=[]
def get(project,path):
 repo,sha=SOURCES[project]; data=urllib.request.urlopen(f'https://raw.githubusercontent.com/{repo}/{sha}/{path}',timeout=30).read(); text=data.decode()
 ledger.append(dict(source_repo=repo,source_commit=sha,source_path=path,source_sha256=hashlib.sha256(data).hexdigest()))
 return text

def write(name,text):
 (ROOT/'adapted'/name).write_text(text)

provider=get('advisu','server/modules/llm_providers.py')
# Preserve transport/model code; remove the academic application's settings factory.
tree=ast.parse(provider); lines=provider.splitlines(True)
node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='settings_from_config')
provider=''.join(lines[:node.lineno-1])+'''def settings_from_config():
    raise ProviderConfigurationError("Supply explicit analytics ProviderSettings; academic config is not imported.")
\n'''+''.join(lines[node.end_lineno:])
write('providers.py',provider)
guard=get('advisu','server/modules/guardrails.py').replace('from modules.localization import message','from .messages import message').replace('from modules.resource_controls import MAX_INPUT_CHARS','MAX_INPUT_CHARS = 8000')
write('guardrails.py',guard)
write('messages.py','def message(key, language="tr", **kwargs):\n    return "İstek güvenli analiz sınırlarının dışında." if language == "tr" else "The request is outside safe analytics boundaries."\n')
confidence=get('advisu','server/modules/confidence.py').replace('from modules import intents','from . import intents')
tree=ast.parse(confidence);lines=confidence.splitlines(True)
node=next(n for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='_INTENT_POLICIES' for t in n.targets))
confidence=''.join(lines[:node.lineno-1])+'''_INTENT_POLICIES = {
    "analytics": IntentPolicy(True, False, False, True),
    "security_sensitive": IntentPolicy(False),
}
'''+''.join(lines[node.end_lineno:])
write('confidence.py',confidence)
write('intents.py','def to_canonical(value):\n    return str(value or "analytics").strip().lower()\n')
write('language.py',get('advisu','server/modules/language.py'))
write('claim_coverage.py',get('advisu','server/modules/claim_coverage.py'))
source=get('advisu','server/modules/bm25_retriever.py');tree=ast.parse(source); lines=source.splitlines(True)
node=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='_BM25')
write('lexical.py','"""BM25 scoring extracted from adviSU; dataset documents are supplied by the caller."""\nimport math\nfrom collections import Counter\n'+''.join(lines[node.lineno-1:node.end_lineno])+'\n')
source=get('polieco','src/build_term_interval_polarization.py');tree=ast.parse(source);lines=source.splitlines(True)
names={'zscore_frame','build_sparse_signed_graph','compute_gatekeeper_scores'}
parts=['"""Pinned PoliEco numeric kernels. Dense similarity is bounded to <=60 items by caller."""\nimport pandas as pd\nimport numpy as np\n']
for n in tree.body:
 if isinstance(n,ast.FunctionDef) and n.name in names:parts.append(''.join(lines[n.lineno-1:n.end_lineno])+'\n')
write('networks.py','\n'.join(parts))
(ROOT/'adapted'/'__init__.py').write_text('')
(ROOT/'SOURCE_LEDGER.json').write_text(json.dumps(ledger,indent=2))
print('adapted',len(ledger),'source modules')
