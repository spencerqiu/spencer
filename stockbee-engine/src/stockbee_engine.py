from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Iterable, Optional

ENGINE_NAME = "stockbee-momentum-burst-screener"
ENGINE_VERSION = "1.0.0"

class StockbeeInputError(ValueError):
    pass

def _sha256(obj: Any) -> str:
    payload = json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()

def _mean(values: list[float]) -> Optional[float]:
    return sum(values) / len(values) if values else None

def _sma(values: list[float], n: int) -> Optional[float]:
    return _mean(values[-n:]) if len(values) >= n else None

def _body_threshold(price: float) -> float:
    if price < 50: return 1.5
    if price < 150: return 3.0
    if price < 500: return 8.0
    return 20.0

def _true_range(cur: dict[str, float], prev: dict[str, float]) -> float:
    return max(cur["high"]-cur["low"], abs(cur["high"]-prev["close"]), abs(cur["low"]-prev["close"]))

def wilder_atr(rows: list[dict[str, Any]], period: int = 14) -> Optional[float]:
    if len(rows) < period + 1: return None
    trs=[_true_range(rows[i], rows[i-1]) for i in range(1,len(rows))]
    if len(trs) < period: return None
    atr=sum(trs[:period])/period
    for tr in trs[period:]:
        atr=((atr*(period-1))+tr)/period
    return atr

