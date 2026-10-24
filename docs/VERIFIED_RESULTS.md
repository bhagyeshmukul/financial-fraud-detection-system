# Earlier local baseline results

This file preserves the original four-window experiment. The current five-window router experiment is recorded separately in [ROUTER_RESULTS.md](ROUTER_RESULTS.md). Do not mix metrics across runs.

Measured on 23 October 2026 using the publisher datasets and the frozen chronological partitions below. These are research benchmarks, not validation against a current bank’s production traffic.

| Dataset | Served candidate | Accuracy | Precision | Fraud recall | PR-AUC | ROC-AUC |
|---|---|---:|---:|---:|---:|---:|
| credit_card | xgboost | 99.95% | 89.66% | 68.42% | 0.7386 | 0.9589 |
| banksim | xgboost_without_resampling | 99.55% | 88.48% | 67.22% | 0.8424 | 0.9950 |

Both profiles exceeded the desired 94% accuracy target and 80% precision target. **Neither reached the initial 80% fraud-recall goal.** Those misses are displayed in the dashboard and preserved in the report. Models and thresholds were selected on validation average precision/F1, not these test results.

The BankSim champion was the no-resampling XGBoost comparison. All three CV algorithms were also trained with SMOTENC. Do not claim resampling improved every result.

## Fraud and false alerts

- Credit-card test: 76 actual frauds; 52 detected and 24 missed. Six legitimate transactions were flagged. The test had 59,888 transactions.
- BankSim test: 1,440 actual frauds; 968 detected and 472 missed. There were 126 false alerts among 133,231 transactions.

## Evidence

- [Versioned benchmark summary](benchmark-summary.json) records dataset SHA-256, source/license, model identity, dependencies, partition boundaries and all candidate metrics.
- Full curves, model artifacts and input datasets remain in ignored local directories. Training recreates them from the documented publisher imports.
- Backend integration tests run against the isolated local PostgreSQL instance. Browser tests exercise the real API and its model artifacts, including both profiles, replay, CSV analysis, reviews, errors and mobile layout.
- Both profiles of the learning notebook execute against the verified data.
- Docker image execution remains a separate verification step where a Docker engine is available; YAML parsing alone is not an image build.

## CV result wording

> Evaluated Logistic Regression, Random Forest and XGBoost with training-only SMOTE/SMOTENC and chronological holdouts. Achieved 99.95% accuracy, 89.66% precision and 68.42% fraud recall on the ULB credit-card test period; built an interactive analysis, simulation and audit application.

Include the dataset, split and fraud metrics when discussing accuracy. BankSim is simulated data; analyst reviews do not establish new verified labels.

## Local traffic verification

One API worker, one inference thread per worker; the shared laptop has 8 GB RAM and two physical / four logical CPU cores.

| Profile | Requests / target | Failures | p50 | p95 | p99 | Observed API process-tree RSS |
|---|---|---:|---:|---:|---:|---:|
| credit_card | 600 / 10 requests per second for 60 seconds | 0 | 31.7 ms | 82.2 ms | 283.7 ms | 157.2 MB |
| banksim | 600 / 10 requests per second for 60 seconds | 0 | 60.8 ms | 477.8 ms | 1363.4 ms | 300.1 MB |

[Recorded traffic evidence](traffic-results.json) includes actual throughput and measurement scope. Latency includes the client concurrency queue, and memory is sampled once per second. Other applications were running; these measurements do not establish cloud capacity. Local audit history contains verification/demo traffic and never feeds the frozen quality metrics.

The first traffic attempt exposed session-wide serialization of independent card requests and nested prediction threading. Request-specific PostgreSQL locks now preserve retry safety while allowing independent card requests to run concurrently. BankSim retains its history-session lock. Generated directories are excluded from PyCharm indexing.

Final local checks: 40 backend tests against PostgreSQL, six real-browser workflows, four Sites proxy tests, both executed notebooks, a successful production frontend build, zero known npm audit findings, and official Compose validation for development and production. Docker image builds remain unverified locally because no Docker engine is available.
