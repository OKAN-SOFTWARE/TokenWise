# Security policy for the learning preview

## Design guarantees

- The demo dashboard contains no third-party CDN/scripts/telemetry.
- The normal HTTP server makes no AWS calls.
- The server listens on loopback by default and blocks non-local `Host` headers.
- The POST API checks local origins, content type, maximum body length, and numeric bounds.
- The app has a restrictive Content Security Policy, `nosniff`, frame rejection and no referrer.
- The prompt inspector never persists the submitted text.
- SQLite uses parameterized queries and stores only scenario values/results.

## Known limitations

This is **not production-ready as a public multi-user service**. It does not implement user authentication, cross-device access policy, HTTPS termination, request quotas per account, encrypted-at-rest storage, adversarial prompt handling, or a security audit. Local processes with filesystem access may read the SQLite database.

The AWS CLI wrapper only provides a best-effort cost preflight using token approximations. It **cannot guarantee a hard billing cap**. Inspect current pricing, quotas, IAM permissions, and account budgets before executing a live call.

Do not put real credentials, private documents, protected data, or customer content in example prompts or test fixtures. Report vulnerabilities privately to the maintainer through an appropriate secure GitHub channel rather than posting exploit details publicly.
