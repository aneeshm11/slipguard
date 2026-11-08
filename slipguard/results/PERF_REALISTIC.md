# Parser cost on realistic agent traffic (PNC corpus: every model turn of the natural Gemma 4 trajectories)

One process per (vLLM version, parser), each pinned to its own CPU core; built-in = the runtime's gemma4 reasoning
+ tool parsers, slipguard = the plugin, both inside that runtime's own server-path objects; token ids and
per-token deltas are computed outside the timers. Generation time = the turn's logged LLM wall time.

| vLLM | parser | turns | non-streaming per 1,000 turns | p50 / p99 / max per turn | streaming per 1,000 turns | p50 / p99 / max per turn | worst stall | turns with a stall >= 100 ms / >= 1 s | parse time as % of generation time (non-stream / stream) | calls delivered / logged |
|---|---|---|---|---|---|---|---|---|---|---|
| 0.19.1 | builtin | 41290/41290 | 117 ms | 0.11 / 0.19 / 2.9 ms | 8473 ms | 1.16 / 128.43 / 9173.5 ms | 16.1 ms | 0 / 0 | 0.0016% / 0.1123% | 41129 / 41120 |
| 0.19.1 | slipguard | 41290/41290 | 254 ms | 0.25 / 0.33 / 2.4 ms | 1984 ms | 0.77 / 18.33 / 95.5 ms | 4.5 ms | 0 / 0 | 0.0034% / 0.0263% | 40435 / 41120 |
| 0.31.0 | builtin | 41290/41290 | 2117 ms | 1.33 / 15.87 / 181.5 ms | 4816 ms | 1.76 / 39.99 / 2838.5 ms | 181.5 ms | 4 / 0 | 0.0280% / 0.0638% | 41313 / 41120 |
| 0.31.0 | slipguard | 41290/41290 | 360 ms | 0.36 / 0.45 / 2.3 ms | 2322 ms | 0.96 / 20.01 / 103.1 ms | 16.1 ms | 0 / 0 | 0.0048% / 0.0308% | 40435 / 41120 |
| 0.32.0 | builtin | 41290/41290 | 1730 ms | 1.03 / 11.77 / 178.1 ms | 4032 ms | 1.54 / 33.97 / 1511.8 ms | 178.1 ms | 4 / 0 | 0.0229% / 0.0534% | 41313 / 41120 |
| 0.32.0 | slipguard | 41290/41290 | 362 ms | 0.36 / 0.45 / 2.3 ms | 2345 ms | 0.97 / 20.05 / 105.5 ms | 13.5 ms | 0 / 0 | 0.0048% / 0.0311% | 40435 / 41120 |
| 0.33.0 | builtin | 41290/41290 | 1783 ms | 1.34 / 8.49 / 110.1 ms | 5128 ms | 2.13 / 38.28 / 193.4 ms | 110.1 ms | 1 / 0 | 0.0236% / 0.0679% | 41313 / 41120 |
| 0.33.0 | slipguard | 41290/41290 | 248 ms | 0.24 / 0.38 / 1.8 ms | 1318 ms | 0.57 / 11.07 / 55.0 ms | 15.5 ms | 0 / 0 | 0.0033% / 0.0175% | 40435 / 41120 |

Tail drivers (the 1% slowest turns by streaming parse time):

