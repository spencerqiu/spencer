import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from stockbee_engine import run_stockbee

def synthetic_rows(n=65):
    rows=[]; px=100.0
    for i in range(n):
        o=px; c=px+0.6
        rows.append({"date":f"2026-{7+i//28:02d}-{1+i%28:02d}","open":o,"high":c+1,"low":o-1,"close":c,
                     "volume":1_000_000+i*10_000,"turnover_twd":120_000_000})
        px=c
    prev=rows[-2]["close"]
    rows[-1].update({"open":prev*1.01,"low":prev*1.005,"high":prev*1.08,"close":prev*1.07,
                     "volume":rows[-2]["volume"]*2,"turnover_twd":500_000_000})
    return rows

def test_branch_a_b_and_metrics():
    out=run_stockbee({"symbol":"TEST","ohlcv":synthetic_rows(),"liquidity_pass":True,"candidate_direction":"BUY","current_bar_complete":True})
    assert out["execution_status"]=="EXECUTED_VERIFIED"
    assert out["branch_A_status"]=="PASS" and out["branch_B_status"]=="PASS"
    assert out["branch_C_status"]=="NOT_IMPLEMENTED"
    assert out["ATR14"] is not None and out["RVOL20"] is not None
    assert out["input_hash"] and out["output_hash"]
    assert out["score"] is None and out["grade"] is None

def test_sell_hard_reject():
    out=run_stockbee({"symbol":"TEST","ohlcv":synthetic_rows(),"liquidity_pass":True,"candidate_direction":"SELL"})
    assert out["hard_reject"] is True and out["reject_reason"]=="EXPLICIT_SELL_OR_STOP"
