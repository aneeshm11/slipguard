# Conformance suite -- public subset

The full suite has 13,573 generated inputs and 39 minimal repros, 13,612 inputs in
all. This directory ships the 2,620 cases and 32 repros that can be public. The
rest is withheld:

| reason | cases dropped |
|---|---|
| re-assembled from the discovery-split logs (family R; its slips ship as release-package snippets instead) | 5,906 |
| on at least one runtime target: hang or timeout, uncaught exception, an extra (injected) call, or more than 1 s | 493 |
| control-token text inside a string, a nested bracket inside a string in an array, or a withheld edge-case subfamily | 343 |
| argument text from the discovery logs whose source repository is not known to be permissively licensed | 4,211 |

Repros withheld: the 7 security-relevant ones (call injection, turn-token and closing-token text in
strings, quadratic-time payloads, deep nesting, the nested-bracket hang). Their classes are described in `SECURITY.md`.

Files:
* `cases_public.jsonl` and `repros_public.jsonl`. One input per line, with the fields of the suite (`text`, `tools`,
  `intended`, `ref`, ...), plus:
  * `classes`: the suite's own predicates;
  * `outcomes`: the outcome on every runtime target that ran it;
  * `provenance`: `synthetic`, or argument text from permissively licensed records of the discovery logs.
* Tool declarations have no `description` fields; the parsers do not read them.
* `SUMMARY.json`: counts per rule and per family.

Every line passed the release privacy rules. Generator: `release/repo_build/build_conformance_public.py` (rules in
its docstring). Licence: CC BY 4.0. Argument text from public repositories keeps its upstream permissive licence.
