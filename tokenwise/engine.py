"""Cache-aware, deterministic scenario engine. Rates are illustrative."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal, ROUND_HALF_UP
from math import ceil, isfinite
from typing import Any

M = Decimal(1_000_000)


@dataclass(frozen=True)
class ModelRate:
    id: str
    name: str
    input_per_m: Decimal
    output_per_m: Decimal
    cache_read_per_m: Decimal

    def json(self) -> dict:
        return {"id": self.id, "name": self.name, "input_per_m": str(self.input_per_m),
                "output_per_m": str(self.output_per_m), "cache_read_per_m": str(self.cache_read_per_m)}


# Intentionally fictional tiers and prices; NEVER describe as real AWS rates.
CATALOG = {
    "balanced": ModelRate("balanced", "Balanced / standard", Decimal("1.20"), Decimal("5"), Decimal("0.12")),
    "compact": ModelRate("compact", "Compact / efficient", Decimal("0.25"), Decimal("1"), Decimal("0.025")),
    "deep": ModelRate("deep", "Deep / advanced", Decimal("3"), Decimal("12"), Decimal("0.30")),
}


@dataclass(frozen=True)
class Scenario:
    requests_per_day: int = 12000
    input_tokens: int = 2400
    output_tokens: int = 520
    prompt_trim_pct: int = 22
    output_trim_pct: int = 12
    cache_hit_pct: int = 46
    cacheable_prefix_pct: int = 55
    compact_route_pct: int = 32
    days: int = 30

    @classmethod
    def parse(cls, data: Any) -> Scenario:
        if not isinstance(data, dict):
            raise ValueError("Expected JSON object")
        bounds = {"requests_per_day": (1, 2_000_000), "input_tokens": (1, 500_000),
                  "output_tokens": (1, 100_000), "prompt_trim_pct": (0, 80),
                  "output_trim_pct": (0, 80), "cache_hit_pct": (0, 100),
                  "cacheable_prefix_pct": (0, 100), "compact_route_pct": (0, 100),
                  "days": (1, 366)}
        if set(data) - set(bounds):
            raise ValueError("Unknown scenario field")
        values = asdict(cls())
        for name, (minimum, maximum) in bounds.items():
            value = data.get(name, values[name])
            if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
                raise ValueError(f"{name} must be an integer from {minimum} to {maximum}")
            values[name] = value
        return cls(**values)


def money(amount: Decimal) -> str:
    return str(amount.quantize(Decimal(".01"), rounding=ROUND_HALF_UP))


def unit_cost(inp: Decimal, out: Decimal, rate: ModelRate, cache_read: Decimal = Decimal(0)) -> Decimal:
    return ((inp - cache_read) * rate.input_per_m + cache_read * rate.cache_read_per_m
            + out * rate.output_per_m) / M


def simulate(s: Scenario) -> dict:
    """Project trim -> warm cache reads -> compact routing, without quality claims.

    No cache write cost or infrastructure charge is modeled. This distinction
    intentionally prevents showing projections as real monthly AWS bills.
    """
    n = Decimal(s.requests_per_day * s.days)
    orig_in, orig_out = Decimal(s.input_tokens), Decimal(s.output_tokens)
    inp = orig_in * (100 - s.prompt_trim_pct) / 100
    out = orig_out * (100 - s.output_trim_pct) / 100
    cached = inp * s.cache_hit_pct * s.cacheable_prefix_pct / 10000
    base = n * unit_cost(orig_in, orig_out, CATALOG["balanced"])
    trimmed = n * unit_cost(inp, out, CATALOG["balanced"])
    warmed = n * unit_cost(inp, out, CATALOG["balanced"], cached)
    portion = Decimal(s.compact_route_pct) / 100
    routed = n * ((1 - portion) * unit_cost(inp, out, CATALOG["balanced"], cached)
                  + portion * unit_cost(inp, out, CATALOG["compact"], cached))
    risk = "ELEVATED" if (s.prompt_trim_pct >= 40 or s.output_trim_pct >= 35 or s.compact_route_pct >= 65) else "REVIEW"
    return {
        "mode": "SIMULATION", "requests": int(n), "baseline_usd": money(base),
        "projected_usd": money(routed), "savings_usd": money(base - routed),
        "savings_pct": round(float(100 * (base - routed) / base), 2),
        "baseline_input_tokens": int(n * orig_in), "optimized_input_tokens": int(n * inp),
        "baseline_output_tokens": int(n * orig_out), "optimized_output_tokens": int(n * out),
        "cache_read_tokens": int(n * cached), "cost_per_1000_usd": money(routed / n * 1000),
        "waterfall": [
            {"label": "Before", "usd": money(base), "gain": "0.00"},
            {"label": "Prompt trim", "usd": money(trimmed), "gain": money(base - trimmed)},
            {"label": "Cache reads", "usd": money(warmed), "gain": money(trimmed - warmed)},
            {"label": "Model routing", "usd": money(routed), "gain": money(warmed - routed)},
        ], "risk": risk,
        "risk_note": ("Aggressive changes require especially careful accuracy and completion tests."
                      if risk == "ELEVATED" else "Validate answer quality before using projected settings."),
        "disclaimer": "Fictional model prices, warm-cache assumptions; excludes cache writes, other AWS costs and taxes.",
    }


def estimate_tokens(text: str) -> int:
    """Approximate planning heuristic, not a model tokenizer."""
    return ceil(len(text.encode("utf-8")) / 4) if text else 0


def inspect_prompt(text: Any) -> dict:
    if not isinstance(text, str) or len(text) > 25000:
        raise ValueError("Prompt must be text no longer than 25,000 characters")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    seen, repeated = set(), 0
    for line in lines:
        normalized = " ".join(line.casefold().split())
        if normalized in seen:
            repeated += 1
        seen.add(normalized)
    tips = []
    if repeated:
        tips.append(f"Review {repeated} repeated line(s), keeping any intentional emphasis.")
    if len(text) > 1800:
        tips.append("Place stable, long instructions in a reusable cacheable prefix if supported.")
    if len(lines) > 18:
        tips.append("Summarize irrelevant older context, preserving requirements and facts.")
    if "```" in text:
        tips.append("Send only code relevant to the current task, while preserving its exact syntax.")
    if not tips:
        tips.append("Looks compact. Benchmark changes against a consistent quality rubric.")
    return {"estimated_tokens": estimate_tokens(text), "characters": len(text),
            "lines": len(lines), "duplicate_lines": repeated, "tips": tips,
            "warning": "Local approximation. Real counts depend on the model and request structure."}


def compare_runs(rows: Any, quality_floor: float = 4) -> dict:
    """The evidence gate accepts only supplied observations, never invented quality."""
    if not isinstance(rows, list) or not 1 <= len(rows) <= 2000:
        raise ValueError("Provide between 1 and 2000 paired rows")
    if isinstance(quality_floor, bool) or not isinstance(quality_floor, (float, int)) or not 1 <= quality_floor <= 5:
        raise ValueError("quality_floor must be 1 to 5")
    report = {}
    for variant in ("baseline", "candidate"):
        costs, scores, latencies = [], [], []
        for row in rows:
            if not isinstance(row, dict) or not isinstance(row.get(variant), dict):
                raise ValueError(f"Missing {variant} observation")
            ob = row[variant]
            v = [ob.get("cost_usd"), ob.get("quality"), ob.get("latency_ms")]
            if any(isinstance(x, bool) or not isinstance(x, (float, int)) or not isfinite(x) for x in v):
                raise ValueError("Metrics must be finite numbers")
            cost, score, latency = v
            if cost < 0 or latency < 0 or not 1 <= score <= 5:
                raise ValueError("Out-of-range metrics")
            costs.append(cost)
            scores.append(score)
            latencies.append(latency)
        passing = sum(score >= quality_floor for score in scores)
        latencies.sort()
        report[variant] = {
            "total_usd": round(sum(costs), 4), "pass_rate": round(100 * passing / len(rows), 2),
            "cost_per_pass": round(sum(costs) / passing, 4) if passing else None,
            "p50_ms": latencies[ceil(.5 * len(rows)) - 1],
            "p95_ms": latencies[ceil(.95 * len(rows)) - 1],
        }
    a, b = report["baseline"], report["candidate"]
    accepted = (b["pass_rate"] >= a["pass_rate"] * .95 and
                a["cost_per_pass"] is not None and b["cost_per_pass"] is not None and
                b["cost_per_pass"] < a["cost_per_pass"])
    return {"count": len(rows), **report, "gate": "PASS" if accepted else "REJECT",
            "gate_reason": "Must retain 95% of baseline pass rate and lower cost per passing answer.",
            "source": "Supplied benchmark data; no model quality scores were fabricated."}
