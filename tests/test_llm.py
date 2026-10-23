import pytest

from intake.config import ModelConfig
from intake.errors import AgentError
from intake.llm import FakeLLM, parse_json


def test_parse_json_tolerates_fences_and_prose():
    assert parse_json('Sure:\n```json\n{"a": 1}\n```') == {"a": 1}


def test_parse_json_rejects_non_json():
    with pytest.raises(AgentError):
        parse_json("no json here")


def test_fake_llm_records_calls():
    llm = FakeLLM([{"x": 1}])
    cfg = ModelConfig("gemini-2.5-flash")
    assert llm.complete(system="s", user="u", config=cfg) == {"x": 1}
    assert llm.calls[0]["config"] is cfg
    with pytest.raises(AgentError):
        llm.complete(system="s", user="u", config=cfg)
