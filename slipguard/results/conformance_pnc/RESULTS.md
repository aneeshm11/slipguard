# Conformance on public real inputs (PNC: every model turn)

41,290 turns: 40,417 strictly valid turns with calls, 1 valid without a call, 872 ill-formed (218 with retry-derived intent, 654 without). Judged with workstream C's rules (diff/analyze_x.judge). Built-in = the parsers vLLM / transformers ship (C's harness); slipguard = this library, the plugin driven through each vLLM version's own server objects. Streaming = one token per delta, no length cap.

Ill-formed input classes (first protocol error): key=value argument drift 446, look-alike string closer 106, call-header drift 95, BAD_NAME 83, bare / foreign literal 65, unterminated call 36, JSON-style string 19, stray control token 15, DUPLICATE_KEY 4, BAD_KEY 1, EXPECTED_CALL_CLOSE 1, none 1.

| target | valid calls exact | ill-formed surfaced | of which: valid calls before the error + rest as text | silently delivered | silently lost | known intent: exact / WRONG / surfaced | no intent: delivered (unscored) | hang / exc |
|---|---|---|---|---|---|---|---|---|
| slipguard parse_completion | 40,417/40,417 | 872/872 | 0 | 0 | 0 | 0 / 0 / 218 (n=218) | 0 (n=654) | 0 / 0 |
| slipguard extract (per-call) | 40,417/40,417 | 872/872 | 0 | 0 | 0 | 0 / 0 / 218 (n=218) | 0 (n=654) | 0 / 0 |
| slipguard extract(repair=True) [opt-in] | 40,417/40,417 | 393/872 | 0 | 479 | 0 | 152 / 0 / 66 (n=218) | 327 (n=654) | 0 / 0 |
| slipguard StreamParser | 40,417/40,417 | 872/872 | 0 | 0 | 0 | 0 / 0 / 218 (n=218) | 0 (n=654) | 0 / 0 |
| slipguard plugin, vLLM 0.19 server | 40,417/40,417 | 872/872 | 4 | 0 | 0 | 0 / 0 / 218 (n=218) | 0 (n=654) | 0 / 0 |
| slipguard plugin, vLLM 0.19 stream | 40,417/40,417 | 872/872 | 4 | 0 | 0 | 0 / 0 / 218 (n=218) | 0 (n=654) | 0 / 0 |
| slipguard plugin, vLLM 0.24 server | 40,417/40,417 | 872/872 | 4 | 0 | 0 | 0 / 0 / 218 (n=218) | 0 (n=654) | 0 / 0 |
| slipguard plugin, vLLM 0.24 stream | 40,417/40,417 | 872/872 | 4 | 0 | 0 | 0 / 0 / 218 (n=218) | 0 (n=654) | 0 / 0 |
| slipguard plugin, vLLM 0.31 server | 40,417/40,417 | 872/872 | 4 | 0 | 0 | 0 / 0 / 218 (n=218) | 0 (n=654) | 0 / 0 |
| slipguard plugin, vLLM 0.31 stream | 40,417/40,417 | 872/872 | 4 | 0 | 0 | 0 / 0 / 218 (n=218) | 0 (n=654) | 0 / 0 |
| slipguard plugin, vLLM 0.32 server | 40,417/40,417 | 872/872 | 4 | 0 | 0 | 0 / 0 / 218 (n=218) | 0 (n=654) | 0 / 0 |
| slipguard plugin, vLLM 0.32 stream | 40,417/40,417 | 872/872 | 4 | 0 | 0 | 0 / 0 / 218 (n=218) | 0 (n=654) | 0 / 0 |
| slipguard plugin, vLLM 0.33 server | 40,417/40,417 | 872/872 | 4 | 0 | 0 | 0 / 0 / 218 (n=218) | 0 (n=654) | 0 / 0 |
| slipguard plugin, vLLM 0.33 stream | 40,417/40,417 | 872/872 | 4 | 0 | 0 | 0 / 0 / 218 (n=218) | 0 (n=654) | 0 / 0 |
| transformers 5.13 parse_response | 40,417/40,417 | 847/872 | 0 | 24 | 1 | 0 / 0 / 218 (n=218) | 24 (n=654) | 0 / 0 |
| transformers 5.17 parse_response | 40,417/40,417 | 847/872 | 0 | 24 | 1 | 0 / 0 / 218 (n=218) | 24 (n=654) | 0 / 0 |
| gemmaproto (reference) | 40,417/40,417 | 872/872 | 0 | 0 | 0 | 0 / 0 / 218 (n=218) | 0 (n=654) | 0 / 0 |
| vLLM 0.19 built-in server | 40,417/40,417 | 185/872 | 0 | 687 | 0 | 0 / 188 / 30 (n=218) | 499 (n=654) | 0 / 0 |
| vLLM 0.19 built-in stream | 40,406/40,417 | 75/872 | 0 | 692 | 105 | 0 / 188 / 12 (n=218) | 504 (n=654) | 1 / 0 |
| vLLM 0.24 built-in server | 40,407/40,417 | 33/872 | 0 | 777 | 62 | 1 / 188 / 1 (n=218) | 588 (n=654) | 0 / 0 |
| vLLM 0.24 built-in stream | 40,407/40,417 | 33/872 | 0 | 777 | 62 | 1 / 188 / 1 (n=218) | 588 (n=654) | 0 / 0 |
| vLLM 0.31 built-in server | 40,406/40,417 | 5/872 | 0 | 865 | 2 | 1 / 216 / 1 (n=218) | 648 (n=654) | 0 / 0 |
| vLLM 0.31 built-in stream | 40,406/40,417 | 3/872 | 0 | 869 | 0 | 1 / 216 / 1 (n=218) | 652 (n=654) | 0 / 0 |
| vLLM 0.32 built-in server | 40,406/40,417 | 5/872 | 0 | 865 | 2 | 1 / 216 / 1 (n=218) | 648 (n=654) | 0 / 0 |
| vLLM 0.32 built-in stream | 40,406/40,417 | 3/872 | 0 | 869 | 0 | 1 / 216 / 1 (n=218) | 652 (n=654) | 0 / 0 |
| vLLM 0.33 built-in server | 40,406/40,417 | 5/872 | 0 | 865 | 2 | 1 / 216 / 1 (n=218) | 648 (n=654) | 0 / 0 |
| vLLM 0.33 built-in stream | 40,406/40,417 | 3/872 | 0 | 869 | 0 | 1 / 216 / 1 (n=218) | 652 (n=654) | 0 / 0 |