def _normalize_rows(raw: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    rows=[]
    for r in raw:
        row={"date":str(r["date"]),"open":float(r["open"]),"high":float(r["high"]),"low":float(r["low"]),"close":float(r["close"]),
             "volume":None if r.get("volume") is None else float(r["volume"]),
             "turnover_twd":None if r.get("turnover_twd") is None else float(r["turnover_twd"])}
        if row["high"] < max(row["open"],row["close"]) or row["low"] > min(row["open"],row["close"]):
            raise StockbeeInputError(f"INVALID_OHLC:{row['date']}")
        rows.append(row)
    rows.sort(key=lambda x:x["date"])
    dates=[r["date"] for r in rows]
    if len(dates)!=len(set(dates)): raise StockbeeInputError("DUPLICATE_DATE")
    return rows

@dataclass
class StockbeeResult:
    symbol:str; name:Optional[str]; market:Optional[str]; data_as_of:str
    engine_name:str; engine_version:str; execution_status:str; data_status:str
    return_pct:float; open:float; high:float; low:float; close:float; prev_close:float
    volume:Optional[float]; prev_volume:Optional[float]; turnover_twd:Optional[float]
    CLV:Optional[float]; real_body:float; ATR14:Optional[float]; RVOL20:Optional[float]
    SMA20:Optional[float]; SMA60:Optional[float]; prior_20d_high:Optional[float]
    distance_from_20d_high:Optional[float]; Extension_ATR:Optional[float]
    TriggerLow:Optional[float]; RiskDistance:Optional[float]
    branch_A_status:str; branch_B_status:str; branch_C_status:str
    hard_reject:bool; reject_reason:Optional[str]; score:Optional[int]; grade:Optional[str]
    precheck_status:str; missing_fields:list[str]; execution_timestamp:str
    input_hash:str; output_hash:str

def run_stockbee(payload: dict[str, Any]) -> dict[str, Any]:
    rows=_normalize_rows(payload.get("ohlcv",[]))
    if len(rows)<2: raise StockbeeInputError("INSUFFICIENT_HISTORY")
    cur,prev=rows[-1],rows[-2]
    ret=cur["close"]/prev["close"]-1.0
    clv=None if cur["high"]==cur["low"] else (cur["close"]-cur["low"])/(cur["high"]-cur["low"])
    real_body=cur["close"]-cur["open"]
    atr14=wilder_atr(rows,14)
    prior_vols=[r["volume"] for r in rows[:-1] if r["volume"] is not None]
    rvol20=None
    if cur["volume"] is not None and len(prior_vols)>=20:
        base=_mean(prior_vols[-20:]); rvol20=None if not base else cur["volume"]/base
    closes=[r["close"] for r in rows]
    sma20=_sma(closes,20); sma60=_sma(closes,60)
    prior20=[r["high"] for r in rows[:-1][-20:]]
    prior20d_high=max(prior20) if len(prior20)==20 else None
    liquidity_pass=payload.get("liquidity_pass")
    if liquidity_pass not in (True,False,None): raise StockbeeInputError("INVALID_LIQUIDITY_FLAG")
    branch_a="UNKNOWN"
    if cur["volume"] is not None and prev["volume"] is not None and liquidity_pass is not None:
        branch_a="PASS" if (ret>=0.04 and cur["volume"]>prev["volume"] and liquidity_pass) else "FAIL"
    branch_b="UNKNOWN"
    if cur["turnover_twd"] is not None and clv is not None and atr14 is not None:
        body_ok=(real_body>=_body_threshold(cur["close"])) or (real_body>=0.8*atr14)
        branch_b="PASS" if (ret>=0.04 and cur["turnover_twd"]>=30_000_000 and cur["close"]>cur["open"] and clv>=0.75 and body_ok) else "FAIL"
    branch_c="NOT_IMPLEMENTED"
    hard_reject=False; reject_reason=None
    if payload.get("candidate_direction")=="SELL":
        hard_reject,reject_reason=True,"EXPLICIT_SELL_OR_STOP"
    elif payload.get("current_bar_complete") is False:
        hard_reject,reject_reason=True,"CURRENT_BAR_INCOMPLETE"
    elif payload.get("corporate_action_unresolved") is True:
        hard_reject,reject_reason=True,"CORPORATE_ACTION_UNRESOLVED"
    missing=[]
    for n,v in (("ATR14",atr14),("RVOL20",rvol20),("SMA20",sma20),("SMA60",sma60),("prior_20d_high",prior20d_high),("turnover_twd",cur["turnover_twd"])):
        if v is None: missing.append(n)
    if liquidity_pass is None: missing.append("liquidity_rule")
    precheck="PRECHECK_INCOMPLETE"
    if sma20 is not None and sma60 is not None:
        precheck="PRECHECK_PASS" if (cur["close"]>sma20>sma60) else "PRECHECK_CONDITIONAL"
    trigger_low=payload.get("trigger_low"); trigger_low=None if trigger_low is None else float(trigger_low)
    input_hash=_sha256(payload)
    base=StockbeeResult(
        symbol=str(payload.get("symbol","")),name=payload.get("name"),market=payload.get("market"),data_as_of=str(payload.get("data_as_of") or cur["date"]),
        engine_name=ENGINE_NAME,engine_version=ENGINE_VERSION,execution_status="EXECUTED_VERIFIED",data_status="PARTIAL" if missing else "COMPLETE",
        return_pct=ret,open=cur["open"],high=cur["high"],low=cur["low"],close=cur["close"],prev_close=prev["close"],
        volume=cur["volume"],prev_volume=prev["volume"],turnover_twd=cur["turnover_twd"],CLV=clv,real_body=real_body,
        ATR14=atr14,RVOL20=rvol20,SMA20=sma20,SMA60=sma60,prior_20d_high=prior20d_high,
        distance_from_20d_high=None if prior20d_high is None else cur["close"]/prior20d_high-1.0,
        Extension_ATR=None if sma20 is None or atr14 in (None,0) else (cur["close"]-sma20)/atr14,
        TriggerLow=trigger_low,RiskDistance=None if trigger_low is None else (cur["close"]-trigger_low)/cur["close"],
        branch_A_status=branch_a,branch_B_status=branch_b,branch_C_status=branch_c,
        hard_reject=hard_reject,reject_reason=reject_reason,
        score=None,grade=None,precheck_status=precheck,missing_fields=missing,
        execution_timestamp=datetime.now(timezone.utc).isoformat(),input_hash=input_hash,output_hash="")
    output=asdict(base)
    output["output_hash"]=_sha256({k:v for k,v in output.items() if k!="output_hash"})
    return output
