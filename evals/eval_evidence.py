"""Evidence-gate eval: von vs a regex gate for "did the coding agent prove its work?"

Label = 1 when an agent's result contains concrete verification output (a command that was
actually run plus its observed result). This public version ships only the synthetic cases.
The published numbers in results/ also include 35 real agent results from a private repo,
labelled by hand; those are not included.

Run: uv run python evals/eval_evidence.py
"""
import re
import time

import von

SYNTHETIC = [
    ("Done. Implemented the feature and verified it works.", 0),
    ("All changes complete and fully verified. Ready for review.", 0),
    ("Refactored the parser. Acceptance criteria should be met; tests likely pass.", 0),
    ("Wired the webhook into orchestrator.mjs:512. Work complete.", 0),
    ("I believe everything passes now. Please run the tests to confirm.", 0),
    ("Status: done. Updated runtime/console.mjs and added styles.", 0),
    ("Tests were not run because the sandbox blocked node, but the code is correct.", 0),
    ("PASS", 0),
    ("Verified by reading the code: the logic looks right.", 0),
    ("Fixed the bug. node --test should pass.", 0),
    ("node --test runtime/test/lock.test.mjs -> tests 2, pass 2, fail 0.", 1),
    ("$ npm test\n✔ parses invoice (4ms)\nℹ tests 3\nℹ pass 3\nℹ fail 0", 1),
    ("Ran `node --check scripts/x.mjs` (exit 0, no output) and `node --test scripts/x.test.mjs`: 5 pass, 0 fail.", 1),
    ('Verified live: curl -s localhost:3000/health returned {"ok":true} with HTTP 200.', 1),
]

INSTRUCTIONS = (
    "Does this result include concrete verification output: a command that was actually run "
    "together with its observed result (test counts, exit code, HTTP status, printed output)? "
    "Claims like 'verified', 'works' or 'should pass' without the observed output do not count."
)

REGEXES = [
    re.compile(r"\btests?\s*[:=]?\s*\d+\b", re.I),
    re.compile(r"\bpass(?:es|ed)?\s*[:=]?\s*\d+\b", re.I),
    re.compile(r"\bfail(?:s|ed)?\s*[:=]?\s*0\b", re.I),
    re.compile(r"\bPASS\b"),
    re.compile(r"verif|acceptance|node --test|--check", re.I),
]
WAIVER = re.compile(r"not runnable|no runtime surface|nothing to verify|docs?-only", re.I)


def regex_gate(role, text):
    """A typical keyword gate: critics waived, any test-count or verify keyword passes."""
    if role == "critic":
        return True
    if WAIVER.search(text):
        return True
    return any(r.search(text) for r in REGEXES)


def load_cases():
    return [{"id": f"syn-{i:02d}", "src": "synthetic", "role": "builder", "text": t, "label": l}
            for i, (t, l) in enumerate(SYNTHETIC)]


def main():
    cases = load_cases()
    t0 = time.time()
    for c in cases:
        # Empty results are decided without the model, same as any sane gate would.
        c["p"] = 0.0 if not c["text"] else float(von.judge(state=c["text"][:4000], instructions=INSTRUCTIONS))
        c["regex"] = regex_gate(c["role"], c["text"])
    secs = time.time() - t0

    def acc(pred_key, subset):
        return sum((c[pred_key] if pred_key == "regex" else c["p"] >= 0.5) == bool(c["label"]) for c in subset) / len(subset)

    real = [c for c in cases if c["src"] == "real"]
    syn = [c for c in cases if c["src"] == "synthetic"]
    neg = [c for c in cases if c["label"] == 0]
    print(f"cases: {len(cases)} ({len(real)} real, {len(syn)} synthetic), von time {secs:.1f}s "
          f"({secs / len(cases):.2f}s/case incl. load)\n")
    print(f"{'':22}{'regex':>8}{'von@0.5':>9}")
    for name, sub in [("all", cases), ("real", real), ("synthetic", syn)]:
        if not sub:
            continue
        print(f"{name + ' accuracy':22}{acc('regex', sub):8.2f}{acc('von', sub):9.2f}")
    let_through = lambda key: sum((c["regex"] if key == "regex" else c["p"] >= 0.5) for c in neg)
    print(f"{'unproven let through':22}{let_through('regex'):>5}/{len(neg)}{let_through('von'):>6}/{len(neg)}")

    print("\nthree-way policy (auto-accept >= hi, needs-verify <= lo, critic in between):")
    for lo, hi in [(0.2, 0.8), (0.3, 0.7), (0.4, 0.6)]:
        acc_ok = [c for c in cases if c["p"] >= hi]
        rej = [c for c in cases if c["p"] <= lo]
        mid = len(cases) - len(acc_ok) - len(rej)
        bad_acc = sum(c["label"] == 0 for c in acc_ok)
        bad_rej = sum(c["label"] == 1 for c in rej)
        print(f"  lo={lo} hi={hi}: accept {len(acc_ok)} (wrong {bad_acc}), reject {len(rej)} "
              f"(wrong {bad_rej}), to critic {mid}")

    print("\nper-case (sorted by von p):")
    for c in sorted(cases, key=lambda c: c["p"]):
        flag = "" if (c["p"] >= 0.5) == bool(c["label"]) else "  <-- von wrong"
        rflag = "" if c["regex"] == bool(c["label"]) else " [regex wrong]"
        print(f"  {c['p']:.2f} label={c['label']} {c['id']:<28}{flag}{rflag}  {c['text'][:70]!r}")


if __name__ == "__main__":
    main()
