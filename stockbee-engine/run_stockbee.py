#!/usr/bin/env python3
import argparse, json, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent/"src"))
from stockbee_engine import StockbeeInputError, run_stockbee

def main():
    p=argparse.ArgumentParser(description="Run Stockbee Taiwan momentum-burst engine on JSON input")
    p.add_argument("input"); p.add_argument("--pretty",action="store_true")
    a=p.parse_args()
    try:
        payload=json.loads(Path(a.input).read_text(encoding="utf-8"))
        print(json.dumps(run_stockbee(payload),ensure_ascii=False,indent=2 if a.pretty else None,sort_keys=True))
        return 0
    except (OSError,json.JSONDecodeError,StockbeeInputError) as e:
        print(json.dumps({"execution_status":"EXECUTED_PARTIAL","error":str(e)},ensure_ascii=False),file=sys.stderr); return 2
if __name__=="__main__": raise SystemExit(main())
