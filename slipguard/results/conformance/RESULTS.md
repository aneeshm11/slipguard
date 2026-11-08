# slipguard conformance (C's suite, C's judging rules)

190568 results; 14 targets = 13 default targets + 1 opt-in repair target (gg.repair, informational): gg.completion, gg.extract, gg.repair, gg.stream, gg.vllm019.server, gg.vllm019.stream, gg.vllm024.server, gg.vllm024.stream, gg.vllm031.server, gg.vllm031.stream, gg.vllm032.server, gg.vllm032.stream, gg.vllm033.server, gg.vllm033.stream.

## Table D: per bug class, worst verdict over the class's minimal repros (✓ pass, ~ policy, ✗ defect)

| class | gg.completion | gg.extract | gg.repair | gg.stream | gg.vllm019.server | gg.vllm019.stream | gg.vllm024.server | gg.vllm024.stream | gg.vllm031.server | gg.vllm031.stream | gg.vllm032.server | gg.vllm032.stream | gg.vllm033.server | gg.vllm033.stream |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| E1 closer_slip (silent absorption after a look-alike closer) | ✓ | ✓ | ~ ABSORB_BACKTICK:EXACT,ABSORB_DQUOTE:EXACT,ABSORB_FIRST_ARG:EXACT,LAST_ARG_CLOSER:EXACT | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| E2 key_restart (closer, comma, newline, same key) | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| E3 opener_drift ('=', JSON/Python quotes, bare text) | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| E4 key_drift (quotes on the key side) | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| E5 unparsed_call (header drift, unclosed call) | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| C2 truncated call returned/executed | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| C4 doubled delimiter -> empty value | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| C5 stray delimiter after number kept | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| C6 control token in string: truncation / deletion / call injection | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| C7 infinite loop + memory growth | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| C8 quadratic parse time | ✓ | ✓ | ✓ | · | ✓ | · | ✓ | · | ✓ | · | ✓ | · | ✓ | · |
| C9 uncaught RecursionError (deep nesting) | ✓ | ✓ | ✓ | · | ✓ | · | ✓ | · | ✓ | · | ✓ | · | ✓ | · |
| C10 type drift on valid input | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| C11 non-L1 literal coerced/stringified | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| C12 valid names/keys/whitespace mishandled | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| C13 multiple calls / streaming call merge | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |

## Table F: per-class presence over the fuzz corpus (k/n inputs where the defect shows)

| class | gg.completion | gg.extract | gg.repair | gg.stream | gg.vllm019.server | gg.vllm019.stream | gg.vllm024.server | gg.vllm024.stream | gg.vllm031.server | gg.vllm031.stream | gg.vllm032.server | gg.vllm032.stream | gg.vllm033.server | gg.vllm033.stream |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ABSORB | 0/2788 | 0/2788 | 0/2788 | 0/2781 | 0/2788 | 0/2781 | 0/2788 | 0/2781 | 0/2788 | 0/2781 | 0/2788 | 0/2781 | 0/2788 | 0/2781 |
| ABSORB_REAL | 0/1610 | 0/1610 | 0/1610 | 0/1608 | 0/1610 | 0/1608 | 0/1610 | 0/1608 | 0/1610 | 0/1608 | 0/1610 | 0/1608 | 0/1610 | 0/1608 |
| TRUNCATED | 0/273 | 0/273 | 0/273 | 0/273 | 0/273 | 0/273 | 0/273 | 0/273 | 0/273 | 0/273 | 0/273 | 0/273 | 0/273 | 0/273 |
| JSON_DIALECT | 0/426 | 0/426 | 0/426 | 0/422 | 0/426 | 0/422 | 0/426 | 0/422 | 0/426 | 0/422 | 0/426 | 0/422 | 0/426 | 0/422 |
| DOUBLED_DELIM | 0/142 | 0/142 | 0/142 | 0/140 | 0/142 | 0/140 | 0/142 | 0/140 | 0/142 | 0/140 | 0/142 | 0/140 | 0/142 | 0/140 |
| LITERAL | 0/104 | 0/104 | 0/104 | 0/103 | 0/104 | 0/103 | 0/104 | 0/103 | 0/104 | 0/103 | 0/104 | 0/103 | 0/104 | 0/103 |
| NONL1_ACCEPTED | 0/828 | 0/828 | 0/828 | 0/820 | 0/828 | 0/820 | 0/828 | 0/820 | 0/828 | 0/820 | 0/828 | 0/820 | 0/828 | 0/820 |
| HANG | 0/13612 | 0/13612 | 0/13612 | 0/13335 | 0/13612 | 0/13335 | 0/13612 | 0/13335 | 0/13612 | 0/13335 | 0/13612 | 0/13335 | 0/13612 | 0/13335 |
| EXCEPTION | 0/13612 | 0/13612 | 0/13612 | 0/13335 | 0/13612 | 0/13335 | 0/13612 | 0/13335 | 0/13612 | 0/13335 | 0/13612 | 0/13335 | 0/13612 | 0/13335 |
| CTRL_IN_STRING | 0/802 | 0/802 | 0/802 | 0/791 | 0/802 | 0/791 | 0/802 | 0/791 | 0/802 | 0/791 | 0/802 | 0/791 | 0/802 | 0/791 |
| NESTED_BRACKET | 0/121 | 0/121 | 0/121 | 0/120 | 0/121 | 0/120 | 0/121 | 0/120 | 0/121 | 0/120 | 0/121 | 0/120 | 0/121 | 0/120 |
| TYPE_DRIFT | 0/5470 | 0/5470 | 0/5470 | 0/5318 | 0/5470 | 0/5318 | 0/5470 | 0/5318 | 0/5470 | 0/5318 | 0/5470 | 0/5318 | 0/5470 | 0/5318 |
| VALID_CORRUPTED | 0/5470 | 0/5470 | 0/5470 | 0/5318 | 0/5470 | 0/5318 | 0/5470 | 0/5318 | 0/5470 | 0/5318 | 0/5470 | 0/5318 | 0/5470 | 0/5318 |
| SPURIOUS_REJECT | 0/4668 | 0/4668 | 0/4668 | 0/4527 | 0/4668 | 0/4527 | 0/4668 | 0/4527 | 0/4668 | 0/4527 | 0/4668 | 0/4527 | 0/4668 | 0/4527 |
| NAME | 0/730 | 0/730 | 0/730 | 0/727 | 0/730 | 0/727 | 0/730 | 0/727 | 0/730 | 0/727 | 0/730 | 0/727 | 0/730 | 0/727 |