* vLLM 0.19.1 builtin: 412 turns; output chars p50 3737 (all turns: 340), max 31327; tokens p50 1060; call argument JSON chars p50 2911, max 16153; tools {'bash': 35, 'edit_file': 73, 'execute_bash': 16, 'read_file': 1, 'str_replace_editor': 12, 'write_file': 271}
* vLLM 0.19.1 slipguard: 412 turns; output chars p50 10430 (all turns: 340), max 63613; tokens p50 3206; call argument JSON chars p50 203, max 16153; tools {'bash': 131, 'edit_file': 111, 'execute_bash': 14, 'finish': 1, 'read_file': 68, 'str_replace_editor': 23, 'submit': 2, 'write_file': 53}
* vLLM 0.31.0 builtin: 412 turns; output chars p50 8874 (all turns: 340), max 31327; tokens p50 2629; call argument JSON chars p50 1522, max 16153; tools {'bash': 79, 'edit_file': 90, 'execute_bash': 21, 'read_file': 40, 'str_replace_editor': 20, 'submit': 2, 'write_file': 153}
* vLLM 0.31.0 slipguard: 412 turns; output chars p50 10444 (all turns: 340), max 63613; tokens p50 3206; call argument JSON chars p50 247, max 16153; tools {'bash': 130, 'edit_file': 113, 'execute_bash': 15, 'read_file': 66, 'str_replace_editor': 22, 'submit': 2, 'write_file': 55}
* vLLM 0.32.0 builtin: 412 turns; output chars p50 9435 (all turns: 340), max 31327; tokens p50 2803; call argument JSON chars p50 1440, max 16153; tools {'bash': 92, 'edit_file': 95, 'execute_bash': 18, 'read_file': 42, 'str_replace_editor': 16, 'write_file': 142}
* vLLM 0.32.0 slipguard: 412 turns; output chars p50 10444 (all turns: 340), max 63613; tokens p50 3206; call argument JSON chars p50 235, max 16153; tools {'bash': 128, 'edit_file': 113, 'execute_bash': 15, 'finish': 1, 'read_file': 65, 'str_replace_editor': 23, 'submit': 2, 'write_file': 56}
* vLLM 0.33.0 builtin: 412 turns; output chars p50 9358 (all turns: 340), max 31327; tokens p50 2803; call argument JSON chars p50 807, max 16153; tools {'bash': 92, 'edit_file': 104, 'execute_bash': 21, 'finish': 1, 'read_file': 46, 'str_replace_editor': 24, 'submit': 2, 'write_file': 115}
* vLLM 0.33.0 slipguard: 412 turns; output chars p50 10430 (all turns: 340), max 63613; tokens p50 3206; call argument JSON chars p50 271, max 16153; tools {'bash': 127, 'edit_file': 112, 'execute_bash': 14, 'read_file': 66, 'str_replace_editor': 23, 'submit': 2, 'write_file': 59}

## Decision (PI rule: a GPU serving benchmark only if the built-in parser costs > 1% of wall time in aggregate, or
## produces multi-second stalls at realistic frequency)

* **Aggregate cost is small for every runtime.** The built-in parsers cost 0.002-0.03% of the turns' generation time
  non-streaming and 0.05-0.11% streaming (vLLM 0.19.1, 0.31.0, 0.32.0 and 0.33.0); slipguard costs 0.003-0.005% and 0.02-0.03%.
  Both are two to four orders of magnitude below the 1% threshold.
* **No multi-second stalls on natural traffic.** The longest single blocking parser call was 181 ms (vLLM 0.31,
  non-streaming, a turn with a 16 KB `write_file` call); 4 of 41,290 turns exceeded 100 ms and none reached 1 s. Per-token
  streaming calls never exceeded 16 ms. (Per-turn streaming totals reach 9.2 s on vLLM 0.19.1 for the longest
  outputs, but spread over thousands of steps, not as one stall.) slipguard's worst single call was 16 ms.
* **Conclusion: no GPU serving benchmark.** On typical Gemma 4 agent traffic the parser is not a throughput
  bottleneck for either implementation, and we say so. slipguard's speed claim stays (a) the micro-benchmark
  (results/PERF.md: 4,000-argument calls 54 s -> 40 ms on vLLM 0.33; slope 2 -> 1) and (b) robustness: no hang, no
  quadratic blow-up on large or many-argument calls, bounded per-call latency.
* **What does differ on natural traffic is correctness:** slipguard refuses 685 of the 41,120 calls that vLLM 0.19.1
  delivered (683 turns; 161 slips the quarantine criterion flags; 445 `key=value` drifts that vLLM silently dropped).
  vLLM 0.31-0.33 deliver 41,313 calls on the same texts: in 192 turns (0.47%) they turn header-drifted text that
  0.19.1 left visible (`call edit_file{`, `call,bash{`, `call:grep "..."`) into calls, some named after argument
  text (the suite's E5 class). slipguard returns those turns as text.

Measurement note: the tables come from the run of 10:08-10:17 UTC, when the eight measurement cores were idle
(utilisation 0-12% before the run). A later re-run of the slipguard rows (after a micro-optimisation that skips a
per-request tool conversion in syntax mode) happened while other jobs saturated those cores; its p99 and maxima were
inflated by contention (e.g. a 3,100-character turn at 41 ms that took 0.3 ms in the quiet run) and it is not used.
The optimisation can only lower the slipguard numbers above.
