# Workstream E — pre-registration: efficiency-first end-to-end evaluation of the protocol fixes

Status: **FROZEN 2026-11-05 07:14 UTC** together with the code manifest `PREREG_E_manifest.txt` (§9; its digest is recorded
in progress.md and the team PROGRESS.md, not in this file). Drafted 2026-11-04; pre-freeze changes listed in §8.
Blinding: no outcome analysis of any confirmatory run before the population runs are complete AND not before D's
numeric predictions are timestamped (2026-11-06 00:00 UTC); before that only operational QA (error rates, throughput,
replay fidelity, event logging, pooled completion counts).
Every deviation from this document is logged in `PREREG_DEVIATIONS.md` (date, what, why, expected impact).

## 1. Question
Do the two shipped protocol fixes — history **quarantine** and **intent-preserving decoding (IPD)** — reduce the
protocol waste of Gemma-4 agents in the official competition harness, end to end, and does the onset of a malformed
call causally change the rest of the episode under each fix?

## 2. Arms (proxy cfgs, `proxy/configs.json`)
| arm | what changes vs `base` |
|---|---|
| `base` | none: the proxy renders, generates and parses exactly like vLLM 0.19.1's chat endpoint (prompt tokens identical on 64/64 real contexts); 4,096-token thinking budget emulated |
| `quar` | malformed historical calls re-rendered (recovered from the raw emission when available, else sanitized) + tool response replaced by a structured `MalformedToolCall` error (frozen renderer `export/quarantine_renderer.py`); a historical call whose raw emission is STRICTLY valid (B's guard) is never rewritten |
| `ipd` | IPD(i+) = **verify-then-repair**, workstream B's reference algorithm: the turn is generated uninterrupted; every call is checked with B's strict guard (vendored byte-identical, `proxy/vendor_b_gemma_protocol.py`); the first call that is not strictly valid is rolled back to its left-most repairable site (B's `first_violation`, rules closer + opener, whitespace-tolerant, declared keys only), `<|"|>` inserted (closer cut by B's noisy-channel rule with the frozen prior `configs/channel_prior.json`), generation resumed; ≤ 4 rounds per call, ≤ 8 per turn; guarded post-hoc fallback |
| `fullp` (= full′) | `quar` + `ipd`. **No argument-order patch** (the order patch is an ablation, cfg `order`, not part of this registration) |

**P1 (byte identity):** no fix ever alters a STRICTLY valid call (B's guard): such calls are delivered byte-identical and are never rewritten in the history (verified on the 229,412 valid QuoteStorm calls, incl. 1,200 adversarial literals, through the real request path; `acceptance/`). **Registered delivery policy:** a call that is still not strictly valid after IPD (no repairable site, rounds exhausted, site inside an undeclared key) is delivered as vLLM 0.19.1's lenient parser reads it, unless the post-hoc fallback recovers a schema-valid call from its raw text. B's opener rule may regenerate calls that are strictly invalid but that vLLM reads correctly (e.g. a bare string value). Verification runs whenever a turn ends: EOS, a user stop string, or the length cap (the harness and the client send no stop strings).

## 3. Design
**Harness.** Official `swegemma 0.2.11` (ADK LlmAgent + AgentTool sub-agent, ToolErrorPlugin, 3 nudges, compaction at
14,336 tokens), Docker sandbox (4 GB, no network; rootless: no CPU quota), per-task wheel sets, Phase-2 verification
with the task's tests. Submission `subs/sample_noadapter*` = the official sample submission without LoRA adapters
(T=0.2, top_p 0.95, max_output_tokens 16,384, thinking budget 4,096, include_thoughts), budgets: population 50 tool
calls / 100 turns / 120 min wall cap (non-binding safety cap), branches 40 tool calls.

**Tasks.** The 113 public tasks that are gradable in our sandbox (gold patch resolves AND empty patch does not;
`configs/eligible_113.txt`, from `runs/gold_routed/gold.jsonl`). Denominator for every resolve rate.

**(a) Population runs.** Each (task, model, replicate) is run under `base` and `fullp`:
| model | replicates | episodes | backend |
|---|---|---|---|
| gemma-4-31b-it-qat-w4a16-ct | 2 | 452 | :8300 (lane 1, right after the freeze, Nov 5) + :8302 (lane 2, from ~11:30–12:30 Nov 5) |
| gemma-4-12b-it-qat-w4a16-ct | 1 | 226 | :8301 |
| gemma-4-e4b-it-qat-w4a16-ct | 1 | 226 | :8311 |
Common random numbers: every generation request carries seed = sha1(`<campaign salt>:<task>:<request index in the
session>`), identical across the two arms of a replicate (vLLM is not batch-invariant, so trajectories may still
diverge without an intervention; CRN only reduces variance). Arms of a replicate run concurrently, same task order.

**(b) Branch-at-onset (closed loop).** Source episodes = the `base` episodes of (a) (replicate 1; for 31B also
replicate 2). Replay prefix = all requests up to and including the root agent's first `edit_file` turn; the proxy
returns the logged responses (same ids, same reported usage) and the harness re-executes every tool call in a fresh
sandbox. **Fidelity**: every replayed request must reproduce the logged tool-result status, error type, normalised
output hash and message count; a branch with any mismatch before the onset is excluded (count reported). **Onset**:
natural if that call was emitted malformed; otherwise injected with workstream A's P1 corruption (first of
new_string/old_string in emitted key order closed with a backtick; the vLLM 0.19.1 parse is delivered; the raw text is
kept so `quar` can recover it). From the onset on, the episode continues live under {`base`, `quar`, `ipd`, `fullp`}
with common per-request seeds sha1(`branch_id:i`), cap 40 tool calls. Branch points: 31B 150, 12B 100, E4B 100;
natural onsets first, then injected (seeded sample, seed 20261105). Plans: `analysis/build_branch_plan.py`.

## 4. Endpoints (computed by `analysis/prereg_analysis.py`, frozen with the code)
Unit = one episode (task attempt). All tool calls of the session count (root agent + AgentTool sub-agent). ADK
compaction calls (no tools) are not agent turns. "Malformed" = SYNTHESIS §5 criterion on the call the harness
receives: unknown tool, missing required key, undeclared key, a string value containing `<look-alike closer>,<declared
key>:` or ending in `,<declared key>:`, or a special token inside a value.

**Co-primary (family F4; 31B population; Holm over the two):**
- **Y1 delivered-malformed calls per episode** — number of tool calls delivered malformed.
- **Y2 wasted calls per episode** — tool calls that were delivered malformed OR whose tool result is a protocol error
  (`MissingParameters`, `UnexpectedArgument`, `TypeError`, `ValueError`, `MalformedToolCall`, `UnknownTool`,
  `ValidationError`, `JSONDecodeError`), each call counted once, PLUS turns whose output contained tool-call syntax that
  produced no delivered call (unparsed call text, including call text without the `<|tool_call>` opener).
Contrast: `fullp − base`, paired by task (31B: the two replicates of a task are averaged within arm first). Estimand:
mean over the 113 tasks of the per-task difference (risk difference first), and the ratio of arm means (second).
Inference: task-cluster bootstrap, B = 10,000, percentile 95% CI; two-sided p from the bootstrap (proportion of
resamples on the other side of 0, ×2); Holm over {Y1, Y2} at α = 0.05.
**Success (pre-stated):** `fullp` reduces Y1 by ≥ 70% (ratio of means ≤ 0.30) with the CI of the difference excluding 0.

**Secondary (reported for every model; no multiplicity claim):**
1. generated tokens per episode;
2. emulated 4×L4 wall-clock per episode = Σ over LLM calls of [0.21 s + uncached prompt tokens / 1,660 + generated
   tokens / 35.7] + measured tool execution time, with uncached = max(0, prompt − (previous prompt + previous generated))
   within the session (constants measured by the main track on 4×L4);
3. stuck episodes: ≥ 5 consecutive delivered-malformed calls (Wilson CI; paired difference by McNemar);
4. time to the first applied edit (agent turns, and seconds) until the first edit_file/write_file with status ok;
   episodes without one are censored (fraction reaching it reported);
5. resolve rate (denominator 113 per arm and replicate): McNemar exact test and the paired difference with a 95% CI;
   non-inferiority of `fullp` at margin −3 pp (lower CI bound > −0.03). **Declared underpowered** (MDE ≈ 6–8 pp);
6. per-arm onset hazard P(slip | no earlier slip) and post-onset rate, and the stuck/killed counts;
7. from the branches: post-onset delivered-malformed calls per branch episode for `quar`, `ipd`, `fullp` vs `base`
   (paired by branch point, bootstrap over branch points); **success (pre-stated, 31B):** `quar` and `ipd` each reduce
   it by ≥ 50%; causal q_r = P(malformed | r malformed calls already in the history) for r ≥ 2 by arm; conditional
   resolve (MDE ≈ 10 pp, 1 seed);
8. D's predictions P-a, P-b, P-c, evaluated as written by D (the 12B/E4B "crossover" is reported against P-a whichever
   way it goes).