## Safety on every input

| target | inputs | hang | exception | skipped (stream > 3,000 chars) | max ms |
|---|---|---|---|---|---|
| gg.completion | 13612 | 0 | 0 | 0 | 25.19 |
| gg.extract | 13612 | 0 | 0 | 0 | 13.7 |
| gg.repair | 13612 | 0 | 0 | 0 | 23.93 |
| gg.stream | 13612 | 0 | 0 | 277 | 20.95 |
| gg.vllm019.server | 13612 | 0 | 0 | 0 | 26.86 |
| gg.vllm019.stream | 13612 | 0 | 0 | 277 | 35.79 |
| gg.vllm024.server | 13612 | 0 | 0 | 0 | 515.46 |
| gg.vllm024.stream | 13612 | 0 | 0 | 277 | 42.89 |
| gg.vllm031.server | 13612 | 0 | 0 | 0 | 647.81 |
| gg.vllm031.stream | 13612 | 0 | 0 | 277 | 30.2 |
| gg.vllm032.server | 13612 | 0 | 0 | 0 | 570.03 |
| gg.vllm032.stream | 13612 | 0 | 0 | 277 | 30.5 |
| gg.vllm033.server | 13612 | 0 | 0 | 0 | 657.72 |
| gg.vllm033.stream | 13612 | 0 | 0 | 277 | 33.55 |

## Real inputs (family R)

| target | real clean calls exact | real slips visible | real raw outputs: loud / text returned | strict calls returned | lost |
|---|---|---|---|---|---|
| gg.completion | 1500/1500 | 1610/1610 | 1058/1114 | 56 | 0 |
| gg.extract | 1500/1500 | 1610/1610 | 1056/1114 | 58 | 0 |
| gg.repair | 1500/1500 | 191/1610 | 1056/1114 | 58 | 0 |
| gg.stream | 1496/1496 | 1608/1608 | 974/1030 | 56 | 0 |
| gg.vllm019.server | 1500/1500 | 1610/1610 | 1056/1114 | 58 | 0 |
| gg.vllm019.stream | 1496/1496 | 1608/1608 | 974/1030 | 56 | 0 |
| gg.vllm024.server | 1500/1500 | 1610/1610 | 1056/1114 | 58 | 0 |
| gg.vllm024.stream | 1496/1496 | 1608/1608 | 974/1030 | 56 | 0 |
| gg.vllm031.server | 1500/1500 | 1610/1610 | 1056/1114 | 58 | 0 |
| gg.vllm031.stream | 1496/1496 | 1608/1608 | 974/1030 | 56 | 0 |
| gg.vllm032.server | 1500/1500 | 1610/1610 | 1056/1114 | 58 | 0 |
| gg.vllm032.stream | 1496/1496 | 1608/1608 | 974/1030 | 56 | 0 |
| gg.vllm033.server | 1500/1500 | 1610/1610 | 1056/1114 | 58 | 0 |
| gg.vllm033.stream | 1496/1496 | 1608/1608 | 974/1030 | 56 | 0 |

gg.repair (opt-in text repair) on the 1,610 real slips: {'EXACT': 1419, 'LOUD': 191} (EXACT = repaired to the intended call; LOUD = left loud; any other outcome would be a wrong repair).
