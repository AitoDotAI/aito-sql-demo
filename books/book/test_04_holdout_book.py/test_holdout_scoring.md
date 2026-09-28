# Scoring installs the engine was never told about

instance: `https://shared.aito.ai/db/aito-sql-demo`


## The cohort

- held-out installs scored: 240
- of which actually churned: 43 (17.9%)

ok
ok

## The score

- accuracy: 78.8%
- base rate (always predict the majority): 82.1%
- top-decile lift: x2.56 (11/24 churned, 45.8%)
- AUC: 0.645

ok
ok
ok

## Calibration

- p in [0%, 10%): n=125, predicted 4.4%, actually churned 11.2%
- p in [10%, 20%): n=47, predicted 14.5%, actually churned 14.9%
- p in [20%, 35%): n=21, predicted 26.1%, actually churned 19.0%
- p in [35%, 60%): n=22, predicted 46.5%, actually churned 27.3%
- p in [60%, 100%): n=25, predicted 79.7%, actually churned 48.0%

ok

## The leak this page exists to avoid

The same statement, against rows whose label IS present.

- I00001: label=false, top prediction=false at p=0.9808
- I00002: label=false, top prediction=false at p=0.9808
- I00004: label=false, top prediction=false at p=0.9808
- I00005: label=false, top prediction=false at p=0.9808
- I00006: label=true, top prediction=true at p=0.9808
- I00007: label=false, top prediction=false at p=0.9808

ok
ok
