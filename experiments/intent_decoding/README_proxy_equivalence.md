
## 8. Proxy equivalence: the SHIPPED proxy vs the reference decoder (PI job, 2026-11-04 18:15 UTC)
Workstream E ships IPD inside its OpenAI-compatible proxy (`experiments/endtoend/proxy/e2e_proxy.py`, cfgs `ipd`
and `fullp`). E's implementation is a **decode-time** variant. It stops generation at look-alike-closer stop
strings (`<closer>[\n],<key>:`, `<closer>[\n]}<tool_call|>`), confirms the slip with one sampled token (the opener of
the next value), and picks the cut with B's noisy-channel rule (pinned copy of the closer prior). It then inserts
`<|"|>`, keeps the model's `,KEY:` and resumes. A post-hoc text-only repair (`intent_parse_args`) handles calls that
are still malformed. B's reference is **post hoc**: generate the whole call, return it unchanged if it is strictly
valid, and otherwise roll back to the first slip site. All numbers: `out/proxy_equivalence.json`; code:
`proxy_equivalence.py`. E's code is used read-only from a hash-verified copy (`proxy_vendor/VENDOR_MANIFEST.txt`;
pre-fix `e2e_proxy.py` sha256 `0c2a5278…`).

### 8.1 Identical generations, CPU (pre-fix code)
The proxy's logic was replayed on the 595 identical gate generations of §4.2. The logged next token stands in for
the proxy's confirmation sample. The cut decision uses B's logged likelihoods.
- **Valid calls:** 480/480 pass byte-identical.
- **Closer slips (104):**
  - 100 are cut at decode time. On all 100 the slip site, candidate cut set, closer-prior values and chosen cut
    agree with B.
  - 2 slips with no visible closer are repaired post hoc, with arguments byte-identical to B's IPD output.
  - 1 unterminated last argument is delivered by vLLM's lenient parse with the same arguments as B's repair.
  - **1 is missed (finding F1):** the slip is written `<closer>, old_string:`, with a space after the comma. No stop
    string matches it. The post-hoc repair then delivers `old_string` with the leaked text `` `, new_string: `` and
    no `new_string`. In C's corpus 50/3,209 base-31B edit slips with a closer pattern (1.6%) have this whitespace
    form. B's relaxed grammar accepts `[ws] , [ws] KEY [ws] :`.
- **Prompt rendering:** the proxy's render matches the logged prompt length on 600/600 gate contexts. B's discovery
  render matches on 0/600; see §3.1.

### 8.2 P1 byte identity on valid calls (finding F2)
Each of the 229,414 valid QuoteStorm calls (§4.7; both key orders; 1,200 adversarial literals) was replayed through
E's **real request path**, `Proxy.engine_chat`, with a teacher-forced stub backend. A call counts as changed if the
proxy's raw text or the delivered arguments differ.

| code | cfg | natural calls changed | adversarial calls changed |
|---|---|---|---|
| reference (B) | — | 0/228,212 | 0/1,200 |
| proxy pre-fix | ipd | 0/228,212 (Wilson upper 0.0017%) | **278/1,200 = 23.2% [20.9, 25.6]** |
| proxy pre-fix | fullp | 0/228,212 | **278/1,200 = 23.2% [20.9, 25.6]** |
| proxy post-fix (final files) | ipd | 0/228,212 | **0/1,200** (Wilson upper 0.32%) |
| proxy post-fix (final files) | fullp | 0/228,212 | **0/1,200** (Wilson upper 0.32%) |

- 184 of the 278 changes are decode-time cuts. A literal value that ends in `` `,old_string: `` right before the
  true closer looks exactly like a slip at decode time, because the next token `<|"|>` reads as the next value's
  opener (P4).
- The other 94 come from the post-hoc path. `classify_args` flags the literal as a leak, and `intent_parse_args`
  then splits a valid call.
- **E's fix is verify-then-repair, mirroring (i+).** There are no decode-time stops. Every call runs to its end and
  goes through B's `is_valid` (vendored byte-identical, `vendor_b_gemma_protocol.py` = B's frozen
  `gemma_protocol.py`). A strictly valid call is delivered byte-identical. Otherwise the proxy applies B's
  `first_violation` (rules closer + opener; sites in undeclared keys are skipped), the noisy-channel cut, truncation,
  `<|"|>` and resume, for up to 4 rounds. The same guard sits in front of the post-hoc repair and of quarantine.
- **Post-fix files**, sha256: `e2e_proxy.py` a7e62cc1…, `gemma_protocol.py` 7ee13396…,
  `vendor_b_gemma_protocol.py` b8dac830…, `quarantine_renderer.py` 5ca5c62c…, `configs.json` 329f0bcf…,
  `channel_prior.json` bb48bb9a…. They are listed in `proxy_vendor_fix/VENDOR_MANIFEST.txt` and equal E's
  `acceptance/final_code_sha256.txt`. An intermediate renderer, 6b08b6e9…, also gave 0/229,412.
- **Post-fix CPU plan check on the 595 identical gate generations:**
  - valid calls → 0 plans (480/480);
  - slips → 104/104 planned, with the same violation kind and the same candidate cuts as B; the chosen cut on B's
    logged likelihoods is the same in 101/101 multi-cut cases, with the same prior;
  - the whitespace slip (F1) is now caught;
  - the opener-drift call is planned as in B, and the undeclared-key call is left alone.

