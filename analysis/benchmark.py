"""Repeatable local subprocess observation, never a production SLA."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import json, subprocess, sys, time, statistics, math
ROOT=Path(__file__).resolve().parent.parent

def one(_):
    start=time.perf_counter()
    proc=subprocess.run([sys.executable,"-m","analysis.worker"],cwd=ROOT,input=json.dumps({"action":"run","dataset":"uci","include_graph":True,"use_llm":False}),text=True,capture_output=True,timeout=45)
    obj=json.loads(proc.stdout)
    result=obj.get("result",{})
    return {"ms":round((time.perf_counter()-start)*1000),"ok":proc.returncode==0 and obj.get("ok") and result.get("summary",{}).get("gross_pence")==1066668454}

def main():
    stages=[]
    for concurrency in [1,3]:
        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            rows=list(pool.map(one,range(12)))
        values=sorted(x["ms"] for x in rows)
        stages.append({"concurrency":concurrency,"samples":len(rows),"p50_ms":statistics.median(values),"sample_p95_ms":values[math.ceil(.95*len(values))-1],"max_ms":max(values),"failures":sum(not x["ok"] for x in rows)})
    print(json.dumps({"dataset_rows":530104,"scope":"loopback subprocess full analysis; no HF; no HTTP/login/DB overhead; warm OS cache, small sample; not SLA or user benchmark","observations":stages},indent=2))
if __name__=="__main__": main()
