#!/bin/bash
# Task 1: serve Gemma 4 with slipguard's strict tool parser and string-aware reasoning parser (no code change).
# Optional: the patched chat template (thinking-off closure + control-token neutralization).
set -e
MODEL=${MODEL:-google/gemma-4-31b-it}
P=$(slipguard plugin-path vllm)
vllm serve "$MODEL" --port 8000 --enable-auto-tool-choice \
  --tool-parser-plugin "$P" --tool-call-parser gemma4_strict \
  --reasoning-parser-plugin "$P" --reasoning-parser gemma4_strict \
  --chat-template "$(slipguard template-path)"
# Variants: --tool-call-parser gemma4_strict_schema (also enforce the request's tool schema)
#           --tool-call-parser gemma4_strict_repair (+ one text-only repair, ids end in -ggrepaired)
