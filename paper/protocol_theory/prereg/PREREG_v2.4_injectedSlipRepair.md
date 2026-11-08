# PREREG_v2.4 (addendum): injected-slip repair battery on public-corpus states, gold intent known by construction (workstream D)

* **Written:** 2026-11-05, starting 11:10 UTC. **Frozen** when its sha256 is written to `PROGRESS.md`.
  Deviations go to `PREREG_DEVIATIONS.md` (this folder).
* **Blindness.** No battery output exists (B builds it after the freeze). D has seen B's discovery results and the
  PREREG_v2 confirmatory summary (13 natural slips; IPD reduction CI [66.7, 98.6]; C16 not estimable; T1 tied IPD). D has not
  read `<host-path>/work` or `/harness`.
* **Relation to earlier registrations.** This is an addendum to PREREG_v2 (sha256 5da75e61…); conventions follow its §3. B
  implements the arms with its existing frozen code (`experiments/intent_decoding/arms.py`, `intent_decode.py`,
  `gemma_protocol.py`) and logs their hashes before the run. Arm semantics below follow that code.

## 1. Construction
**States.** P's S1 episodes; **strictly valid** `edit_file` calls whose tool result was success.
* Rank by sha256(`"PREREG_v2.4|20261105|" + episode_id + "|" + str(turn_index)`), ascending.
* Accept in rank order with at most 2 calls per episode, no repository above 40% of the accepted calls, and prompt ≤ 24,000
  tokens.
* **Target 600.**

**Closer strata** (design choice: **four equal strata**, assigned by accepted rank mod 4):

| stratum | injected closer | n | why |
|---|---|---|---|
| BT | backtick `` ` `` | 150 | the dominant natural closer |
| DQ | double quote `"` | 150 | |
| EQ | escaped quote `\"` | 150 | composite: the cut is ambiguous when the content ends in `\` or `"` |
| TB | triple backtick ```` ``` ```` | 150 | composite: the cut is ambiguous when the content ends in backticks |

The equal strata give power on composite closers, where discovery showed IPD's edge. **Headline estimates** reweight the
strata to the discovery base-31B closer channel: BT 0.865, DQ 0.082, EQ 0.037, TB 0.016 (the composite share goes to TB).
Per-stratum results are always reported beside them.

**Slip injection.**
* Teacher-force the model's own logged call (thought and call text) up to the closing `<|"|>` of `new_string`.
* Replace that delimiter with the stratum's closer.
* Let the 31B **QAT-ct** continue live: thinking on, P's sampling (T = 1.0, top-p 0.95, top-k 64), one seed per state shared
  by all arms that sample.
* **Gold intent** = the original logged call.

