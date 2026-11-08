# EXPLORATORY: why the registered soak failed (PI, 2026-11-06 19:20 UTC; after the frozen analysis ran once)

**The registered verdict is final:** `FAIL: K-a, K-b` (experiments/soak/out/soak_analysis.json, frozen soak_analyze.py
f4460929). This note characterises the failure. It does not re-test anything.

## What passed
| gate | measure | result |
|---|---|---|
| K-c (latency, non-repaired proxy requests vs direct) | median TTLB ratio | 0.96 |
| | p99 ratio | 0.77 |
| K-d (memory growth, minutes 10–12 vs the last 2) | proxy | +21.8 MB |
| | stock server | +5.7 MB |
| | plugin server | +2.4 MB |
| K-e (no protocol-corrupt deliveries) | proxy | 0 leak/non-JSON in 473 calls |
| | plugin | 0 protocol-corrupt in 918 calls |
| | stock vLLM, same load | 1 leak + 1 missing in 451 calls |
| Availability | bad health samples | 0 of 752 (K1 377 + K2 375); no crash or restart |

## What failed, and why
K-a counted every 600-s client timeout as a hang; K-b's error rate counts them too. Timeouts by route and mode
(ReadTimeout = no bytes for 600 s):

| route | non-streamed | streamed |
|---|---|---|
| stock vLLM (K1 direct) | 5 / 232 | 0 / 235 |
| slipguard proxy (K1) | 4 / 230 | 4 / 255 |
| slipguard plugin server (K2) | 9 / 468 | 7 / 494 (+1 transport ReadError) |

- **Non-streamed: the same rate on every route (≈2%).** The load saturated the server.
  - Throughput: mean 19 requests running and up to 43 waiting; GPU KV cache up to 94% (PNC contexts average ~16k
    tokens); aggregate generation about 63 tokens/s, i.e. ~3 tokens/s per request.
  - At that rate a 2,048-token generation takes about 11 min, beyond the 600-s timeout.
  - This is a property of the soak load, not of slipguard: stock vLLM timed out at the same rate.
- **Streamed: only slipguard timed out.** Both slipguard paths withhold output until a tool call is verified.
  - The proxy (IPD) needs the whole turn before it can decide.
  - The strict plugin delivers a call only once its text is strictly valid.
  - With ~3 tokens/s, a long turn can produce no bytes for more than 600 s. Stock streaming sends tokens as they are
    generated, so it never went silent that long.
- **Practical consequence (goes to LIMITATIONS and USER_GUIDE).** Under heavy load, clients of slipguard's streaming
  endpoints see a longer time-to-first-byte for tool-call turns. They must not use a short read timeout.
  - At normal load (tens of tokens/s per request) a 2,048-token turn takes about 1–2 minutes.
  - Possible mitigation for a later release: forward the thought or content tokens that precede a tool call, or send
    keep-alive frames.

## Design note (for the record)
The registered gates assumed that a stock server under this load would not time out. It did (5 / 467). Gates relative
to the stock route (as K-b is for the proxy) would have isolated slipguard's effect. K-a and K-b's absolute plugin
bound did not. The registration is not changed; the verdict stands as FAIL.
