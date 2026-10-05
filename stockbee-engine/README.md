# Stockbee Momentum Burst Screener — Taiwan Mode v1.0.0

Executable, auditable research engine for the Stockbee Taiwan workflow used by Quant Research Daily v3.4.

## Status

- A branch: implemented
- B branch: implemented
- C branch: NOT_IMPLEMENTED until its fixed range-expansion rule is formally specified
- ATR14 (Wilder): implemented
- RVOL20: implemented
- SMA20/SMA60/prior-20D-high: implemented
- Hard Reject: explicit SELL/stop, incomplete current bar, unresolved corporate action
- input/output SHA-256: implemented
- official 100-point score / A/A- grade: intentionally disabled until all seven score components are formally defined and executable

A program can be EXECUTED_VERIFIED while official score/grade remain N/A if the scoring specification is incomplete.

## Run

```bash
python run_stockbee.py input.json --pretty
```

Input JSON requires completed daily bars. `turnover_twd` must be actual turnover; the engine never estimates it as close × volume.

## Branch A

- return >= 4%
- volume > previous completed-day volume
- liquidity_pass == true

Missing liquidity evidence => UNKNOWN.

## Branch B

- return >= 4%
- actual turnover >= NT$30m
- close > open
- CLV >= 0.75
- real body >= price-tier threshold OR >= 0.8 × Wilder ATR14

Body thresholds:
- <50: 1.5 TWD
- 50–<150: 3 TWD
- 150–<500: 8 TWD
- >=500: 20 TWD

## Branch C

Not simulated. Returns `NOT_IMPLEMENTED` until the fixed rule is committed.

## Execution semantics

`EXECUTED_VERIFIED` means the Python engine actually ran on supplied input and computations are reproducible. It does not authorize trading.

## Research-only constraints

No automatic orders. Missing data stay missing. SELL/stop/Hard Reject override positive evidence. Incomplete current-day daily bars are not valid EOD inputs.
