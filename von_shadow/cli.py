"""von-shadow: run an open Jev-style decision model next to Claude Code, in shadow mode.

Commands
  log      Hook entry point (UserPromptSubmit). Reads the hook JSON on stdin and appends the
           prompt to the queue. No model load, returns in milliseconds, never blocks a prompt.
  tag      Tags every queued prompt with von, appends to predictions.jsonl, clears the queue.
           Run it from a SessionEnd hook with --background so it never holds RAM between sessions.
  label    Walk through untagged-by-you predictions and mark them right/wrong. Builds the
           labelled set a later fine-tune needs.
  report   Counts per tag, confidence spread, and accuracy against your labels.

Nothing here acts on a prediction. Tags are only logged.
"""
import argparse
import fcntl
import json
import os
import subprocess
import sys
import time
from pathlib import Path

HOME = Path(os.environ.get("VON_SHADOW_HOME", Path.home() / ".local/share/von-shadow"))
QUEUE = HOME / "queue.jsonl"
PREDICTIONS = HOME / "predictions.jsonl"
LABELS = HOME / "labels.jsonl"
LOCK = HOME / "tag.lock"
MAX_CHARS = 1000

INSTRUCTIONS = "What kind of feedback is the user giving the AI assistant in this message?"
CHOICES = {
    "correction": "The user says the assistant did something wrong or should do it differently",
    "praise": "The user approves of or confirms what the assistant did",
    "capability_gap": "The user wants something the assistant could not do",
    "neutral": "A plain request or question with no feedback about the assistant",
}


def _append(path, record):
    HOME.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _read(path):
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return out


def cmd_log(_args):
    # A hook must never break the prompt: swallow everything, always exit 0.
    try:
        event = json.load(sys.stdin)
        prompt = (event.get("prompt") or "").strip()
        if prompt:
            _append(QUEUE, {
                "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "session": event.get("session_id", ""),
                "text": prompt[:MAX_CHARS],
            })
    except Exception:
        pass
    return 0


def cmd_tag(args):
    if args.background:
        # Detach so the SessionEnd hook returns immediately.
        subprocess.Popen([sys.executable, "-m", "von_shadow.cli", "tag"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         start_new_session=True)
        return 0
    HOME.mkdir(parents=True, exist_ok=True)
    with open(LOCK, "w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return 0  # another tag run is already working the queue
        # Claim the queue atomically so prompts logged during tagging are kept for next run.
        if not QUEUE.exists():
            return 0
        work = QUEUE.with_suffix(".tagging")
        QUEUE.rename(work)
        items = _read(work)
        if not items:
            work.unlink()
            return 0
        # von resolves its checkpoint (and a `von calibrate` result) relative to the working
        # directory. Hooks run from whatever project is open, so pin it to HOME.
        os.chdir(HOME)
        import von  # heavy import, only when there is work

        t0 = time.time()
        for it in items:
            r = von.decide(state=it["text"], choices=CHOICES, instructions=INSTRUCTIONS)
            _append(PREDICTIONS, {**it, "tag": r.choice, "confidence": round(r.confidence, 3),
                                  "probabilities": {k: round(v, 3) for k, v in r.probabilities.items()},
                                  "model": "von-1.3.4+cal", "tagged_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
        work.unlink()
        print(f"tagged {len(items)} prompts in {time.time() - t0:.1f}s -> {PREDICTIONS}")
    return 0


def cmd_label(_args):
    done = {(l["ts"], l["text"]) for l in _read(LABELS)}
    todo = [p for p in _read(PREDICTIONS) if (p["ts"], p["text"]) not in done]
    if not todo:
        print("nothing to label")
        return 0
    keys = list(CHOICES)
    print("Enter = von was right · 1-4 = the right tag · s = skip · q = quit")
    print("  " + "  ".join(f"{i + 1}={k}" for i, k in enumerate(keys)))
    for p in todo:
        print(f"\n{p['text'][:300]!r}\n  von: {p['tag']} ({p['confidence']:.2f})")
        ans = input("> ").strip().lower()
        if ans == "q":
            break
        if ans == "s":
            continue
        gold = p["tag"] if ans == "" else keys[int(ans) - 1] if ans in ("1", "2", "3", "4") else None
        if gold:
            _append(LABELS, {"ts": p["ts"], "text": p["text"], "gold": gold, "von": p["tag"],
                             "confidence": p["confidence"]})
    return 0


def cmd_report(_args):
    preds = _read(PREDICTIONS)
    labels = _read(LABELS)
    print(f"queued: {len(_read(QUEUE))}   tagged: {len(preds)}   labelled by you: {len(labels)}")
    if preds:
        counts = {}
        for p in preds:
            counts[p["tag"]] = counts.get(p["tag"], 0) + 1
        print("tags: " + ", ".join(f"{k} {v}" for k, v in sorted(counts.items(), key=lambda x: -x[1])))
        bands = [(0, .4), (.4, .6), (.6, .8), (.8, 1.01)]
        print("confidence: " + ", ".join(
            f"{lo:.1f}-{min(hi, 1):.1f}: {sum(lo <= p['confidence'] < hi for p in preds)}" for lo, hi in bands))
    if labels:
        right = sum(l["gold"] == l["von"] for l in labels)
        print(f"accuracy vs your labels: {right}/{len(labels)} = {right / len(labels):.2f}")
        for lo, hi in [(0, .6), (.6, .8), (.8, 1.01)]:
            band = [l for l in labels if lo <= l["confidence"] < hi]
            if band:
                ok = sum(l["gold"] == l["von"] for l in band)
                print(f"  conf {lo:.1f}-{min(hi, 1):.1f}: {ok}/{len(band)} right")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="von-shadow", description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("log", help="hook: queue the prompt from stdin JSON")
    t = sub.add_parser("tag", help="tag queued prompts with von")
    t.add_argument("--background", action="store_true", help="detach and return immediately")
    sub.add_parser("label", help="mark predictions right/wrong")
    sub.add_parser("report", help="summary and accuracy")
    args = ap.parse_args(argv)
    return {"log": cmd_log, "tag": cmd_tag, "label": cmd_label, "report": cmd_report}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
