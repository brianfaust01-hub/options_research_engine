# Preserving winners while avoiding losers

Read-only review through the November 5, 2026 broker statement. Detailed output:
`reports/trade_filter_review_20261106_final/review.md` and `review.json`.
Reproduce using `src/trade_filter_review.py` with the post-September broker
attribution JSON as `--attribution` and a new `--output` directory.

The 156 fully closed long-option entry groups earned $4,067.52 after allocated
fees. We tested simple entry filters against actual dollars, counting both
losses avoided and winning profits sacrificed. Earlier closed outcomes selected
the candidate; later entries checked whether the benefit carried forward.
Eight positions crossing the training boundary were purged and three still-open
groups were excluded. This is a retrospective screen, not a new forward trial.

## Findings

- The training-selected IV-at-or-below-40% filter reduced later profit by
  $169.73: $561.29 of losses avoided versus $731.02 of profits forgone. It
  excluded profitable APH and AVGO trades. Its earlier benefit did not repeat.
- An absolute delta floor of 0.35 improved later profit by $153.57 and retained
  94.4% of winning dollars, but the benefit becomes negative $0.38 when the
  largest avoided loss is removed. At one contract per group the benefit was
  only $2.30. This is a fragile research lead, not an established edge.
- Higher research and execution score cutoffs reduced later profits. Better
  stock-direction statistics do not automatically imply better option returns.
- None of these findings justifies a new production filter. Existing frozen
  shadows continue unchanged; these screens do not replace their results.

## Next evidence

Continue measuring actual option dollars alongside signal characteristics and
the forward shadows. Revisit candidate filters with more closed trades and
market conditions, preserving the full cost of missed winners. Do not choose
a new rule merely because it looks best in this holdout table. Recommendation
features are historical recommendation-time measurements and broker links are
contract/time inferences, not confirmed broker recommendation IDs. No historical
first-hour or VIX observations were invented.
