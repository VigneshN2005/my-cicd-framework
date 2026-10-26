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


def test_extract_text_joins_parts():
    response = {"candidates": [{"content": {"parts": [{"text": "No "}, {"text": "issues."}]}}]}
    assert ai_review.extract_text(response) == "No issues."


def test_extract_text_rejects_bad_response():
    with pytest.raises(ValueError):
        ai_review.extract_text({"error": "quota"})


def test_comment_is_marked_and_advisory():
    comment = ai_review.format_comment("Looks fine.", "gemini-2.5-flash", trimmed=True)
    assert comment.startswith(ai_review.MARKER)
    assert "advisory" in comment
    assert "first part" in comment


def test_skips_cleanly_without_api_key(tmp_path, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    diff = tmp_path / "pr.diff"
    diff.write_text("+x = 1")
    out = tmp_path / "review.md"
    assert ai_review.main(["ai_review.py", str(diff), str(out)]) == 0
    assert not out.exists()
