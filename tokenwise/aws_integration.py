"""Optional, explicit AWS operations. Never called by the demo HTTP server.

Examples:
  python -m tokenwise.aws_integration cost-report --days 7
  python -m tokenwise.aws_integration invoke --model-id MODEL_ID \
    --prompt-file sample.txt --input-price 0.50 --output-price 2.00 \
    --limit-usd 0.02 --execute
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from .engine import estimate_tokens


def client(service: str, region: str):
    try:
        import boto3
    except ImportError as exc:
        raise SystemExit("Install the optional AWS dependency: python -m pip install '.[aws]'") from exc
    return boto3.client(service, region_name=region)


def cost_report(days: int) -> dict:
    if not 1 <= days <= 90:
        raise SystemExit("--days must be between 1 and 90")
    end = datetime.now(timezone.utc).date()  # exclusive
    start = end - timedelta(days=days)
    ce = client("ce", "us-east-1")
    token = None
    services: dict[str, Decimal] = {}
    currency = "USD"
    while True:
        params = {"TimePeriod": {"Start": str(start), "End": str(end)},
                  "Granularity": "DAILY", "Metrics": ["UnblendedCost"],
                  "GroupBy": [{"Type": "DIMENSION", "Key": "SERVICE"}]}
        if token:
            params["NextPageToken"] = token
        response = ce.get_cost_and_usage(**params)
        for interval in response.get("ResultsByTime", []):
            for group in interval.get("Groups", []):
                record = group["Metrics"]["UnblendedCost"]
                currency = record.get("Unit", currency)
                service = group["Keys"][0]
                services[service] = services.get(service, Decimal(0)) + Decimal(record["Amount"])
        token = response.get("NextPageToken")
        if not token:
            break
    return {"period_start": str(start), "period_end_exclusive": str(end),
            "metric": "UnblendedCost", "currency": currency,
            "service_costs": [{"service": key, "cost": str(value.quantize(Decimal('.0001')))}
                              for key, value in sorted(services.items(), key=lambda kv: kv[1], reverse=True)],
            "note": "Cost Explorer reporting may lag and is not a final invoice."}


def invoke(args: argparse.Namespace) -> dict:
    if not args.execute:
        raise SystemExit("Real Bedrock invocation is disabled without --execute")
    if not args.prompt_file.is_file() or args.prompt_file.stat().st_size > 40_000:
        raise SystemExit("--prompt-file must exist and be no larger than 40 KB")
    prompt = args.prompt_file.read_text(encoding="utf-8")
    if not prompt.strip():
        raise SystemExit("Prompt is empty")
    rates = (args.input_price, args.output_price, args.limit_usd)
    if any(not amount.is_finite() or amount <= 0 for amount in rates):
        raise SystemExit("Use positive finite rates and a positive USD limit")
    if not 1 <= args.max_output_tokens <= 10000:
        raise SystemExit("--max-output-tokens must be 1–10000")
    # Two times a text heuristic is NOT a hard upper bound. It is a warning guard.
    predicted_input = estimate_tokens(prompt) * 2 + 64
    ceiling = (Decimal(predicted_input) * args.input_price
               + Decimal(args.max_output_tokens) * args.output_price) / Decimal(1_000_000)
    if ceiling > args.limit_usd:
        raise SystemExit(f"Rejected: approximate pre-flight ${ceiling:.6f} exceeds ${args.limit_usd}.")
    print(f"Approximate pre-flight: ${ceiling:.6f} USD; not a guaranteed billing cap")
    response = client("bedrock-runtime", args.region).converse(
        modelId=args.model_id,
        messages=[{"role": "user", "content": [{"text": prompt}]}],
        inferenceConfig={"maxTokens": args.max_output_tokens, "temperature": 0.2},
    )
    usage = response.get("usage", {})
    answer = "".join(part.get("text", "") for part in response["output"]["message"]["content"])
    # Cache read/write rates vary. No cache is requested in this simple example.
    estimated_cost = (Decimal(usage.get("inputTokens", 0)) * args.input_price
                      + Decimal(usage.get("outputTokens", 0)) * args.output_price) / Decimal(1_000_000)
    return {"model": args.model_id, "region": args.region, "answer": answer,
            "usage": usage, "estimated_usd": str(estimated_cost),
            "note": "Uses user-supplied model rates; check billing for actual charges."}


def main():
    parser = argparse.ArgumentParser(description="Explicit read-only AWS costs / billable Bedrock requests")
    commands = parser.add_subparsers(dest="operation", required=True)
    report = commands.add_parser("cost-report", help="Read AWS Cost Explorer unblended costs")
    report.add_argument("--days", type=int, default=7)
    request = commands.add_parser("invoke", help="Send one explicitly authorized Bedrock request")
    request.add_argument("--region", default="us-east-1")
    request.add_argument("--model-id", required=True)
    request.add_argument("--prompt-file", type=Path, required=True)
    request.add_argument("--input-price", type=Decimal, required=True, help="Published USD per million input tokens")
    request.add_argument("--output-price", type=Decimal, required=True, help="Published USD per million output tokens")
    request.add_argument("--limit-usd", type=Decimal, required=True, help="Approximate pre-flight safety threshold")
    request.add_argument("--max-output-tokens", type=int, default=160)
    request.add_argument("--execute", action="store_true", help="Required; this request can incur charges")
    args = parser.parse_args()
    payload = cost_report(args.days) if args.operation == "cost-report" else invoke(args)
    print(json.dumps(payload, indent=2, default=str))


if __name__ == "__main__":
    main()
