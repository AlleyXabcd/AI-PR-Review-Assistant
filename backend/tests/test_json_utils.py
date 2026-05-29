import pytest

from app.services.json_utils import extract_json


@pytest.mark.parametrize(
    "text",
    [
        '{"overview": "x", "key_changes": ["a"], "impact": "y"}',
        '```json\n{"overview": "x"}\n```',
        '```\n{"overview": "x"}\n```',
        '这是结果：{"overview": "x"} 以上。',
    ],
)
def test_extract_json_ok(text):
    data = extract_json(text)
    assert data["overview"] == "x"


@pytest.mark.parametrize("text", ["", "   ", "no json here", "{not valid"])
def test_extract_json_fail(text):
    with pytest.raises(ValueError):
        extract_json(text)
