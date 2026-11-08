# slipguard conformance (C's suite, C's judging rules)

54448 results; targets: gg.ref, gg.sgl523.detector, gg.sgl523.server, gg.sgl523.stream.

## Table D: per bug class, worst verdict over the class's minimal repros (✓ pass, ~ policy, ✗ defect)

| class | gg.ref | gg.sgl523.detector | gg.sgl523.server | gg.sgl523.stream |
|---|---|---|---|---|
| E1 closer_slip (silent absorption after a look-alike closer) | ✓ | ✓ | ✓ | ✓ |
| E2 key_restart (closer, comma, newline, same key) | ✓ | ✓ | ✓ | ✓ |
| E3 opener_drift ('=', JSON/Python quotes, bare text) | ✓ | ✓ | ✓ | ✓ |
| E4 key_drift (quotes on the key side) | ✓ | ✓ | ✓ | ✓ |
| E5 unparsed_call (header drift, unclosed call) | ✓ | ✓ | ✓ | ✓ |
| C2 truncated call returned/executed | ✓ | ✓ | ✓ | ✓ |
| C4 doubled delimiter -> empty value | ✓ | ✓ | ✓ | ✓ |
| C5 stray delimiter after number kept | ✓ | ✓ | ✓ | ✓ |
| C6 control token in string: truncation / deletion / call injection | ✓ | ✓ | ✓ | ✓ |
| C7 infinite loop + memory growth | ✓ | ✓ | ✓ | ✓ |
| C8 quadratic parse time | ✓ | ✓ | ✓ | · |
| C9 uncaught RecursionError (deep nesting) | ✓ | ✓ | ✓ | · |
| C10 type drift on valid input | ✓ | ✓ | ✓ | ✓ |
| C11 non-L1 literal coerced/stringified | ✓ | ✓ | ✓ | ✓ |
| C12 valid names/keys/whitespace mishandled | ✓ | ✓ | ✓ | ✓ |
| C13 multiple calls / streaming call merge | ✓ | ✓ | ✓ | ✓ |

## Table F: per-class presence over the fuzz corpus (k/n inputs where the defect shows)

| class | gg.ref | gg.sgl523.detector | gg.sgl523.server | gg.sgl523.stream |
|---|---|---|---|---|
| ABSORB | 0/2788 | 0/2788 | 0/2788 | 0/2781 |
| ABSORB_REAL | 0/1610 | 0/1610 | 0/1610 | 0/1608 |
| TRUNCATED | 0/273 | 0/273 | 0/273 | 0/273 |
| JSON_DIALECT | 0/426 | 0/426 | 0/426 | 0/422 |
| DOUBLED_DELIM | 0/142 | 0/142 | 0/142 | 0/140 |
| LITERAL | 0/104 | 0/104 | 0/104 | 0/103 |
| NONL1_ACCEPTED | 0/828 | 0/828 | 0/828 | 0/820 |
| HANG | 0/13612 | 0/13612 | 0/13612 | 0/13335 |
| EXCEPTION | 0/13612 | 0/13612 | 0/13612 | 0/13335 |
| CTRL_IN_STRING | 0/802 | 4/802 | 159/802 | 11/791 |
| NESTED_BRACKET | 0/121 | 0/121 | 0/121 | 0/120 |
| TYPE_DRIFT | 0/5470 | 0/5470 | 0/5470 | 0/5318 |
| VALID_CORRUPTED | 0/5470 | 0/5470 | 116/5470 | 7/5318 |
| SPURIOUS_REJECT | 0/4668 | 13/4668 | 13/4668 | 13/4527 |
| NAME | 0/730 | 2/730 | 42/730 | 2/727 |

## Safety on every input

| target | inputs | hang | exception | skipped (stream > 3,000 chars) | max ms |
|---|---|---|---|---|---|
| gg.ref | 13612 | 0 | 0 | 0 | 18.17 |
| gg.sgl523.detector | 13612 | 0 | 0 | 0 | 127.87 |
| gg.sgl523.server | 13612 | 0 | 0 | 0 | 132.03 |
| gg.sgl523.stream | 13612 | 0 | 0 | 277 | 17.09 |

## Real inputs (family R)

| target | real clean calls exact | real slips visible | real raw outputs: loud / text returned | strict calls returned | lost |
|---|---|---|---|---|---|
| gg.ref | 1500/1500 | 1610/1610 | 1058/1114 | 56 | 0 |
| gg.sgl523.detector | 1500/1500 | 1610/1610 | 1070/1114 | 44 | 0 |
| gg.sgl523.server | 1500/1500 | 1610/1610 | 1070/1114 | 44 | 0 |
| gg.sgl523.stream | 1496/1496 | 1608/1608 | 980/1030 | 42 | 8 |
