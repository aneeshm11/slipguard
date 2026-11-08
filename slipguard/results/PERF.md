# Parser timing: slipguard vs built-in Gemma 4 parsers (same inputs, same process, one CPU core)

Wall time of the largest size each target finished, and the least-squares log-log slope over all finished
sizes (1 = linear, 2 = quadratic). Inputs: workstream C's scaling families (diff/scaling.py). Streaming =
per-token deltas from the Gemma 4 tokenizer; built-in and plugin streaming include the server's own per-step
string accumulation (O(n) per step in every runtime); gg.stream is the parser alone.

| vLLM env | mode | family | target | sizes (n: ms) | slope | first timeout |
|---|---|---|---|---|---|---|
| vllm019 | non-streaming | code_with_commas | `gg.completion` | 250: 0.1, 1000: 0.1, 4000: 0.1, 16000: 0.3, 64000: 2.6 | None | - |
| vllm019 | non-streaming | code_with_commas | `gg.vllm019.server` | 250: 0.3, 1000: 0.3, 4000: 0.9, 16000: 3.1, 64000: 13 | 1.06 | - |
| vllm019 | non-streaming | code_with_commas | `vllm019.server` | 250: 0.5, 1000: 0.4, 4000: 1.0, 16000: 3.6, 64000: 13 | 0.96 | - |
| vllm019 | non-streaming | deep_arrays | `gg.completion` | 50: 0.2, 100: 0.3, 200: 0.7 | None | - |
| vllm019 | non-streaming | deep_arrays | `gg.vllm019.server` | 50: 0.4, 100: 0.5, 200: 0.8 | None | - |
| vllm019 | non-streaming | deep_arrays | `vllm019.server` | 50: 0.5, 100: 0.7, 200: 2.4 | None | - |
| vllm019 | non-streaming | flat_array_strings | `gg.completion` | 250: 0.5, 1000: 1.5, 4000: 5.8, 16000: 24 | 1.03 | - |
| vllm019 | non-streaming | flat_array_strings | `gg.vllm019.server` | 250: 0.8, 1000: 2.1, 4000: 6.7, 16000: 27 | 0.93 | - |
| vllm019 | non-streaming | flat_array_strings | `vllm019.server` | 250: 0.6, 1000: 2.1, 4000: 24, 16000: 339 | 1.84 | - |
| vllm019 | non-streaming | long_string | `gg.completion` | 10000: 0.1, 100000: 0.1, 1000000: 0.7, 4000000: 3.9 | None | - |
| vllm019 | non-streaming | long_string | `gg.vllm019.server` | 10000: 0.4, 100000: 0.7, 1000000: 5.8, 4000000: 24 | 1.02 | - |
| vllm019 | non-streaming | long_string | `vllm019.server` | 10000: 0.3, 100000: 0.7, 1000000: 5.9, 4000000: 25 | 1.03 | - |
| vllm019 | non-streaming | many_calls | `gg.completion` | 10: 0.3, 100: 1.4, 1000: 13, 4000: 55 | 1.01 | - |
| vllm019 | non-streaming | many_calls | `gg.vllm019.server` | 10: 0.6, 100: 2.7, 1000: 26, 4000: 103 | 0.98 | - |
| vllm019 | non-streaming | many_calls | `vllm019.server` | 10: 0.4, 100: 1.6, 1000: 14, 4000: 54 | 0.99 | - |
| vllm019 | non-streaming | many_int_keys | `gg.completion` | 125: 1.1, 250: 1.8, 500: 3.4, 1000: 6.6, 2000: 13, 4000: 27, 8000: 54, 16000: 108 | 1.0 | - |
| vllm019 | non-streaming | many_int_keys | `gg.vllm019.server` | 125: 1.3, 250: 2.1, 500: 3.6, 1000: 6.9, 2000: 14, 4000: 28, 8000: 56, 16000: 112 | 0.97 | - |
| vllm019 | non-streaming | many_int_keys | `vllm019.server` | 125: 0.9, 250: 0.7, 500: 0.8, 1000: 1.6, 2000: 3.2, 4000: 8.0, 8000: 21, 16000: 66 | 1.45 | - |
| vllm019 | non-streaming | many_string_keys | `gg.completion` | 125: 0.7, 250: 1.2, 500: 2.3, 1000: 4.6, 2000: 9.1, 4000: 18, 8000: 37, 16000: 74 | 1.01 | - |
| vllm019 | non-streaming | many_string_keys | `gg.vllm019.server` | 125: 1.0, 250: 1.5, 500: 2.6, 1000: 4.9, 2000: 9.9, 4000: 19, 8000: 40, 16000: 80 | 0.99 | - |
| vllm019 | non-streaming | many_string_keys | `vllm019.server` | 125: 0.5, 250: 0.6, 500: 0.7, 1000: 1.3, 2000: 3.4, 4000: 9.1, 8000: 28, 16000: 97 | 1.61 | - |
| vllm019 | streaming | code_with_commas | `gg.stream` | 100: 14, 400: 60, 1600: 258, 6400: 1064 | 1.04 | - |
| vllm019 | streaming | code_with_commas | `gg.vllm019.stream` | 100: 22, 400: 162, 1600: 2093, 6400: 39969 | 1.81 | - |
| vllm019 | streaming | code_with_commas | `vllm019.stream` | 100: 227, 400: 3523 | 1.98 | 1600 |
| vllm019 | streaming | long_string | `gg.stream` | 4000: 4.9, 16000: 18, 64000: 75, 256000: 315 | 1.01 | - |
| vllm019 | streaming | long_string | `gg.vllm019.stream` | 4000: 6.2, 16000: 27, 64000: 178, 256000: 2002 | 1.39 | - |
| vllm019 | streaming | long_string | `vllm019.stream` | 4000: 85, 16000: 1191, 64000: 18583 | 1.94 | 256000 |
| vllm019 | streaming | many_string_keys | `gg.stream` | 62: 5.9, 125: 9.9, 250: 21, 500: 43, 1000: 88, 2000: 194 | 1.02 | - |
| vllm019 | streaming | many_string_keys | `gg.vllm019.stream` | 62: 6.7, 125: 14, 250: 34, 500: 92, 1000: 276, 2000: 1042 | 1.45 | - |
| vllm019 | streaming | many_string_keys | `vllm019.stream` | 62: 36, 125: 134, 250: 561, 500: 2248, 1000: 9059, 2000: 47484 | 2.06 | - |
| vllm031 | non-streaming | code_with_commas | `gg.completion` | 250: 0.1, 1000: 0.1, 4000: 0.1, 16000: 0.3, 64000: 1.9 | None | - |
| vllm031 | non-streaming | code_with_commas | `gg.vllm031.server` | 250: 3.2, 1000: 9.3, 4000: 39, 16000: 157, 64000: 1184 | 1.06 | - |
| vllm031 | non-streaming | code_with_commas | `vllm031.server` | 250: 79, 1000: 1145, 4000: 18691 | 1.97 | 16000 |
| vllm031 | non-streaming | deep_arrays | `gg.completion` | 50: 0.2, 100: 0.4, 200: 0.7 | None | - |
| vllm031 | non-streaming | deep_arrays | `gg.vllm031.server` | 50: 0.7, 100: 0.7, 200: 1.1 | None | - |
| vllm031 | non-streaming | deep_arrays | `vllm031.server` | 50: 1.8, 100: 3.8, 200: 13 | 1.72 | - |
| vllm031 | non-streaming | flat_array_strings | `gg.completion` | 250: 0.5, 1000: 1.7, 4000: 6.1, 16000: 24 | 1.0 | - |
| vllm031 | non-streaming | flat_array_strings | `gg.vllm031.server` | 250: 4.2, 1000: 14, 4000: 54, 16000: 223 | 0.96 | - |
| vllm031 | non-streaming | flat_array_strings | `vllm031.server` | 250: 8.1, 1000: 28, 4000: 115, 16000: 473 | 0.98 | - |
| vllm031 | non-streaming | long_string | `gg.completion` | 10000: 0.1, 100000: 0.1, 1000000: 0.7, 4000000: 3.9 | None | - |
| vllm031 | non-streaming | long_string | `gg.vllm031.server` | 10000: 4.0, 100000: 37, 1000000: 502, 4000000: 2469 | 1.07 | - |
| vllm031 | non-streaming | long_string | `vllm031.server` | 10000: 6.0, 100000: 54, 1000000: 684, 4000000: 3210 | 1.05 | - |
| vllm031 | non-streaming | many_calls | `gg.completion` | 10: 0.3, 100: 1.4, 1000: 15, 4000: 55 | 0.95 | - |
| vllm031 | non-streaming | many_calls | `gg.vllm031.server` | 10: 1.2, 100: 4.4, 1000: 295, 4000: 162 | 1.07 | - |
| vllm031 | non-streaming | many_calls | `vllm031.server` | 10: 1.9, 100: 9.8, 1000: 94, 4000: 391 | 1.0 | - |
| vllm031 | non-streaming | many_int_keys | `gg.completion` | 125: 1.0, 250: 1.8, 500: 3.4, 1000: 6.8, 2000: 14, 4000: 28, 8000: 55, 16000: 110 | 1.0 | - |
| vllm031 | non-streaming | many_int_keys | `gg.vllm031.server` | 125: 2.3, 250: 2.8, 500: 4.8, 1000: 9.3, 2000: 19, 4000: 39, 8000: 82, 16000: 169 | 0.93 | - |
| vllm031 | non-streaming | many_int_keys | `vllm031.server` | 125: 42, 250: 151, 500: 582, 1000: 2304, 2000: 9291, 4000: 38812 | 1.97 | - |
| vllm031 | non-streaming | many_string_keys | `gg.completion` | 125: 0.8, 250: 1.4, 500: 2.2, 1000: 4.4, 2000: 9.2, 4000: 18, 8000: 37, 16000: 75 | 1.02 | - |
| vllm031 | non-streaming | many_string_keys | `gg.vllm031.server` | 125: 2.3, 250: 3.5, 500: 6.5, 1000: 13, 2000: 27, 4000: 53, 8000: 106, 16000: 227 | 0.97 | - |
| vllm031 | non-streaming | many_string_keys | `vllm031.server` | 125: 39, 250: 139, 500: 529, 1000: 2058, 2000: 8379, 4000: 34103 | 1.96 | - |
| vllm031 | streaming | code_with_commas | `gg.stream` | 100: 14, 400: 59, 1600: 250, 6400: 1039 | 1.04 | - |
| vllm031 | streaming | code_with_commas | `gg.vllm031.stream` | 100: 18, 400: 75, 1600: 316, 6400: 1322 | 1.03 | - |
| vllm031 | streaming | code_with_commas | `vllm031.stream` | 100: 100, 400: 1225, 1600: 19459 | 1.9 | 6400 |
| vllm031 | streaming | long_string | `gg.stream` | 4000: 4.7, 16000: 18, 64000: 73, 256000: 307 | 1.01 | - |
| vllm031 | streaming | long_string | `gg.vllm031.stream` | 4000: 6.2, 16000: 22, 64000: 90, 256000: 370 | 0.98 | - |
| vllm031 | streaming | long_string | `vllm031.stream` | 4000: 7.1, 16000: 24, 64000: 98, 256000: 406 | 0.98 | - |
| vllm031 | streaming | many_string_keys | `gg.stream` | 62: 8.4, 125: 9.7, 250: 21, 500: 43, 1000: 87, 2000: 190 | 0.94 | - |
| vllm031 | streaming | many_string_keys | `gg.vllm031.stream` | 62: 6.7, 125: 13, 250: 26, 500: 55, 1000: 111, 2000: 243 | 1.04 | - |
| vllm031 | streaming | many_string_keys | `vllm031.stream` | 62: 29, 125: 90, 250: 308, 500: 1126, 1000: 4293, 2000: 17195 | 1.84 | - |
| vllm033 | non-streaming | code_with_commas | `gg.completion` | 250: 0.1, 1000: 0.1, 4000: 0.1, 16000: 0.3, 64000: 2.0 | None | - |
| vllm033 | non-streaming | code_with_commas | `gg.vllm033.server` | 250: 3.3, 1000: 9.6, 4000: 40, 16000: 171, 64000: 1200 | 1.06 | - |
| vllm033 | non-streaming | code_with_commas | `vllm033.server` | 250: 12, 1000: 53, 4000: 394, 16000: 5520 | 1.48 | 64000 |
| vllm033 | non-streaming | deep_arrays | `gg.completion` | 50: 0.2, 100: 0.3, 200: 0.7 | None | - |
| vllm033 | non-streaming | deep_arrays | `gg.vllm033.server` | 50: 0.7, 100: 0.8, 200: 1.2 | None | - |
| vllm033 | non-streaming | deep_arrays | `vllm033.server` | 50: 2.1, 100: 4.8, 200: 17 | 1.48 | - |
| vllm033 | non-streaming | flat_array_strings | `gg.completion` | 250: 0.5, 1000: 1.5, 4000: 6.0, 16000: 24 | 1.0 | - |
| vllm033 | non-streaming | flat_array_strings | `gg.vllm033.server` | 250: 4.3, 1000: 14, 4000: 52, 16000: 229 | 0.96 | - |
| vllm033 | non-streaming | flat_array_strings | `vllm033.server` | 250: 8.4, 1000: 29, 4000: 118, 16000: 496 | 0.98 | - |
| vllm033 | non-streaming | long_string | `gg.completion` | 10000: 0.1, 100000: 0.1, 1000000: 0.7, 4000000: 4.0 | None | - |
| vllm033 | non-streaming | long_string | `gg.vllm033.server` | 10000: 4.1, 100000: 37, 1000000: 512, 4000000: 2511 | 1.07 | - |
| vllm033 | non-streaming | long_string | `vllm033.server` | 10000: 6.0, 100000: 54, 1000000: 678, 4000000: 3216 | 1.05 | - |
| vllm033 | non-streaming | many_calls | `gg.completion` | 10: 0.2, 100: 1.5, 1000: 13, 4000: 54 | 1.01 | - |
| vllm033 | non-streaming | many_calls | `gg.vllm033.server` | 10: 1.2, 100: 4.4, 1000: 38, 4000: 158 | 0.97 | - |
| vllm033 | non-streaming | many_calls | `vllm033.server` | 10: 2.0, 100: 10, 1000: 99, 4000: 696 | 1.13 | - |
| vllm033 | non-streaming | many_int_keys | `gg.completion` | 125: 1.8, 250: 3.2, 500: 6.4, 1000: 8.4, 2000: 14, 4000: 27, 8000: 53, 16000: 107 | 0.82 | - |
| vllm033 | non-streaming | many_int_keys | `gg.vllm033.server` | 125: 12, 250: 3.0, 500: 5.1, 1000: 9.5, 2000: 19, 4000: 40, 8000: 82, 16000: 170 | 0.72 | - |
| vllm033 | non-streaming | many_int_keys | `vllm033.server` | 125: 55, 250: 220, 500: 834, 1000: 3268, 2000: 13334, 4000: 54182 | 1.98 | - |
| vllm033 | non-streaming | many_string_keys | `gg.completion` | 125: 0.7, 250: 1.2, 500: 2.3, 1000: 4.4, 2000: 9.2, 4000: 18, 8000: 38, 16000: 76 | 1.02 | - |
| vllm033 | non-streaming | many_string_keys | `gg.vllm033.server` | 125: 2.4, 250: 3.5, 500: 6.5, 1000: 13, 2000: 27, 4000: 53, 8000: 106, 16000: 224 | 0.96 | - |
| vllm033 | non-streaming | many_string_keys | `vllm033.server` | 125: 51, 250: 187, 500: 722, 1000: 2826, 2000: 11522, 4000: 46789 | 1.97 | - |
| vllm033 | streaming | code_with_commas | `gg.stream` | 100: 14, 400: 58, 1600: 245, 6400: 1016 | 1.04 | - |
| vllm033 | streaming | code_with_commas | `gg.vllm033.stream` | 100: 18, 400: 73, 1600: 309, 6400: 1268 | 1.03 | - |
| vllm033 | streaming | code_with_commas | `vllm033.stream` | 100: 36, 400: 151, 1600: 670, 6400: 2947 | 1.06 | - |
| vllm033 | streaming | long_string | `gg.stream` | 4000: 4.6, 16000: 17, 64000: 71, 256000: 307 | 1.01 | - |
| vllm033 | streaming | long_string | `gg.vllm033.stream` | 4000: 6.1, 16000: 21, 64000: 87, 256000: 362 | 0.99 | - |
| vllm033 | streaming | long_string | `vllm033.stream` | 4000: 11, 16000: 42, 64000: 173, 256000: 786 | 1.02 | - |
| vllm033 | streaming | many_string_keys | `gg.stream` | 62: 10, 125: 9.7, 250: 20, 500: 42, 1000: 86, 2000: 191 | 0.9 | - |
| vllm033 | streaming | many_string_keys | `gg.vllm033.stream` | 62: 6.5, 125: 12, 250: 26, 500: 53, 1000: 107, 2000: 236 | 1.04 | - |
| vllm033 | streaming | many_string_keys | `vllm033.stream` | 62: 44, 125: 142, 250: 504, 500: 1882, 1000: 7273, 2000: 29287 | 1.88 | - |

## Figure spec (paper)

* Two panels, log-log axes: (a) `many_string_keys` (x = number of arguments, 125 to 16,000), (b) `long_string`
  (x = string length in characters, 1e4 to 4e6); y = parse wall time in ms (non-streaming).
* Series: vLLM 0.19.1 / 0.31.0 / 0.33.0 built-in `gemma4` server path (one colour family, three shades);
  slipguard `parse_completion` and the slipguard plugin through vLLM 0.33's server objects (second colour).
* Reference lines: slope 1 and slope 2 through the first slipguard / first vLLM 0.33 point (dashed, grey).
* Timeouts drawn as an open marker at the timeout value with an upward arrow; annotate the vLLM 0.33
  4,000-argument point with its wall time.
* Inset or third panel: streaming (`many_string_keys`, per-token deltas), same series; caption notes that
  server-side per-step string accumulation is included for the runtime paths.
* Data: results/PERF.json (`points` per series).