### 8.3 Identical generations with the model in the loop (31B on :8302)
`proxy_equivalence.py tfe` sends each state through E's real `Proxy.engine_chat`, using a hybrid backend:
- requests whose token prefix matches the logged generation are answered from the log, so the proxy sees exactly
  the generation B's reference saw;
- likelihood scoring and every resumed generation after a cut go live to the 31B server;
- the proxy's seed is the request seed (0 on the gate). B's resume used seed + 1000, so regenerated suffixes are
  independent samples.

| set | code | valid calls byte-identical | slips intervened | cut = B's cut | delivered clean on slips (B) | all calls: delivered malformed (B loud) |
|---|---|---|---|---|---|---|
| gate, 595 calls / 104 slips | pre-fix | 480/480 | 102/104 | 100/100 decode-time | 103/104 (102/104) | 5/595 (12/595) |
| gate, 595 calls / 104 slips | post-fix | 480/480 | 104/104 | **104/104** | 101/104 (102/104) | 5/595 (12/595) |

| set | code | exact intent, proxy | exact intent, B's IPD (same states) | discordant states |
|---|---|---|---|---|
| G1, 229 gold states | pre-fix | 227/229 | 227/229 | 0 |
| G1, 229 gold states | post-fix | **227/229** | 227/229 | 0 |

- **Post-fix residuals on gate slips (3):**
  - 2 resumed generations degenerated into a run of `<|"|>` tokens under heavy server load, so no call was
    delivered. Re-running the same 2 states (same seed, lighter load) delivered calls byte-identical to B's repairs.
    The difference is vLLM batch nondeterminism.
  - 1 sample closed the call without `old_string` after the cut. B's sample of the same state wrote it.
  - A second post-fix pass, stopped at 20/104 slips to protect the server's KV cache, reproduced the first pass
    exactly: same cut, same delivered arguments 20/20.
- **Policy difference.** A residual invalid call is delivered leniently (malformed) by the proxy and fails loud in B.
  Over all 595 gate calls this gives 5 delivered-malformed calls for the proxy versus 12 loud errors for B.
- **Pre-fix only:** the whitespace slip (F1) is delivered malformed.

### 8.4 Live HTTP runs (600 gate contexts through the running proxy)
Post-fix proxy on port 8461, June template, backend :8302. Cfgs base, ipd and fullp. Seed 0, T 0.2, top-p 0.95,
max_tokens 6,144, no thinking budget, as in the gate. All three cfgs completed 600/600 contexts between 20:01 and
21:49 UTC. The proxy renders the log-faithful prompt, so the base arm also measures the render caveat of §3.1.

| arm (first call of the turn) | edit calls | closer slips (B detector, raw) | census-malformed delivered (B criterion) | contexts with an IPD repair |
|---|---|---|---|---|
| gate, B reference, natural calls (for comparison) | 406 | 63/406 = 15.5% | base 67/406 = 16.5% [13.2, 20.4] → after B's IPD 4/406 = 1.0% [0.4, 2.5] | — |
| proxy `base` | 404/600 | 65/404 = 16.1% [12.8, 20.0] | 67/404 = **16.6% [13.3, 20.5]** | — |
| proxy `ipd` | 410/600 | 0/410 | **1/410 = 0.2% [0.0, 1.4]** | 72 (75 repairs) |
| proxy `fullp` | 403/600 | 0/403 | **1/403 = 0.2% [0.0, 1.4]** | 64 (66 repairs) |

- **The baseline matches the gate.** The live base arm has 16.6% census-malformed first edits on log-faithful
  prompts, against 16.5% in B's natural-call gate on prompts 1 token short. So the render caveat has no measurable
  effect.
- **Delivered malformed edits, unconditional per context:** 67/600 = 11.2% under `base` and 1/600 = 0.2% under `ipd`
  or `fullp`. That is a relative reduction of **98.5%** (context bootstrap 95% [95, 100]). B's reference gives 94.0%
  [85.6, 97.7] on the gate's natural calls, and the intervals overlap.
- **The one residual** (the same context in `ipd` and `fullp`) has a quote followed by the key with **no comma**:
  `click.echo(", "old_string:`. That is not a slip site under B's grammar either, and in B's gate replay the same
  context failed loud.
- **Byte identity live.** `base` and `ipd` share the seed and the prompt, but only 267/528 (50.6%) of the
  intervention-free pairs are byte-identical. vLLM's seeded sampling is not batch-invariant over multi-thousand-token
  thinking generations, so live pairing cannot test P1. P1 is established by the teacher-forced tests in §8.2
  (0/229,412) and §8.3 (480/480).

### 8.5 Verdict
- On identical generations, the shipped post-fix proxy makes the same decisions as the reference decoder on every
  gate slip: site, candidates, prior and chosen cut agree on 104/104. It leaves all valid calls byte-identical: 480/480
  gate calls and 0/229,412 QuoteStorm calls changed, including 0/1,200 adversarial ones.
- On the 229 gold states it recovers exactly the same intents: 227/229, with 0 discordant states.
- Live, it removes 98.5% of delivered malformed first edits, matching the reference's discovery effect.
- The remaining difference is a policy, not a decoder difference: a residual invalid call is delivered leniently by
  the proxy and fails loud in the reference.
- Both pre-fix findings (F1 whitespace variant; F2 no byte identity on adversarial literals, 23.2%) are fixed in the
  post-fix files listed above.
