# AWS integration and cost safety

## Recommended learning sequence

1. **Offline first:** run TokenWise and compare 3 simulated scenario choices.
2. **Cost observability:** enable AWS Budgets and alerts. Understand that alerts notify and do not automatically impose a hard cap.
3. **AWS reporting:** allow narrowly scoped `ce:GetCostAndUsage`, then run `cost-report` for an explicit date range.
4. **Bedrock inference:** enable a supported model, confirm actual regional pricing and `bedrock:InvokeModel` scope, and make one deliberately billable call with `--execute`.
5. **Benchmark:** measure real latency, token usage and actual costs separately, with a hand-reviewed quality rubric.

Use IAM roles/SSO instead of embedding permanent access keys. Do not put confidential production prompts in shell arguments, the repository, screenshots, or diagnostic logs.

## Caveat: AWS pricing is not a single global value

Pricing can depend on the model ID, region, inference option, prompt caching semantics, input/output ratio, data residency, and provider discounts. The sample model rates in the dashboard are fictional. For real decisions use live official [Bedrock pricing](https://aws.amazon.com/bedrock/pricing/) and [AWS pricing calculator](https://calculator.aws/).

Amazon Bedrock `usage` typically includes `inputTokens` and `outputTokens`, with extra fields such as `cacheReadInputTokens` and `cacheWriteInputTokens` for models/features that support caching. Make sure a cost implementation respects the specific accounting and billing rules of the selected API/model. [TokenUsage reference](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_TokenUsage.html).

## Beyond token optimization: AWS cloud economics

- Rightsize EC2/RDS/compute using metrics and [Cost Optimization Hub](https://docs.aws.amazon.com/cost-management/latest/userguide/cost-optimization-hub.html).
- Compare on-demand, reserved, and Savings Plans only after validating utilization and commitment risk.
- Reduce unnecessary S3/EBS data retention; avoid unplanned network egress and idle NAT gateways.
- Compare Lambda and always-on compute based on real traffic, execution duration, memory, concurrency, and warm/cold behavior.
- Instrument service cost, latency, errors, and user/business value in one observable system.

## Deployment warning

`tokenwise` is a **localhost learning workbench**, not an authenticated public cloud application. If turning this into SaaS later, first add authentication, authorization, CSRF and abuse protections, auditable user-scoped data isolation, TLS, external secrets management, deployment health checks, and comprehensive security review.
