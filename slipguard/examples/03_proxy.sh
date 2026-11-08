#!/bin/bash
# Task 3: intent-preserving repair (verify-then-repair) in front of a plain vLLM server -- the evaluated configuration.
set -e
MODEL=${MODEL:-google/gemma-4-31b-it}
MODEL_DIR=${MODEL_DIR:?set MODEL_DIR to the local model directory (tokenizer, chat_template.jinja, generation_config.json)}
vllm serve "$MODEL" --port 8000 &
slipguard proxy --backend http://127.0.0.1:8000/v1 --served "$MODEL" --model-dir "$MODEL_DIR" --logdir ./proxy-logs
# Agents: OpenAI base URL http://127.0.0.1:8420/fullp/v1   (cfgs: base, quar, ipd, fullp, ...)
