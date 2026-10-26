"""Ask an LLM to review a pull request diff (Groq or Google Gemini).

The workflow saves the PR diff to a file, runs this script, and posts the
output as a PR comment. The review is advisory: it never blocks a merge,
and a human still decides. If the provider's API key is not configured the
script exits cleanly so the pipeline keeps working without it.

Usage:
    python scripts/ai_review.py <diff-file> <output-file>

Environment:
    AI_PROVIDER      - "groq" or "gemini" (from pipeline-config.yml)
    AI_MODEL         - model name (from pipeline-config.yml)
    GROQ_API_KEY     - used when AI_PROVIDER=groq   (GitHub secret)
    GEMINI_API_KEY   - used when AI_PROVIDER=gemini (GitHub secret)
    MAX_DIFF_CHARS   - diffs longer than this are trimmed
    PR_TITLE         - pull request title, for context
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

GROQ_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"
GEMINI_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
KEY_NAMES = {"groq": "GROQ_API_KEY", "gemini": "GEMINI_API_KEY"}
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


def build_request(provider: str, prompt: str, model: str, api_key: str) -> urllib.request.Request:
    """Build the HTTP request for the chosen provider."""
    if provider == "groq":
        # Groq exposes an OpenAI-compatible chat completions API.
        body = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
        }
        req = urllib.request.Request(GROQ_ENDPOINT, data=json.dumps(body).encode(), method="POST")
        req.add_header("Authorization", f"Bearer {api_key}")
    elif provider == "gemini":
        body = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"temperature": 0.2}}
        req = urllib.request.Request(
            GEMINI_ENDPOINT.format(model=model), data=json.dumps(body).encode(), method="POST"
        )
        req.add_header("x-goog-api-key", api_key)
    else:
        raise ValueError(f"unknown AI provider: {provider}")
    req.add_header("Content-Type", "application/json")
    # Groq's API sits behind Cloudflare, which rejects Python's default
    # "Python-urllib" user agent with HTTP 403; identify the client instead.
    req.add_header("User-Agent", "my-cicd-framework-ai-review/2.0")
    return req


def extract_text(provider: str, response: dict) -> str:
    """Pull the review text out of the provider's response."""
    try:
        if provider == "groq":
            text = response["choices"][0]["message"]["content"]
        else:
            parts = response["candidates"][0]["content"]["parts"]
            text = "".join(p.get("text", "") for p in parts)
    except (KeyError, IndexError, TypeError):
        raise ValueError(f"unexpected response from the model: {str(response)[:300]}") from None
    text = (text or "").strip()
    if not text:
        raise ValueError("the model returned an empty review")
    return text


def call_model(provider: str, prompt: str, model: str, api_key: str) -> str:
    req = build_request(provider, prompt, model, api_key)
    with urllib.request.urlopen(req, timeout=120) as resp:
        return extract_text(provider, json.loads(resp.read().decode()))


def format_comment(review: str, provider: str, model: str, trimmed: bool) -> str:
    note = "\n\n_Note: the diff was long, so only the first part was reviewed._" if trimmed else ""
    return (
        f"{MARKER}\n### AI code review ({provider}: {model})\n\n{review}{note}\n\n"
        "_Automated and advisory only. A human reviewer makes the final call._"
    )


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: ai_review.py <diff-file> <output-file>")
        return 2

    provider = os.environ.get("AI_PROVIDER", "groq").strip().lower()
    if provider not in KEY_NAMES:
        print(f"::error::AI_PROVIDER must be one of {', '.join(KEY_NAMES)}; got {provider!r}")
        return 1
    key_name = KEY_NAMES[provider]
    api_key = os.environ.get(key_name, "").strip()
    if not api_key:
        print(f"::notice::{key_name} is not set, so the AI review was skipped.")
        return 0

    diff = open(argv[1], encoding="utf-8", errors="replace").read()
    if not diff.strip():
        print("Empty diff, nothing to review.")
        return 0

    model = os.environ.get("AI_MODEL", "llama-3.3-70b-versatile")
    max_chars = int(os.environ.get("MAX_DIFF_CHARS", "60000"))
    prompt, trimmed = build_prompt(diff, os.environ.get("PR_TITLE", ""), max_chars)
    try:
        review = call_model(provider, prompt, model, api_key)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:300]
        print(f"::warning title=AI review unavailable::HTTP {exc.code} from {provider}: {detail}")
        return 0
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        # Advisory stage: report the problem but never fail the pipeline over it.
        print(f"::warning title=AI review unavailable::{exc}")
        return 0

    with open(argv[2], "w", encoding="utf-8") as fh:
        fh.write(format_comment(review, provider, model, trimmed))
    print(f"Review written ({provider}: {model}).")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
