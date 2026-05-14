import pytest

from generators.llm_client import parse_json_response


def test_parses_plain_json():
    text = '{"a": 1, "b": "x"}'
    assert parse_json_response(text) == {"a": 1, "b": "x"}


def test_strips_fenced_code_block():
    text = '```json\n{"a": 1}\n```'
    assert parse_json_response(text) == {"a": 1}


def test_strips_fenced_block_without_lang():
    text = '```\n{"a": 1}\n```'
    assert parse_json_response(text) == {"a": 1}


def test_handles_leading_prose():
    text = 'Here is the JSON:\n\n{"a": 1, "b": 2}\n\nLet me know if you need more.'
    assert parse_json_response(text) == {"a": 1, "b": 2}


def test_raises_on_no_json():
    with pytest.raises(ValueError):
        parse_json_response("just some text with no braces")


def test_handles_nested():
    text = '{"a": {"b": [1, 2, 3]}}'
    assert parse_json_response(text) == {"a": {"b": [1, 2, 3]}}
