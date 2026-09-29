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

## What the engine says about the score

- `select.predictions_in_sample`: 'churned' is predicted with its own value held out, but the row being scored is still part of the population the prediction is read from, so this confidence is in-sample and reads better than held-out accuracy. Use '_evaluate' for an unbiased estimate.

ok

## The unbiased estimate the warning points at

- accuracy: 78.6% on 600 test rows (2400 train, n=551)
- base rate: 79.1%
- gain over base: -0.5pp

ok
ok

## The leak this page exists to avoid, and its real cause

The same statement, against rows whose label IS present. The engine holds `churned` out; what it still sees is `reordered`.

- I00001 (temperate/active): churned=false, reordered=true -> false at p=0.9808
- I00002 (hot/liquid): churned=false, reordered=true -> false at p=0.9808
- I00004 (arctic/active): churned=false, reordered=true -> false at p=0.9808
- I00005 (temperate/liquid): churned=false, reordered=true -> false at p=0.9808
- I00006 (hot/active): churned=true, reordered=false -> true at p=0.9808
- I00007 (hot/passive): churned=false, reordered=true -> false at p=0.9808

ok
ok
