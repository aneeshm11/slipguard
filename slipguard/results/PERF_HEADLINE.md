| input | vLLM | built-in parser | slipguard plugin (same server objects) | slipguard API |
|---|---|---|---|---|
| many_int_keys (non-streaming), 4,000 arguments | 0.19 | 8.0 ms, slope 1.45 | 28 ms, slope 0.97 | 27 ms, slope 1.0 |
| many_int_keys (non-streaming), 4,000 arguments | 0.31 | 38.8 s, slope 1.97 | 39 ms, slope 0.93 | 28 ms, slope 1.0 |
| many_int_keys (non-streaming), 4,000 arguments | 0.33 | 54.2 s, slope 1.98 | 40 ms, slope 0.72 | 27 ms, slope 0.82 |
| many_string_keys (non-streaming), 4,000 arguments | 0.19 | 9.1 ms, slope 1.61 | 19 ms, slope 0.99 | 18 ms, slope 1.01 |
| many_string_keys (non-streaming), 4,000 arguments | 0.31 | 34.1 s, slope 1.96 | 53 ms, slope 0.97 | 18 ms, slope 1.02 |
| many_string_keys (non-streaming), 4,000 arguments | 0.33 | 46.8 s, slope 1.97 | 53 ms, slope 0.96 | 18 ms, slope 1.02 |
| code_with_commas (non-streaming), 16,000 code lines | 0.19 | 3.6 ms, slope 0.96 | 3.1 ms, slope 1.06 | 0.3 ms, slope None |
| code_with_commas (non-streaming), 16,000 code lines | 0.31 | > 60 s (timeout), slope 1.97 | 157 ms, slope 1.06 | 0.3 ms, slope None |
| code_with_commas (non-streaming), 16,000 code lines | 0.33 | 5.5 s, slope 1.48 | 171 ms, slope 1.06 | 0.3 ms, slope None |
| long_string (non-streaming), 4,000,000 chars | 0.19 | 25 ms, slope 1.03 | 24 ms, slope 1.02 | 3.9 ms, slope None |
| long_string (non-streaming), 4,000,000 chars | 0.31 | 3.2 s, slope 1.05 | 2.5 s, slope 1.07 | 3.9 ms, slope None |
| long_string (non-streaming), 4,000,000 chars | 0.33 | 3.2 s, slope 1.05 | 2.5 s, slope 1.07 | 4.0 ms, slope None |
| many_string_keys (streaming), 2,000 arguments | 0.19 | 47.5 s, slope 2.06 | 1.0 s, slope 1.45 | 194 ms, slope 1.02 |
| many_string_keys (streaming), 2,000 arguments | 0.31 | 17.2 s, slope 1.84 | 243 ms, slope 1.04 | 190 ms, slope 0.94 |
| many_string_keys (streaming), 2,000 arguments | 0.33 | 29.3 s, slope 1.88 | 236 ms, slope 1.04 | 191 ms, slope 0.9 |
| code_with_commas (streaming), 6,400 code lines | 0.19 | > 60 s (timeout), slope 1.98 | 40.0 s, slope 1.81 | 1.1 s, slope 1.04 |
| code_with_commas (streaming), 6,400 code lines | 0.31 | > 60 s (timeout), slope 1.9 | 1.3 s, slope 1.03 | 1.0 s, slope 1.04 |
| code_with_commas (streaming), 6,400 code lines | 0.33 | 2.9 s, slope 1.06 | 1.3 s, slope 1.03 | 1.0 s, slope 1.04 |
