# The Gemma-4 "thinking off" switch is not honoured in multi-turn tool use (template gap)

Workstream A, 2026-11-04 18:00 UTC. For C (template hazards) and the paper. The template and token evidence below comes
from A's renders; the behavioural numbers are B's replays (PREREG_v2.2 §1). A's own measurement on 1,500 samples
(PREREG_v2.1 manipulation check M-v2.1) is in the section below.

## Finding
With `enable_thinking=false`, both Gemma-4 chat templates emit the closed empty thought `<|channel>thought\n<channel|>`
only when they open a **new** model turn. After a tool response, the model's turn continues, and the generation prompt
then appends nothing: the prompt ends at `<tool_response|>`. The flag's only remaining effect is that `<|think|>` is
dropped from the system turn. The model therefore still opens a thought in nearly every flag-off sample (B: 583/587
with the June template, 584/588 with July; median about 680 characters vs about 952 with thinking on). In an agent
loop, every request after the first tool call is in this state, so the shipped switch does not turn thinking off.

## Template lines
| | June / main-track template (md5 d6c5bd0d…) | July / current HF template (md5 f016bd4b…) |
|---|---|---|
| `<|think|>` in the system turn iff thinking is on | lines 179–184 | lines 186, 190–195 |
| generation prompt, new model turn: `<|turn>model\n`, then `<|channel>thought\n<channel|>` iff thinking is off | lines 347–352 (`ns.prev_message_type != 'tool_response' and != 'tool_call'`) | lines 381–386 |
| generation prompt after a tool response, thinking ON | nothing | lines 387–388: `<|channel>thought\n` (forced open) |
| generation prompt after a tool response, thinking OFF | nothing | nothing (there is no branch) |
| earlier thoughts re-rendered into history | lines 237–241, independent of the flag | lines 238–243, independent of the flag |

## Token and render evidence
Data: 300 real agent states (A's discovery gate contexts, logged histories, arm P0) rendered with both templates, from
`scripts/check_template_thinking_off.py` → `out/template_thinking_off_check.json`.

Token ids:

| token | id |
|---|---|
| `<|channel>` | 100 |
| `<channel|>` | 101 |
| `<|think|>` | 98 |
| `<tool_response|>` | 51 |
| `<|turn>` | 105 |

The closed empty thought tokenizes as **[100, 45518 'thought', 107 '\n', 101]**, two real control tokens around
"thought\n".

Prompt endings:

| template | thinking ON | thinking OFF |
|---|---|---|
| June | 300/300 end at `<tool_response|>` (id 51) | 300/300 end at `<tool_response|>`: identical to ON except `<|think|>` |
| July | 300/300 end at `<tool_response|><|channel>thought\n` (… 51, 100, 45518, 107) | 300/300 end at `<tool_response|>` (… 51) |

`<|think|>` appears in the system turn in 300/300 ON renders and 0/300 OFF renders.

Control: the same history truncated after the first user message, so the model starts a new turn. Here both templates
honour the flag:
- ON ends `<turn|>\n<|turn>model\n`, ids … 106, 107, 105, 4368 'model', 107;
- OFF ends `<|turn>model\n<|channel>thought\n<channel|>`, ids … 4368 'model', 107, 100, 45518, 107, 101.

The OFF renders still re-render the earlier logged thoughts into the history in 300/300 contexts (June).

## A's behavioural measurement (PREREG_v2.1 manipulation check, 300 gate contexts, 31B QAT-ct, June template, flag off)
From `out/v21_analysis.json` (1,500 samples):
* **The prompt ends at `<tool_response|>`** in every P0, P1, P6 and P8a context, and in 112 P5 contexts. The model opens
  a thought in **1,200/1,200** P0/P1/P6/P8a samples and in 112/112 of those P5 samples.
* **The template emits its closed thought** in 188 P5 contexts: P5 removes the last edit call, so the turn restarts.
  There the model re-opens a thought in **0/188**. The closed thought is honoured whenever the template emits it, so the
  gap is the missing branch alone.
* **Flag-off thoughts are shorter**: median 117.5 characters, vs 185 for thinking-on on the same contexts.

## Consequences
* A "thinking-off" run of an agent behaves as a thinking-on run without the system cue. Measurements labelled "no
  reasoning" that rely on the flag are mislabelled. PREREG_v2.2 reinterprets v2.1 accordingly: v2.1 tests the shipped
  flag, not the absence of reasoning.
* Thought-free generation requires appending `<|channel>thought\n<channel|>` after a tool response when thinking is off.
  This is one missing template branch, the mirror image of July's lines 387–388, and it is what PREREG_v2.2's arm set S
  does (`scripts/run_cond.py --cond S`, verified on 1,200 prompts: the last four tokens are 100, 45518, 107, 101).
* The same gap affects any serving stack that relies on the chat template, e.g. vLLM `chat_template_kwargs`.
