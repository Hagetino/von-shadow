"""Probe: von on short, intent-style decisions a coding-agent setup could offload.

Hand-labelled examples for session-retrospective turn tagging (incl. Denglisch), failure triage, recall link
typing, and the evidence gate rephrased as a choice. Small n: a smoke signal, not a benchmark.

Run: uv run python evals/probe_tasks.py
"""
import von

SUITES = {
    "turn tagging": {
        "instructions": "What kind of feedback is the user giving the AI assistant in this message?",
        "choices": {
            "correction": "The user says the assistant did something wrong or should do it differently",
            "praise": "The user approves of or confirms what the assistant did",
            "capability_gap": "The user wants something the assistant could not do",
            "neutral": "A plain request or question with no feedback about the assistant",
        },
        "cases": [
            ("no, don't use em dashes in outreach, it sounds like AI", "correction"),
            ("stop adding the magnetic hover, I told you I hate the wobble", "correction"),
            ("why did you invent a speaker name, only use what I gave you", "correction"),
            ("nee, das ist falsch, mach das bitte ohne den Institutsnamen", "correction"),
            ("perfect, that's exactly what I wanted", "praise"),
            ("yes that works great, keep doing it like this", "praise"),
            ("passt, genau so", "praise"),
            ("can you send this on WhatsApp? oh you can't connect to it", "capability_gap"),
            ("I wish you could just post this to LinkedIn directly", "capability_gap"),
            ("feel free to push all", "neutral"),
            ("what was open still?", "neutral"),
            ("next lets work on the nova site hero section", "neutral"),
        ],
    },
    "failure triage": {
        "instructions": "What caused this CLI agent run to fail?",
        "choices": {
            "ratelimit": "Usage limit, quota, rate limit or too many requests",
            "auth": "Login, token, credentials or permission to the account",
            "context": "Prompt or conversation too long for the model's context window",
            "sandbox": "Blocked by the sandbox, file permissions or approval settings",
            "code_error": "A bug, exception or failing test in the code being run",
        },
        "cases": [
            ("You've hit your usage limit. Upgrade to Pro or try again at 3:00 PM.", "ratelimit"),
            ("Error 429: Too Many Requests. Retry after 60s.", "ratelimit"),
            ("Invalid API key · Please run /login", "auth"),
            ("OAuth token has expired. Please re-authenticate.", "auth"),
            ("prompt is too long: 212345 tokens > 200000 maximum", "context"),
            ("patch rejected: writing outside of the project; rejected by user approval settings", "sandbox"),
            ("EACCES: permission denied, open '/home/dev/project/notes/INDEX.md'", "sandbox"),
            ("TypeError: Cannot read properties of undefined (reading 'status') at orchestrator.mjs:665", "code_error"),
            ("✖ refill validation (3ms)\nℹ tests 4\nℹ pass 3\nℹ fail 1", "code_error"),
        ],
    },
    "note relation typing": {
        "instructions": "How does note B relate to note A?",
        "choices": {
            "supersedes": "B replaces or overrides what A says; A is now outdated",
            "supports": "B agrees with or adds evidence for A",
            "contradicts": "B disagrees with A but neither is clearly newer",
            "unrelated": "B is about a different topic",
        },
        "cases": [
            ("A: Shared memory runs on a Neo4j knowledge graph with local LLM extraction. "
             "B: 2026-09-27: the graph is parked; shared memory is the markdown decisions log.", "supersedes"),
            ("A: Intake for the club opens in November. B: Update: intake moved to 1 October.", "supersedes"),
            ("A: Outreach copy avoids em dashes. B: Keep peer outreach casual and human, no machine phrasing.", "supports"),
            ("A: Commit with the work email in work repos. B: Git identity fixed: work repos now use the work address.", "supports"),
            ("A: Use magnetic cursor-tracking hover on buttons. B: The user rejects magnetic hover; use scale or shadow.", "contradicts"),
            ("A: Sales prospects are checked against each company imprint. B: The laptop has 8 GB RAM.", "unrelated"),
            ("A: The club site uses GSAP and Lenis for motion. B: Commission estimate formula for hotel refunds.", "unrelated"),
        ],
    },
    "evidence as choice": {
        "instructions": "What kind of proof does this agent result give that the work is done?",
        "choices": {
            "observed_output": "Shows output from a command that was actually run: test counts, exit codes, printed results",
            "claim_only": "Only says it is done, verified or working, without any observed output",
            "no_result": "Blocked, empty, or reports that the work could not be done",
        },
        "cases": [
            ("Done. Implemented the feature and verified it works.", "claim_only"),
            ("All changes complete and fully verified. Ready for review.", "claim_only"),
            ("Wired the webhook into orchestrator.mjs:512. Work complete.", "claim_only"),
            ("Verified by reading the code: the logic looks right.", "claim_only"),
            ("node --test runtime/test/lock.test.mjs -> tests 2, pass 2, fail 0.", "observed_output"),
            ("$ npm test\n✔ parses invoice (4ms)\nℹ tests 3\nℹ pass 3\nℹ fail 0", "observed_output"),
            ('curl -s localhost:3000/health returned {"ok":true} with HTTP 200.', "observed_output"),
            ("Ran node --check (exit 0) and node --test: 5 pass, 0 fail.", "observed_output"),
            ("status: blocked. apply_patch was rejected; the directory is not writable.", "no_result"),
            ("Tests were not run because the sandbox blocked node.", "no_result"),
        ],
    },
}


def main():
    for name, s in SUITES.items():
        right, confident, confident_right = 0, 0, 0
        misses = []
        for text, gold in s["cases"]:
            r = von.decide(state=text, choices=s["choices"], instructions=s["instructions"])
            ok = r.choice == gold
            right += ok
            if r.confidence >= 0.6:
                confident += 1
                confident_right += ok
            if not ok:
                misses.append(f"    got {r.choice} ({r.confidence:.2f}) want {gold}: {text[:60]!r}")
        n = len(s["cases"])
        chance = 1 / len(s["choices"])
        print(f"{name:20} acc {right}/{n} = {right / n:.2f} (chance {chance:.2f}) | "
              f"conf>=0.6: {confident} cases, {confident_right} right")
        print("\n".join(misses))


if __name__ == "__main__":
    main()