Exploratory (labelled as such): the no-nudge client, the order ablation, the 12B/E4B pilots `p12a`/`p4a`.

## 5. n and power (from UPGRADE_PLAN §P0-E)
31B population, 226 pairs: base ≈ 1.2 malformed calls/episode (SD ≈ 3) → > 90% power for a −50% change in Y1.
Resolve: MDE ≈ 6–8 pp (stated, not claimed). Branches: post-onset malformed calls under base ≈ 5–12 → power > 99% for
−50%; conditional resolve MDE ≈ 10 pp (1 seed), ≈ 8 pp (2 seeds).

## 6. Exclusions and failures (decided now)
- Infrastructure failures (proxy 5xx, backend errors after retries, sandbox setup errors, harness exceptions not
  caused by model output) → the episode is re-run once with the same seeds; if it fails again it is excluded from BOTH
  arms of that pair (pairwise deletion); counts reported.
- Context-length errors, budget exhaustion, nudge exhaustion and malformed output are outcomes, not failures.
- Branch points with a replay-fidelity mismatch before the onset are excluded (count reported).
- No episode is excluded on the basis of its outcome.

## 7. Operational rules
≤ 14 concurrent sandboxes for E (PI, Nov 5); per-server request caps as set by the PI; no `prompt_logprobs` anywhere; one proxy per
campaign, never restarted mid-campaign; each run writes its own directory; aborted launches are archived as
`runs/invalid_*` and never analysed.

