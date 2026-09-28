# von-shadow

**Run an open Jev-style decision model on your laptop, next to Claude Code, in shadow mode.**
It tags your prompts in the background and logs what it would have decided. Nothing acts on
the tags. Includes the eval harness I used to decide whether it's ready to act yet (it isn't).

## Why

In September 2026 TypeSafe AI released [Jev](https://en.wikipedia.org/wiki/Jev_(AI_model)), a
"System One" model: it doesn't chat, it answers typed questions (yes/no, pick one, rate)
with calibrated probabilities, fast and cheap. Jev itself is closed and API-only. Open copies
followed within days. I wanted one running **locally** on an 8 GB M1 for the small, repetitive
decisions around my coding-agent setup: *was that message a correction? did the agent prove
its work? does this note replace that one?*

This repo uses [von](https://github.com/wfzyx/von) (Apache-2.0, 395M ModernBERT encoder,
wire-compatible with Jev's `/v1/systemone` API). It fits in 8 GB and answers in ~0.3 s.

## What shadow mode does

```
you type a prompt ──► UserPromptSubmit hook ──► von-shadow log   (queue, ~ms, no model)
session ends     ──► Stop hook              ──► von-shadow tag --background
                                                 └─ loads von, tags the queue, exits
you, later       ──► von-shadow label        (mark tags right/wrong)
                 ──► von-shadow report       (tag counts, confidence, accuracy vs you)
```

Each prompt gets one of: `correction`, `praise`, `capability_gap`, `neutral`, with a
probability for each. The model only loads when there's a queue to work through, so it doesn't
hold ~1.2 GB of RAM between sessions. The labels you add become the training set for a
fine-tune later, which is the realistic path to making this good enough to act on.

## Results so far (Apple M1, 8 GB, von 1.3)

Full detail: [`results/2026-09-29-apple-m1-8gb.md`](results/2026-09-29-apple-m1-8gb.md).

| Task | von | Takeaway |
|---|---|---|
| Did the agent prove its work? (`noul`, 49 cases: 35 real, 14 synthetic) | 0.53 accuracy vs 0.78 for a keyword regex | worse than regex; fooled by the word "verified" |
| Same, phrased as a `choice` (10 synthetic) | 0.80 | phrasing matters a lot |
| Prompt feedback tagging (12, English + German) | 0.75 | usable signal, but 3 misses at ~0.9 confidence |
| Why did an agent run fail? (9) | 0.56 | worse than plain substring matching |
| How does note B relate to note A? (7) | 0.43 (0.57 on the public, anonymised wording) | not usable: every answer low confidence |

**Bottom line:** fast and cheap enough to run all the time on a laptop, but on my data its
confidence isn't trustworthy yet. So it runs in shadow mode, collects labels, and doesn't
decide anything. Small sample sizes: treat these as a smoke test, not a benchmark.

## Install

Needs macOS/Linux, Python 3.12 or 3.13 (torch has no 3.14 wheels yet) and
[uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/Hagetino/von-shadow && cd von-shadow
uv sync                                         # ~750 MB (torch + transformers)
uv run von-shadow report                        # sanity check
```

The first `tag` run downloads the von weights from Hugging Face (~1.5 GB with the base model).
von loads them with `torch.load(..., weights_only=True)`, so the pickle can't run code.

### Hook it into Claude Code

Merge [`hooks/claude-code-settings.json`](hooks/claude-code-settings.json) into
`~/.claude/settings.json` and replace `/path/to/von-shadow` with your clone path. Both hooks
exit 0 no matter what, so a broken install can't block a prompt.

## Use

```bash
uv run von-shadow report     # queued / tagged / labelled, confidence bands, accuracy
uv run von-shadow label      # Enter = von was right, 1-4 = correct tag, s = skip, q = quit
uv run von-shadow tag        # tag the queue now instead of waiting for session end
```

Data lives in `~/.local/share/von-shadow/` (override with `VON_SHADOW_HOME`). It contains
your prompt text, stays on your machine, and is never inside the repo.

## Re-run the evals

```bash
uv run python evals/probe_tasks.py      # short intent-style tasks
uv run python evals/eval_evidence.py    # evidence gate vs regex (synthetic cases only)
```

Swap in a different Jev-compatible model and re-run to compare. Kev
([jaredpalmer/kev](https://github.com/jaredpalmer/kev)) serves the same API but its useful
sizes need a 32 GB Mac.

## Related

- [recall](https://github.com/Hagetino/recall): local semantic search + graph over markdown
  agent memory
- [hone](https://github.com/Hagetino/hone): retrospectives on your Claude Code sessions

## License

MIT. von is Apache-2.0 and installed as a dependency, not vendored.
