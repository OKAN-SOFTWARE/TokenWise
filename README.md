# TokenWise

### AI Token & Cloud Cost Optimizer

**Measure the work. Question the spend. Protect the quality.**

TokenWise is an original, offline-first engineering workbench for exploring the economics of AI inference. It combines a polished operator dashboard, deterministic scenario simulations, a prompt microscope, a quality-aware benchmark gate, a local evidence ledger, and explicitly opt-in AWS read-only billing / Bedrock integrations.

Created by **Okan Tiktas** / [OKAN-SOFTWARE](https://github.com/OKAN-SOFTWARE).

> **Current release:** v0.1.0 — educational/engineering preview. The default dashboard uses **fictional model tiers, illustrative token rates, and synthetic observations**. It is **not** connected to your AWS bill and cannot infer production-quality outcomes. The default web app makes zero AWS calls.

## Why this project exists

Most dashboards celebrate “tokens saved.” That's not the right objective: trimming context can make answers worse, a smaller model may fail harder tasks, and warm cache reads are not the same as fewer tokens. TokenWise introduces an **evidence gate** that judges an optimization by **cost per acceptable response**, retaining a quality pass-rate threshold and reporting p50/p95 latency.

Key differentiators:

1. **Optimization waterfall:** isolates savings from prompt trimming, cache reuse, and compact-model routing. Each stage is deterministic and explains its assumptions.
2. **Quality firewall:** a candidate is *rejected* if its passing-response rate falls below 95% of the baseline or its cost per passing answer doesn't improve. You supply real benchmark observations; the engine never invents quality scores.
3. **Prompt microscope:** lightweight local inspection of duplicates, long prefixes, and approximate token weight. Prompt text is not persisted.
4. **Evidence ledger:** SQLite stores scenario parameters and projections locally for repeatable experiments.
5. **Honest economics:** synthetic price catalog is clearly distinct from published AWS rates. AWS operations require explicit CLI commands.
6. **Zero dependencies for core:** Python 3.11+ is enough to run the UI, API, simulation engine, and unit tests.

## Quick start

Requirements: **Python 3.11 or newer**. No API key, Node.js, npm, database installation, or credit card is needed for demo mode.

```bash
cd tokenwise
python -m tokenwise
```

Visit **http://127.0.0.1:8765**. Stop with `Ctrl+C`.

On Windows, if `python` isn't on the PATH, try:

```powershell
py -3 -m tokenwise
```

To run on another port:

```bash
python -m tokenwise --port 9000
```

The local SQLite file is created as `.tokenwise-data/runs.sqlite3`; it is excluded from Git. Deleting that *specific* file resets local simulation history.

## Interface

- **Overview:** projected spend, savings, synthetic trend lines, and the savings decomposition.
- **Scenario Lab:** workload volume, prompt/output trimming, cache hit rate, eligible cached context, and compact-model routing.
- **Prompt Microscope:** inspect a non-sensitive prompt locally. Counts are approximate, not tokenization parity with a model.
- **Evidence Ledger:** compare demo observations using the quality gate and inspect your saved simulations.

To inspect real evaluation evidence, open the **Evidence, not optimism** section and import a JSON file of paired observations. [This fictional example dataset](examples/paired_benchmark.json) shows the required structure. Imported observations are assessed for quality and cost but are not stored in the ledger. Replace sample scores with results from your own reviewed test set.

## API

The HTTP API is served on the same local origin as the dashboard. It uses JSON and enforces size/range validation.

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/health` | GET | Confirm no AWS calls in web mode |
| `/api/overview` | GET | Synthetic baseline, model catalog, demo evidence |
| `/api/runs` | GET | List recent local scenarios |
| `/api/simulate` | POST | Compute and record a scenario |
| `/api/inspect` | POST | Estimate local prompt weight |
| `/api/compare` | POST | Evaluate paired baseline/candidate records |

### Simulate a workload

```bash
curl -s http://127.0.0.1:8765/api/simulate \
  -H 'Content-Type: application/json' \
  -d '{"requests_per_day":3000,"input_tokens":2500,"output_tokens":400,"prompt_trim_pct":20,"output_trim_pct":10,"cache_hit_pct":40,"cacheable_prefix_pct":60,"compact_route_pct":25,"days":30}'
```

### Benchmark an optimization, including quality

```bash
curl -s http://127.0.0.1:8765/api/compare \
  -H 'Content-Type: application/json' \
  -d '{"quality_floor":4,"rows":[{"baseline":{"cost_usd":0.04,"quality":4.5,"latency_ms":900},"candidate":{"cost_usd":0.02,"quality":4.5,"latency_ms":640}},{"baseline":{"cost_usd":0.04,"quality":4.6,"latency_ms":940},"candidate":{"cost_usd":0.025,"quality":4.3,"latency_ms":670}}]}'
```

Unlike a basic token counter, `compare` reports p50/p95 latency, quality pass rates, and **total cost / passing answers**. Quality scores must come from human review or a separate documented evaluation pipeline.

## Using real AWS data (optional)

The web dashboard does not connect to AWS. The optional AWS adapter is a separate explicit command, never called by the server.

```bash
python -m pip install -e '.[aws]'
aws configure sso
python -m tokenwise.aws_integration cost-report --days 7
```

This reads AWS Cost Explorer `UnblendedCost` by service, through your standard AWS credentials. You need permission for `ce:GetCostAndUsage`, a configured account, and Cost Explorer availability. API/billing reporting can have provider charges. Values may lag and are not invoices.

To make **one billable Amazon Bedrock call**, use a known supported model ID and the **current actual** model/region/token prices (USD per million). Put only non-sensitive content in the file:

```bash
python -m tokenwise.aws_integration invoke \
  --model-id YOUR_ENABLED_MODEL_ID \
  --region us-east-1 \
  --prompt-file your-safe-prompt.txt \
  --input-price YOUR_CURRENT_RATE \
  --output-price YOUR_CURRENT_RATE \
  --max-output-tokens 160 \
  --limit-usd 0.02 \
  --execute
```

The sample checks an approximate pre-flight cost estimate, but **it is not a hard billing cap**: tokenization and real prices can vary. You must deliberately specify `--execute` or no invocation occurs. Use least-privilege IAM and set AWS Budget alerts first. Avoid submitting confidential prompts to third-party models without authorization.

For deeper integration guidance and cost assumptions see [AWS guide](docs/aws-guide.md).

## Run tests

```bash
python -m unittest discover -s tests -v
python -m compileall -q tokenwise
```

The tests verify projections, zero-change behavior, cache savings, validation, quality regression rejection, invalid metrics, and SQLite persistence. GitHub Actions runs the test suite on Python 3.11 and 3.12.

## Docker — local access only

```bash
docker build -t tokenwise:dev .
docker run --rm -p 127.0.0.1:8765:8765 tokenwise:dev
```

The container binds to all interfaces internally only to work with Docker networking, while the example publishes the port **on the host loopback interface only**. Simulations within the disposable container are lost when it stops unless you mount a dedicated data volume.

Do **not** deploy the v0.1 local app to the public internet. It has no authentication, user segregation, rate limiting across clients, or TLS reverse proxy configuration. See [security](docs/security.md).

## Design choices and constraints

| Design | Why |
|---|---|
| Standard-library HTTP server | Demo runs on a fresh Python installation without dependency setup |
| Python `Decimal` | Stable cost arithmetic; avoids float-based dollar accumulation |
| Local SQLite with bounded history | Reproducible experiments without managed infrastructure |
| Fictional baseline and compact pricing | Never confuses a demo figure with an actual cloud provider rate |
| One explicit Bedrock CLI invocation | Separates costly operations from UI exploration |
| Paired evidence gate | Optimization is judged on quality-adjusted economics |
| Browser same-origin API | No external script/CDN or cross-origin calls needed |

Roadmap: import/export benchmark datasets, provider-specific real rate catalogs, warmup/cache-write modeling, CI benchmark regressions, optional S3/CloudWatch sink, and authenticated hosted deployment.

## References

- [AWS Well-Architected Cost Optimization](https://docs.aws.amazon.com/wellarchitected/latest/framework/cost-optimization.html)
- [AWS Cost Optimization Hub](https://docs.aws.amazon.com/cost-management/latest/userguide/cost-optimization-hub.html)
- [Amazon Bedrock Converse with Boto3](https://docs.aws.amazon.com/bedrock/latest/userguide/getting-started-api-ex-python.html)
- [Amazon Bedrock prompt caching](https://docs.aws.amazon.com/bedrock/latest/userguide/prompt-caching.html)
- [Amazon Bedrock token usage](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_TokenUsage.html)

## License

MIT — © 2026 Okan Tiktas. Built to learn, measure, and improve.
