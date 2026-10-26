import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ai_review  # noqa: E402


def test_prompt_contains_diff_and_title():
    prompt, trimmed = ai_review.build_prompt("+print('hi')", "Add greeting", 1000)
    assert "+print('hi')" in prompt
    assert "Add greeting" in prompt
    assert trimmed is False


def test_long_diff_is_trimmed():
    prompt, trimmed = ai_review.build_prompt("x" * 500, "", 100)
    assert trimmed is True
    assert "diff trimmed" in prompt
    assert "x" * 101 not in prompt


def test_groq_request_uses_openai_format():
    req = ai_review.build_request("groq", "review this", "llama-3.3-70b-versatile", "k123")
    body = json.loads(req.data)
    assert req.full_url == ai_review.GROQ_ENDPOINT
    assert req.get_header("Authorization") == "Bearer k123"
    assert body["model"] == "llama-3.3-70b-versatile"
    assert body["messages"][0] == {"role": "user", "content": "review this"}


def test_requests_send_a_user_agent():
    for provider in ("groq", "gemini"):
        req = ai_review.build_request(provider, "x", "m", "k")
        assert req.get_header("User-agent", "").startswith("my-cicd-framework")


def test_gemini_request_uses_api_key_header():
    req = ai_review.build_request("gemini", "review this", "gemini-2.5-flash", "k123")
    assert "gemini-2.5-flash:generateContent" in req.full_url
    assert req.get_header("X-goog-api-key") == "k123"


def test_unknown_provider_is_rejected():
    with pytest.raises(ValueError):
        ai_review.build_request("openai", "x", "m", "k")


def test_extract_text_groq():
    response = {"choices": [{"message": {"content": "  No issues found.  "}}]}
    assert ai_review.extract_text("groq", response) == "No issues found."


def test_extract_text_gemini_joins_parts():
    response = {"candidates": [{"content": {"parts": [{"text": "No "}, {"text": "issues."}]}}]}
    assert ai_review.extract_text("gemini", response) == "No issues."


def test_extract_text_rejects_bad_response():
    with pytest.raises(ValueError):
        ai_review.extract_text("groq", {"error": {"message": "rate limited"}})


def test_comment_is_marked_and_advisory():
    comment = ai_review.format_comment("Looks fine.", "groq", "llama-3.3-70b-versatile", trimmed=True)
    assert comment.startswith(ai_review.MARKER)
    assert "groq: llama-3.3-70b-versatile" in comment
    assert "advisory" in comment
    assert "first part" in comment


@pytest.mark.parametrize("provider,key", [("groq", "GROQ_API_KEY"), ("gemini", "GEMINI_API_KEY")])
def test_skips_cleanly_without_api_key(tmp_path, monkeypatch, provider, key):
    monkeypatch.setenv("AI_PROVIDER", provider)
    monkeypatch.delenv(key, raising=False)
    diff = tmp_path / "pr.diff"
    diff.write_text("+x = 1")
    out = tmp_path / "review.md"
    assert ai_review.main(["ai_review.py", str(diff), str(out)]) == 0
    assert not out.exists()


def test_fallback_prefers_known_good_models():
    available = ["whisper-large-v3", "qwen/qwen3-32b", "openai/gpt-oss-120b"]
    assert ai_review.pick_fallback(available) == "openai/gpt-oss-120b"


def test_fallback_skips_non_chat_models():
    assert ai_review.pick_fallback(["whisper-large-v3", "llama-guard-4", "new-chat-model"]) == "new-chat-model"
    assert ai_review.pick_fallback(["whisper-large-v3"]) is None
