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