## 8. What was seen before this registration
The exploratory 12B/E4B pilots (`p12a`, `p4a`, launched 2026-11-04 11:08/11:11 UTC with the earlier `full` =
order+quar+ipd) were used for timing and operational QA only. Disclosure of what WAS seen from them: two n ≤ 2 smoke
checks of the metrics script (11:20–11:30 UTC, before the blinding instruction), and — inadvertently, AFTER the
instruction — one automatic progress summary at 12:02 UTC that printed per-arm resolved/completed counts
(p12a H-base 0/1, H-full 0/1, C-base 0/0, C-full 2/6; p4a H-base 0/4, H-full 0/4, C-base 0/5, C-full 3/8). The
monitor was changed to pooled counts immediately; no other pilot outcome was looked at. Component-level
validation on 20 real slip contexts (E4B, one turn each; results.json `ipd_live_exercise`) was seen and motivated the
opener rule; it is not an endpoint here.

### Pre-freeze changes (code changed before the freeze; logged here and in PREREG_DEVIATIONS.md)
- 2026-11-04 ~10:30–12:10 UTC: `fullp` defined (no order patch); renderer exported; branch mode; CRN seeds.
- 2026-11-04 18:40–19:30 UTC, after workstream B's proxy-equivalence checks on the candidate
  (e2e_proxy.py sha 0c2a5278…, archived in `archive/candidate_0c2a5278/`):
  1. **P1 violation fixed (redesign of IPD).** B found the decode-time IPD (stop strings + opener confirmation + cut
     before the call was complete) changed 184/1,200 ADVERSARIAL valid QuoteStorm calls (0/228,212 natural), and the
     post-hoc path changed 94 more (the SYNTHESIS criterion flags a literal "`,old_string:" inside a valid value and
     `intent_parse_args` split it): 278/1,200 = 23.2% [20.9, 25.6]. IPD is now B's verify-then-repair with B's strict
     guard in front of EVERY path (decode, post-hoc, quarantine).
  2. Whitespace variants of the closer slip (`` `, new_string: ``; 1/104 gate slips, 50/3,209 base-31B edit slips)
     are now handled (B's site finder; whitespace-tolerant post-hoc parse).
  3. Sites inside arguments not declared in the schema are never repaired.
  4. Separator drift (`key="..."`) is no longer repaired by default (not in B's (i+); opt-in rule).
  5. B's opener rule (strict guard decides) replaces the earlier opener rule that required vLLM to read the call
     malformed.
  6. The post-hoc / quarantine parser accepts whitespace variants only where a value of the key's type opens next
     (B's site rule); renderer byte-identical to the version A used (13e28567…) on 12,208 A-style P1 cases, and A
     verified identical prompts/actions on its 1,476 discovery renders.
  None of these changes affects cfg `base` (rendering, generation and parsing unchanged; no fix runs).
  The registered endpoints, arms, design and analysis are unchanged.
  **Proxy freeze candidate declared 2026-11-04 19:13:11 UTC** (`acceptance/FREEZE_CANDIDATE.txt`: sha256 of
  proxy/e2e_proxy.py, proxy/gemma_protocol.py, proxy/vendor_b_gemma_protocol.py, proxy/configs.json,
  export/quarantine_renderer.py, configs/channel_prior.json). PASS: B's P1 acceptance test on exactly these files,
  `ipd` and `fullp` 0/229,412 valid calls changed (adversarial 0/1,200, natural 0/228,212).

- Schedule shift: the freeze (planned 2026-11-05 12:00 UTC) was held for the GPU maintenance outage
  (2026-11-05 00:30 UTC to the user's green light ~07:00 UTC); it is done after the 31B smoke on the proxy freeze
  candidate and BEFORE any population launch.

## 9. Code freeze
Manifest: `PREREG_E_manifest.txt` (sha256 of every file under proxy/, export/, harness/, client/, analysis/, configs/,
tests/, run_*.sh) and its digest, written by `tools_freeze.sh` at the freeze. Branch mode: its own digest before
2026-11-06 12:00 if changed after the freeze.