**Arms on the identical slipped prefix** (B's semantics):

| arm | behaviour |
|---|---|
| lenient | vLLM 0.19.1's gemma4 parser on the live emission |
| fail-loud | C's/B's strict reference parser + schema: reject → loud |
| T1 | text-only repair of the live emission; the post-slip continuation is kept |
| IPD (i+) | decode-time rollback and resume, active during the live continuation: noisy-channel cut, true delimiter forced, generation resumed |
| grammar-CD | longest grammatical prefix + the grammar's forced legal continuation, then free generation (≤ 6 rounds) |
| retry×2 | if the live emission is strictly invalid, resample the whole call at T = 1.0 (new seeds), at most 2 tries; else deliver it; loud if both fail |
| greedy | the call re-decoded at T = 0 from the call head (B's `arm_greedy`) |

## 2. Outcomes (judged against gold; mutually exclusive)
| outcome | definition |
|---|---|
| **exact intent** | the delivered call has every argument byte-equal to gold |
| **silent corruption** | the delivered call is strictly valid, differs from gold, and carries slip damage: look-alike residue such as `ℓ,<key>:` or a stray injected closer, a lost or misassigned argument, or a `new_string` that differs from gold by look-alike characters at the cut |
| **other valid** | strictly valid, ≠ gold, no slip damage (e.g. a resampled, different edit) |
| **delivered-malformed** | the delivered call is malformed under A's/E's judge |
| **loud** | no call delivered, or an explicit error surfaced |

**Secondary outcomes:**
* `new_string` exact (the slipped argument recovered byte-exactly), isolating cut quality from live variation in later
  arguments;
* old_string exact;
* tokens and latency per arm.

**Injection mechanics** (descriptive, from the live emission before any arm acts):
* *slip pattern*: the look-alike is followed by `,<declared key>:` or by the call end;
* *closer doubling*: `<|"|>` immediately follows the injected closer;
* *content continuation*: the model keeps writing `new_string` content.

Doubling and content continuation yield strictly valid texts carrying the injected characters. **No method can detect
them** (theory.md Thm 1.3, S2).

**Estimands.**
* **ITT:** over all 600 states.
* **Detectable subset (primary for repair quality):** states whose lenient-arm live emission is strictly invalid, i.e. a
  detectable slip.
* **Pairing and CIs:** every comparison is paired by state; CIs use an episode-cluster bootstrap (B ≥ 2,000, percentile)
  and Wilson for single rates.

## 3. Predictions (D's 80% prediction intervals; discovery = B's 519 natural slips with gold, 31B, June)
**Injection mechanics (ITT, reweighted):**
* slip pattern 0.65 [0.30, 0.90];
* closer doubling 0.25 [0.05, 0.60];
* content continuation 0.10 [0.02, 0.30];
* doubling likelier for BT and DQ than for EQ and TB.

**Arm outcomes on the detectable subset** (discovery value in parentheses):

| arm | exact intent | silent corruption | delivered-malformed | loud |
|---|---|---|---|---|
| IPD (i+) | **0.90 [0.75, 0.98]** (0.977) | ≤ 0.02 | ≤ 0.01 | ≤ 0.05 |
| T1 | 0.88 [0.72, 0.97] (0.944) | ≤ 0.05 | 0 | ≤ 0.05 |
| lenient | ≤ 0.02 | 0.10 [0.02, 0.30] | **0.88 [0.65, 0.98]** | 0 |
| fail-loud | 0 | 0 | 0 | **1.00** by construction |
| grammar-CD | ≤ 0.05 | **0.90 [0.70, 0.99]** (0.97–1.00) | ≤ 0.10 | 0 |
| retry×2 (T = 1.0) | 0.20 [0.05, 0.45] (0.123) | — | 0 | 0.10 [0.02, 0.30] |
| greedy | 0.35 [0.15, 0.60] (0.079 on natural slips; injected states were valid originally) | — | 0.05 [0, 0.15] | — |

* retry×2: "other valid" takes the rest.
* greedy: "other valid" takes the rest.
* The exact-intent ceiling for IPD and T1 is P(the live `old_string` equals gold) at T = 1.0, predicted 0.92 [0.80, 0.98].

**On ITT:** exact intent for IPD and T1 is predicted at about 0.60 [0.30, 0.88] (the undetectable doubling and continuation
cases cost every arm equally). ITT silent corruption is about 0.30 for every parser arm, because the doubling cases are
silent.

**IPD vs T1 (the explicit question):**

| scope | predicted exact-intent difference |
|---|---|
| BT stratum | 0 pp [−2, +2] |
| composite strata (EQ + TB) | **+6 pp [0, +20]**: T1's text-only cut fails when the content ends in look-alike characters; IPD's model-scored cut does not (discovery: T1 fails exactly the 10 composite runs, IPD 10/10) |
| reweighted headline | **+1 pp [−1, +4]** |

`new_string`-exact differences are predicted to equal the exact-intent differences (both arms keep or regenerate the same
later arguments, apart from sampling noise).

## 4. Decision rules
**Per-claim rules** (detectable subset, reweighted):

| # | claim | REPLICATES | ATTENUATED | FAILS |
|---|---|---|---|---|
| R1 | IPD recovers intent | exact intent ≥ 0.85 and CI_lo ≥ 0.75 | exact ≥ 0.60, but R1's replication rule fails | otherwise |
| R2 | IPD never delivers malformed | ≤ 1% with Wilson upper ≤ 3% | — | otherwise |
| R3 | IPD causes no silent corruption on detectable slips | ≤ 2% with Wilson upper ≤ 5% | ≤ 5% | otherwise |
| R4 | grammar-CD corrupts silently | silent ≥ 0.80 with CI_lo ≥ 0.60 | silent ≥ 0.50 | otherwise |
| R5 | lenient delivers malformed or corrupted calls | delivered-malformed + silent ≥ 0.80 | ≥ 0.50 | otherwise |
| R6 | fail-loud is loud on every detectable slip | 100% | — | otherwise (that would be a defect, with case IDs) |
| R7 | retry×2 rarely recovers intent | exact ≤ 0.35 | — | exact > 0.35 |
| R8 | greedy rarely recovers intent | exact ≤ 0.60 | — | exact > 0.60 |

**Holm family F-R (primary; 12 one-sided paired tests, reweighted, detectable subset):** IPD vs each of {lenient, fail-loud,
T1, grammar-CD, retry×2, greedy} on
* (a) exact intent (H: IPD > baseline), and
* (b) silent corruption (H: IPD < baseline).

Bootstrap p = (1 + #{Δ* ≤ 0})/(B + 1), Holm-adjusted over the 12 tests.

**The explicit question, "does IPD beat T1 on exact intent?":**
* **IPD BEATS T1** iff the reweighted IPD − T1 exact-intent contrast has Holm-adjusted p < 0.05.
* **TIE** iff its 95% CI lies within [−2, +2] pp.
* **INCONCLUSIVE** otherwise.
* Secondary (unadjusted, reported as such): "IPD beats T1 on composite closers" iff the pooled EQ + TB contrast has
  CI_lo > 0; and the same on `new_string` exact.

**Reporting:**
* ITT and detectable-subset tables side by side, per stratum and reweighted;
* the injection-mechanics shares, with the undetectable cases highlighted as a limit no repair can overcome;
* tokens and latency per arm.

## 5. Notes
* The battery measures repair quality where intent is known. It does **not** estimate natural slip rates (PREREG_v2 C12
  does that).
* Opener drift is not injected here. The discovery IPD-vs-T1 edge from opener drift is out of scope, so any claim about it
  rests on discovery only.
