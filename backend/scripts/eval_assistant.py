"""Runs the fixed question set in evals/questions.jsonl through the assistant with Gemma loaded, and writes a report
with every answer in full: automatic checks catch the obvious failures, a person reads the rest.

Stop the server first: one Gemma engine at a time on the laptop.
Usage (from backend/): .venv/bin/python -m scripts.eval_assistant ../docs/evals/assistant_v0.2.md
"""

import json
import re
import sys
import time
from pathlib import Path

from sca.app import Config
from sca.assistant import Assistant

BACKEND = Path(__file__).resolve().parents[1]
DEVANAGARI = re.compile(r"[ऀ-ॿ]")
LETTERS = re.compile(r"[A-Za-zऀ-ॿ]")
REPEAT = re.compile(r"(.{4,}?)\1{3,}")  # the same 4+ characters four times in a row: a decoding loop


def script_ok(text: str, lang: str) -> bool:
    """English answers are in Latin letters; Hindi and Marathi answers mostly in Devanagari."""
    letters = LETTERS.findall(text)
    share = len(DEVANAGARI.findall(text)) / max(len(letters), 1)
    return share < 0.1 if lang == "en" else share > 0.6


def checks(case: dict, answer) -> dict[str, bool]:
    text = answer.text.lower()
    return {
        "mode": answer.mode == case["mode"],
        "language": script_ok(answer.text, case["lang"]),
        "includes": any(word.lower() in text for word in case.get("include_any", [])) if case.get("include_any") else True,
        "excludes": not any(word.lower() in text for word in case.get("exclude", [])),
        "no_loop": REPEAT.search(answer.text) is None,
    }


def main(out: Path) -> None:
    config = Config.from_env()
    cases = [json.loads(line) for line in (BACKEND / "evals" / "questions.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    assistant = Assistant(config.notes_path, "Satt Chitt Anand Yoga", "Ramit ji")
    start = time.perf_counter()
    assistant.load_gemma(config.model_path, config.gemma, config.cache_dir)
    if assistant.gemma is None:
        sys.exit(f"Gemma did not load: {assistant.status}")
    load_s = time.perf_counter() - start
    assistant.ask("Warm-up question about breathing.", "en")  # the first call compiles; time the rest warm

    rows, details = [], []
    for case in cases:
        answer = assistant.ask(case["question"], case["lang"])
        result = checks(case, answer)
        passed = all(result.values())
        rows.append((case, answer, result, passed))
        failed = ", ".join(k for k, v in result.items() if not v)
        details.append(
            f"### {case['id']} {'✅' if passed else '❌ ' + failed}\n\n"
            f"**Q ({case['lang']}):** {case['question']}\n\n"
            f"**Mode:** {answer.mode} · **Sources:** {', '.join(answer.sources) or 'none'} · **Time:** {answer.latency_s:.1f} s\n\n"
            + "\n".join(f"> {line}" if line else ">" for line in answer.text.splitlines())
            + "\n"
        )

    gemma_times = sorted(a.latency_s for _, a, _, _ in rows if a.mode == "gemma")
    median = gemma_times[len(gemma_times) // 2] if gemma_times else float("nan")
    passed = sum(1 for *_, ok in rows if ok)
    by_lang = {lang: f"{sum(1 for c, *_, ok in rows if ok and c['lang'] == lang)}/{sum(1 for c, *_ in rows if c['lang'] == lang)}" for lang in ("en", "hi", "mr")}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        f"# Assistant evaluation: {out.stem}\n\n"
        f"- **Model:** {assistant.gemma.name}, greedy decoding, on {config.gemma.upper()}; load {load_s:.0f} s\n"
        f"- **Notes:** `backend/knowledge/yoga_health.md`; **questions:** `backend/evals/questions.jsonl`\n"
        f"- **Passed the automatic checks:** {passed}/{len(rows)} (English {by_lang['en']}, Hindi {by_lang['hi']}, Marathi {by_lang['mr']})\n"
        f"- **Gemma answer time, warm:** median {median:.1f} s, max {max(gemma_times):.1f} s (n={len(gemma_times)})\n\n"
        "The automatic checks are coarse: the right path (Gemma or the fixed urgent reply), the right script for the\n"
        "language, a required word (\"doctor\", \"112\"…), no forbidden phrase, and no word looping. They catch obvious\n"
        "failures only.\n"
        "Read every answer below before trusting a pass.\n\n"
        "| id | lang | mode | language | includes | excludes | no loop | time |\n|---|---|---|---|---|---|---|---|\n"
        + "".join(
            f"| {c['id']} | {c['lang']} | {'✓' if r['mode'] else '✗'} | {'✓' if r['language'] else '✗'} | "
            f"{'✓' if r['includes'] else '✗'} | {'✓' if r['excludes'] else '✗'} | {'✓' if r['no_loop'] else '✗'} | {a.latency_s:.1f} s |\n"
            for c, a, r, _ in rows
        )
        + "\n## Answers\n\n" + "\n".join(details),
        encoding="utf-8",
    )
    print(f"{passed}/{len(rows)} passed; report: {out}")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