## Silent outcomes per input class (turns where the target neither raised nor kept the call text)

| target | key=value argument drift (n=446) | look-alike string closer (n=106) | call-header drift (n=95) | BAD_NAME (n=83) | bare / foreign literal (n=65) | unterminated call (n=36) | JSON-style string (n=19) | stray control token (n=15) | DUPLICATE_KEY (n=4) | BAD_KEY (n=1) | EXPECTED_CALL_CLOSE (n=1) | none (n=1) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| slipguard parse_completion | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| slipguard extract (per-call) | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| slipguard extract(repair=True) [opt-in] | 440 | 35 | 0 | 0 | 0 | 4 | 0 | 0 | 0 | 0 | 0 | 0 |
| slipguard StreamParser | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| slipguard plugin, vLLM 0.19 server | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| slipguard plugin, vLLM 0.19 stream | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| slipguard plugin, vLLM 0.24 server | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| slipguard plugin, vLLM 0.24 stream | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| slipguard plugin, vLLM 0.31 server | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| slipguard plugin, vLLM 0.31 stream | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| slipguard plugin, vLLM 0.32 server | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| slipguard plugin, vLLM 0.32 stream | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| slipguard plugin, vLLM 0.33 server | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| slipguard plugin, vLLM 0.33 stream | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| transformers 5.13 parse_response | 0 | 0 | 1 | 0 | 0 | 0 | 7 | 13 | 4 | 0 | 0 | 0 |
| transformers 5.17 parse_response | 0 | 0 | 1 | 0 | 0 | 0 | 7 | 13 | 4 | 0 | 0 | 0 |
| gemmaproto (reference) | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| vLLM 0.19 built-in server | 446 | 106 | 1 | 1 | 65 | 31 | 19 | 12 | 4 | 1 | 1 | 0 |
| vLLM 0.19 built-in stream | 446 | 106 | 53 | 53 | 65 | 35 | 19 | 12 | 4 | 1 | 1 | 1 |
| vLLM 0.24 built-in server | 446 | 106 | 65 | 83 | 65 | 36 | 19 | 12 | 4 | 1 | 1 | 1 |
| vLLM 0.24 built-in stream | 446 | 106 | 65 | 83 | 65 | 36 | 19 | 12 | 4 | 1 | 1 | 1 |
| vLLM 0.31 built-in server | 446 | 106 | 93 | 83 | 65 | 36 | 19 | 12 | 4 | 1 | 1 | 1 |
| vLLM 0.31 built-in stream | 446 | 106 | 95 | 83 | 65 | 36 | 19 | 12 | 4 | 1 | 1 | 1 |
| vLLM 0.32 built-in server | 446 | 106 | 93 | 83 | 65 | 36 | 19 | 12 | 4 | 1 | 1 | 1 |
| vLLM 0.32 built-in stream | 446 | 106 | 95 | 83 | 65 | 36 | 19 | 12 | 4 | 1 | 1 | 1 |
| vLLM 0.33 built-in server | 446 | 106 | 93 | 83 | 65 | 36 | 19 | 12 | 4 | 1 | 1 | 1 |
| vLLM 0.33 built-in stream | 446 | 106 | 95 | 83 | 65 | 36 | 19 | 12 | 4 | 1 | 1 | 1 |

