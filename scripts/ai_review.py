"""Ask an LLM (Google Gemini) to review a pull request diff.

The workflow saves the PR diff to a file, runs this script, and posts the
output as a PR comment. The review is advisory: it never blocks a merge,
and a human still decides. If no API key is configured the script exits
cleanly so the pipeline keeps working without it.

Usage:
    python scripts/ai_review.py <diff-file> <output-file>

Environment:
    GEMINI_API_KEY   - API key (GitHub secret); review is skipped if absent
    AI_MODEL         - model name from pipeline-config.yml
    MAX_DIFF_CHARS   - diffs longer than this are trimmed
    PR_TITLE         - pull request title, for context
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
MARKER = "<!-- ai-code-review -->"

INSTRUCTIONS = """You are a careful senior engineer reviewing a pull request.
Review ONLY the diff below. Report, in this order:
1. Bugs or logic errors
2. Security risks (secrets, injection, unsafe input handling, insecure config)
3. Missing tests for changed behaviour
4. Anything that would break the CI/CD pipeline or the Docker build

Rules:
- Be specific: name the file and quote the line.
- Give each finding a severity: High, Medium or Low.
- Do not comment on style or formatting; linters handle that.
- If you find nothing important, say so in one line. Do not invent problems.
- Keep the whole review under 300 words, in Markdown."""


def build_prompt(diff: str, title: str, max_chars: int) -> tuple[str, bool]:
    """Return the prompt and whether the diff had to be trimmed."""
    trimmed = len(diff) > max_chars
    if trimmed:
        diff = diff[:max_chars] + "\n... [diff trimmed for length]"
    prompt = f"{INSTRUCTIONS}\n\nPull request title: {title or '(none)'}\n\n```diff\n{diff}\n```"
    return prompt, trimmed


def extract_text(response: dict) -> str:
    try:
        parts = response["candidates"][0]["content"]["parts"]
    except (KeyError, IndexError, TypeError):
        raise ValueError(f"unexpected response from the model: {str(response)[:300]}") from None
    text = "".join(p.get("text", "") for p in parts).strip()
    if not text:
        raise ValueError("the model returned an empty review")
    return text


def call_model(prompt: str, model: str, api_key: str) -> str:
    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.2},
    }).encode()
    req = urllib.request.Request(ENDPOINT.format(model=model), data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("x-goog-api-key", api_key)
    with urllib.request.urlopen(req, timeout=120) as resp:
        return extract_text(json.loads(resp.read().decode()))


def format_comment(review: str, model: str, trimmed: bool) -> str:
    note = "\n\n_Note: the diff was long, so only the first part was reviewed._" if trimmed else ""
    return (
        f"{MARKER}\n### AI code review ({model})\n\n{review}{note}\n\n"
        "_Automated and advisory only. A human reviewer makes the final call._"
    )


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: ai_review.py <diff-file> <output-file>")
        return 2
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        print("::notice::GEMINI_API_KEY is not set, so the AI review was skipped.")
        return 0

    diff = open(argv[1], encoding="utf-8", errors="replace").read()
    if not diff.strip():
        print("Empty diff, nothing to review.")
        return 0

    model = os.environ.get("AI_MODEL", "gemini-2.5-flash")
    prompt, trimmed = build_prompt(diff, os.environ.get("PR_TITLE", ""), int(os.environ.get("MAX_DIFF_CHARS", "60000")))
    try:
        review = call_model(prompt, model, api_key)
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        # Advisory stage: report the problem but never fail the pipeline over it.
        print(f"::warning title=AI review unavailable::{exc}")
        return 0

    with open(argv[2], "w", encoding="utf-8") as fh:
        fh.write(format_comment(review, model, trimmed))
    print("Review written.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
