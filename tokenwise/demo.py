"""Fixed fictional benchmark observations for the interface demo."""
from __future__ import annotations

from .engine import CATALOG, Scenario, compare_runs, simulate


def overview() -> dict:
    scenario = Scenario()
    result = simulate(scenario)
    history = []
    for day in range(1, 15):
        # Deterministic and clearly synthetic, not fabricated historical billing.
        variation = 0.82 + (day % 5) * 0.045 + (day // 5) * 0.012
        history.append({"day": f"D{day:02}",
                        "baseline": round(float(result["baseline_usd"]) / 30 * variation, 2),
                        "optimized": round(float(result["projected_usd"]) / 30 * variation, 2)})
    rows = []
    for i in range(24):
        rows.append({
            "baseline": {"cost_usd": round(.018 + (i % 4) * .001, 4),
                         "quality": 4.7 if i % 8 else 3.6, "latency_ms": 790 + (i % 6) * 52},
            "candidate": {"cost_usd": round(.009 + (i % 3) * .001, 4),
                          "quality": 4.5 if i % 9 else 3.7, "latency_ms": 620 + (i % 5) * 36},
        })
    return {"scenario": scenario.__dict__, "result": result, "history": history,
            "evidence": compare_runs(rows), "model_rates": [rate.json() for rate in CATALOG.values()],
            "mode": "SYNTHETIC DEMO — NOT AWS ACCOUNT DATA"}
