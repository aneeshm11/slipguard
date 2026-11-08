# Security

## What is withheld, and how to get it

Four of the parser defect classes we found are security-relevant:
- tool-call injection from a string argument;
- a quadratic-time parse that blocks the server's event loop;
- an uncaught recursion error on deeply nested input;
- an infinite loop with unbounded memory growth.

Some of them are unpatched in current vLLM and SGLang, and one can stall the vLLM 0.19.1 server used by the challenge's
agent harness.

**This release does not contain their exact inputs or reproduction reports**, because they could be used to exploit
ongoing competitions built on Gemma. We have not filed them publicly. We ask the challenge organizers to contact us
for access. Everything else that can be public is released: the conformance suite's other classes, all results
and the code that protects against these classes. Some further inputs are withheld for licence or provenance reasons,
not for security: discovery-derived and non-permissive conformance cases (`conformance/README.md`), files that freeze
manifests list (`WITHHELD.json`, with their hashes), and the end-to-end run records (`REPRODUCE.md`, Level 1).

Related public reports by others: SGLang issue #42791 (a hang on a stray `]` in an array argument) and vLLM PR #41991
(an infinite loop and array-boundary issues in the Gemma 4 tool parser).

## The classes (described, not reproduced)

- **Untrusted data can carry protocol structure.** Tool results, files and web pages can contain the *text* of Gemma 4
  control tokens. The official template and tokenizer turn that text into real control tokens.
  - `slipguard.history` and the patched template make such text inert, reversibly.
  - Where you control tokenization, prefer the token-level form: special-token parsing disabled for untrusted spans.
- **Resynchronizing after a malformed call can execute data.** A parser that resumes after a broken call can be steered
  into executing a "call" that was really part of a string argument of the broken call.
  - slipguard delivers calls only up to the first protocol error and returns the rest as content, never as calls. This
    holds identically for streaming and non-streaming parsing.
- **Unbounded work.** Some built-in parsers loop forever, recurse without bound or take quadratic time on crafted
  or unlucky inputs.
  - slipguard's parser is linear in the input for any chunking, and it bounds nesting without recursion.
  - Inside vLLM 0.19's streaming loop, total time is still super-linear for any parser; see `LIMITATIONS.md` §8.
- **Strings are opaque.** Inside `<|"|>...<|"|>`, every control token is content.

## What slipguard does not protect against

- Slips in argument *names*. The proxy passes them through; the strict parser refuses them.
- A model that emits a *valid* but harmful call. slipguard checks protocol syntax and schema, not intent.
- Runtimes or parsers other than the ones tested (vLLM 0.19.1, 0.24.0, 0.31–0.33).

## Reporting a problem in slipguard

Please report it privately through Kaggle or a private GitHub security advisory on this repository, not in a public
issue. We will acknowledge it and fix it in the open once a fix exists.
