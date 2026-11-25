# Target extensions and profit protection

November 18, 2026. Outcome Review / Learning owns this historical sensitivity
analysis under Intraday Profit Protection and Overnight Hold Decisions.

## Findings

The question is whether information available before a target fills can justify
raising the target and protecting gains. Later price peaks motivated the test,
but are never used to decide whether a historical rule activates.

The actual-account bridge from September 25 close through November 18 reconciles
to +$6,725.59 after fees. The study contains 214 new long-entry groups. Thirty
have unfinished five-subsequent-session windows and twelve lack initial levels
or a contemporaneous endpoint. There are 172 replayable mature groups, 61
passing the broad path standard and zero passing the strict standard. The
actual-exit comparison has 60 comparable groups across eleven entry dates,
including winners and losers, with actual net profit of $1,668.32. These are
coverage-selected research cohorts, not the entire account.

The table shows illustrative settings with a 60-second replacement delay,
$0.01 adverse slippage per share and $0.70 exit fees per contract. Target
extension means increasing the entry-to-initial-target distance by 25%.

| Candidate | Activated groups | Actual net on cohort | Modeled candidate net | Difference | Extra gains / gains surrendered |
|---|---:|---:|---:|---:|---:|
| Extend at 75% of planned gain | 9 | $1,668.32 | $965.86 | -$702.46 | $307.49 / $1,009.95 |
| Extend at 75%, ratchet stop to retain 75% of gains | 9 | $1,668.32 | $905.11 | -$763.21 | $63.97 / $827.18 |
| Extend at 90%, ratchet stop to retain 75% of gains | 2 | $1,668.32 | $1,496.28 | -$172.04 | $0.00 / $172.04 |

The extension-only example added 4.75 calendar holding hours per cohort group,
or approximately 31.67 per activated group. The paired examples averaged
approximately 1.24 and 1.14 additional minutes per cohort group respectively;
positive and negative holding-time changes offset. None of these three examples
uses a terminal valuation in place of a modeled sale.

All 32 candidates were tested across four execution settings. None improved the
broad actual-exit comparison in any setting. The subset with recovered broker
brackets and no ambiguous changes has 41 comparable groups. Two protection-only
variants improved it by $6.66 with $0.01 slippage; none improved it at $0.05.
The rising-bid condition did not establish a durable advantage. The paired 75%
example underperformed in both earlier and later entry-date periods. Results
do not establish that target revision is intrinsically harmful or that these
parameters are optimal. They do show that later observed upside alone does not
justify adopting these particular extension rules.

## Design and interpretation

- The grid tests activation at 75%/90% of initial planned gain, target-distance
  multiples 1.25/1.50, and profit retention 50%/75%. Extension-only,
  protection-only and paired variants isolate contributions.
- A separate condition requires rising option bids over three to five minutes
  and a spread no greater than 10% of bid. It uses only quotes already known.
  This first study tests option-price conditions; it does not reconstruct a
  fresh underlying-stock thesis or calibrated confidence forecast intraday.
- The protected stop ratchets upward with observed gains, allowing at least
  two spreads or the last six sampled bids' range. It applies on later samples.
- Execution sensitivities are zero/60-second latency, $0.01/$0.05 slippage and
  full size/one contract per quote. Existing sampled stops/targets take priority
  during replacement. Position size at the quote remains unverified.
- Every policy shares actual entries, quantities and a common endpoint one
  minute before the fifth subsequent session closes. Entry fees are actual.
  A replacement itself adds no modeled transaction fee; each sale has an exit
  fee. Cash recycling and hypothetical replacement investments receive no gain.
- Broad paths require at least 80% of market minutes, gaps no longer than 30
  minutes and both endpoints within five minutes. Strict paths require 95%,
  gaps of at most five minutes and endpoints within two minutes. Missing quotes
  can hide crossings. Four additional corrupt bundles are retained in provenance.
- The full modeled control still differs materially from actual exits. The
  main actual comparison therefore starts from a broker-confirmed intact lot,
  requires candidate activation before its first actual sale, and preserves
  actual results when no intervention occurs. It includes only simultaneous
  completed actual exits within the common window. Once a rule activates, it
  supersedes later manual decisions. This estimates a specific intervention,
  including the decisions it displaces, rather than a full funded portfolio.
- The known sampled-bid versus broker-stop-trigger uncertainty continues after
  intervention. These are modeled exit comparisons, not proven broker fills.
- Early paths end by October 21. Later entries start after October 21.
  Cross-boundary groups are excluded from the split. History was previously
  inspected, so this is chronological stability evidence, not an untouched test.

GOOGL's November 13 entry and November 16 exit are outside the mature primary
cohort at the November 18 cutoff. Its initial broker bracket was $8.70 stop /
$15.75 target; the $13.15 sale was a later separate order placed November 16.
The recommendation's initial target was $15.73. A later $16.95 sampled bid on
November 18 supports reviewing target reductions as well as extensions.
Determining why the later order used $13.15 requires its daily guidance lineage.

Validation passed all 295 fixture tests, including ten target-extension tests,
Python compilation and all paired dollar identities. The new code and
documentation remain local pending a requested commit and push.

## Reproduction and next decision

Tool `src/target_extension_review.py` uses the existing broker attribution,
order-history parser and checksum-verified quote projection. Outputs are
`reports/target_extension_20261118/review.md` and `review.json`, with all
candidate results, actual comparisons, per-trade fills and outlier sensitivity.
The extracted quote cache is local under the chat's
`outputs/target-extension-20261118/quotes.json`, with checksum and source manifest.
Pass `--statements`, `--journal`, `--archive`, `--projection`, `--quote-cache`,
`--beginning`, `--ending` and a new `--output` path to reproduce it. Existing
report paths are refused. No external provider calls are required.

Use this evidence when discussing a prospective candidate. First distinguish
initial targets from subsequent reductions and attribute those decisions to
their contemporaneous guidance. Any richer thesis-based extension would need
its own observable inputs and paired test. Production and frozen experiment
policies were not changed. Focused tests cover latency, causal signal checks,
stop ratchets, partial fills and broker-anchored intervention timing.