## Streaming == non-streaming (same outcome and same calls)

| path | same / n |
|---|---|
| slipguard plugin, vLLM 0.19 | 41,290/41,290 |
| slipguard plugin, vLLM 0.24 | 41,290/41,290 |
| slipguard plugin, vLLM 0.31 | 41,290/41,290 |
| slipguard plugin, vLLM 0.32 | 41,290/41,290 |
| slipguard plugin, vLLM 0.33 | 41,290/41,290 |
| vLLM 0.19 built-in | 41,250/41,290 |
| vLLM 0.24 built-in | 41,285/41,290 |
| vLLM 0.31 built-in | 41,268/41,290 |
| vLLM 0.32 built-in | 41,268/41,290 |
| vLLM 0.33 built-in | 41,268/41,290 |

Definitions. *Surfaced*: C's judge passes the target on ill-formed input (an error, or the turn returned as text that still carries the call), or -- per-call runtime semantics -- the strictly valid calls BEFORE the first protocol error are delivered and everything from the error on is returned as text (a server has no error channel; nothing after the error becomes a call). *Silently delivered*: the target returned a call from ill-formed text without an error. On turns with known intent the delivered call is scored (exact = what the model meant; WRONG = a dropped argument, a corrupted value, a wrong name or a wrong number of calls); without intent it is not scored. *Retry-derived intent*: the malformed call is the turn's last call and a later turn of the same episode (within 3) restates it as a clean call (strictly valid, not flagged by the frozen quarantine criterion) whose keys and values all occur in the malformed call text, with a canonical rendering at most 8 characters shorter / 24 characters longer (conformance/build_pnc_cases.py).

## Post-hoc fix to the opt-in repair (disclosure)

The opt-in text repair (`gg.repair` here; `gemma4_strict_repair` in vLLM) was changed AFTER this public-input run was
first judged, so for the repair rule these PNC turns are no longer a held-out test. Nothing else is affected: every other
target's results are identical before and after (the strict parser and the default plugin parsers never call the repair
code).

* **Pre-fix** (rule as run 11:20 UTC Nov 5): on the 218 turns with retry-derived intent, 152 exact / **1 wrong** / 65
  left loud; 350 unscored repairs on the 654 no-intent turns. Judged results: `prefix_fix/RESULTS.md` (.json).
* **Cause**: in one turn the model ended a `write_file` content string with a shell heredoc terminator (`EOF` and a
  newline) and wrote no string closer before `,file_path:`. The closer rule treated the whitespace-only run (the newline)
  as a look-alike closer and kept `EOF` in the value; the model's own retry dropped `EOF` and kept the newline.
* **Fix**: an empty or whitespace-only run is a missing closer, not a look-alike, and now stays loud
  (`prefix_fix/repair_fix.diff`).
* **Post-fix** (this file): 152 exact / **0 wrong** / 66 loud; 327 unscored repairs.
* **The same fix on the development-log suite**: real slips 1,429 -> 1,419 exact (the 10 lost were whitespace-only cuts
  that happened to match), 0 wrong before and after, 181 -> 191 loud; synthetic families unchanged. On the 683 PNC turns
  that strict parsing refuses: 503 -> 479 repaired (closer slips 63 -> 39; kwarg 440 unchanged).
* **Provenance** (no git): `prefix_fix/PROVENANCE.json` has the sha256 of every input, result and code file. The
  reconstructed pre-fix rule reproduces the logged pre-fix run on all 872 ill-formed turns (same outcome, same call
  fingerprint).
