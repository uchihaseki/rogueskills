# G6 / M3 Release Readiness Gate Report

Date: 2026-07-23

## Live

- Case Pack: `release-readiness@1.0.0`
- Repository: `openai/openai-python@main`
- Candidate SHA: `e67afa88433dad9f97e733ae8f2ee6e9c240bc51`
- Case ID: `case-run-c13f4265126a4e2ca3eb58b5b61b61f3`
- Status: `succeeded`
- Recommendation: `blocked`
- Check Runs: 19 total, 18 successful, 1 failing, 0 pending
- Runtime Verified: `true`
- Evaluation: 100, 6/6 hard gates passed
- Sources / Facts: 4 / 7
- Source Bundle Digest:
  `sha256:2ee8fdb00d0693de9ae05d5def02df1ecdea8de8934e6ad0afbbfc893d505f64`
- Artifact ID: `artifact-43343ba872d8678c944e`
- Artifact Digest:
  `sha256:43343ba872d8678c944e62bb5b518f507918604dd87ab00d9015165158e51b07`

The release is blocked because one captured GitHub Check Run failed. The report is
runtime-verified because all evidence, fact-integrity, CI, review-work, citation, and
recommendation-consistency gates passed.

## Verified Replay

- Case ID: `case-run-6ef697f4ee8745d6b84d91cfe305b07e`
- Source Case ID: `case-run-c13f4265126a4e2ca3eb58b5b61b61f3`
- Facts equal Live: `true`
- Sources equal Live: `true`
- Live Gateway calls before / after: `1 / 1`
- Runtime Verified: `true`
- Replay Artifact Digest:
  `sha256:c55d438807f8235ecfb3e64af3576227a9abac1573d363286920f005abf8bdbf`

An additional replay was executed in a sandbox process without GitHub DNS access:

- Offline Replay ID: `case-run-81a5c71032b44a5daf3c0b7c4fe035a5`
- Live Gateway calls: `0`
- Runtime Verified: `true`
- Score: 100

## Regression

- Python: 86 passed
- Release Case tests: 13 passed
- Changed-file Ruff: passed
- `git diff --check`: passed
- Frontend smoke: 3 passed
- Vue type-check: passed
- Frontend production build: passed
- Alembic upgrade/downgrade: passed

Gate: **PASS**
