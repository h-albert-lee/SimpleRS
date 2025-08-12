# Ranking System Guide

## Overview
This document explains the ranking logic used in the SimpleRS API service.

The ranking pipeline consists of three stages:
1. **Candidate Loading** – fetch initial items and their raw scores from stores such as MongoDB.
2. **Pre-filter Rules** – remove items that should not be shown to the user (e.g., already seen items).
3. **Post-ranking Rules** – adjust scores with various signals and sort the final list.

If no candidates are returned from the candidate store, the service falls back to curated items stored in `curation_hist` or `curation` collections.

## Rule Architecture
Rules are organized as modular classes so new rules can be plugged in easily.

### Pre-filter Rules
These rules run before scoring and drop items:
- `ExcludeSeenItemsRule`: filters out content the user has already interacted with.

### Post-ranking Rules
These rules modify scores after pre-filtering:
- `HeuristicScoreRule`: blends market cap, recency, and random signals. Each signal is normalized to 0–1 and combined with equal weights by default.
- `BoostUserStocksRule`: boosts items related to user owned or interested stocks.
- `BoostTopReturnStockRule`: emphasizes items about high-return stocks.
- `AddScoreNoiseRule`: adds small noise to break ties.

All rules implement a common interface defined under `api/rules` so they can be executed sequentially.

## Heuristic Scoring Details
`HeuristicScoreRule` computes three signals for every candidate:
1. **Market Cap** – higher market capitalization receives higher score.
2. **Recency** – recently created content is favored.
3. **Random** – random value to provide slight variety.

Each signal is standardized and scaled between 0 and 1. The final heuristic score is the sum of the signals (weighted equally by default). This score is added to the original candidate score with a configurable weight.

## Configuration
Weights for heuristic and original scores can be tuned through the service configuration:
```yaml
ranking:
  heuristic_weight: 1.0
  raw_score_weight: 1.0
```

## Extending the Ranking System
To add a new rule:
1. Create a class in `api/rules/pre_filter_rules.py` or `api/rules/post_reorder_rules.py` implementing the base rule interface.
2. Register the rule in `api/rules/__init__.py`.
3. Update tests under `tests/` to cover the new rule.
4. Update this document if the rule affects ranking behavior.

## API Endpoint
The ranking service is exposed via FastAPI:
```
GET /recommendations/user/{cust_no}
```
It returns a list of items with their final scores after all rules are applied.

## Fallback Behavior
If candidate generation fails or returns nothing, the service retrieves items from curated collections (`curation_hist` or `curation`) and applies the same filtering and ranking rules to ensure consistent responses.

## Testing
Run unit tests to validate ranking logic:
```bash
pytest
```
