import json
import pytest
from pathlib import Path

from ai_quota.providers.lmstudio import parse_conversations, fmt_short, fmt_slack


def _write_conversation(tmp_path: Path, filename: str, data: dict) -> None:
    (tmp_path / filename).write_text(json.dumps(data))


CONV_WITH_STATS = {
    "assistantLastMessagedAt": 1700000000000,
    "userLastMessagedAt": 1700000001000,
    "messages": [
        {
            "currentlySelected": 0,
            "versions": [
                {
                    "senderInfo": {"senderName": "llama-3"},
                    "steps": [
                        {
                            "genInfo": {
                                "stats": {
                                    "promptTokensCount": 100,
                                    "predictedTokensCount": 50,
                                    "totalTokensCount": 150,
                                }
                            }
                        }
                    ],
                }
            ],
        },
        {
            "currentlySelected": 0,
            "versions": [
                {
                    "senderInfo": {"senderName": "llama-3"},
                    "steps": [
                        {
                            "genInfo": {
                                "stats": {
                                    "promptTokensCount": 200,
                                    "predictedTokensCount": 80,
                                    "totalTokensCount": 280,
                                }
                            }
                        }
                    ],
                }
            ],
        },
    ],
}


def test_parse_conversations_aggregates(tmp_path):
    _write_conversation(tmp_path, "conv1.json", CONV_WITH_STATS)
    entries = parse_conversations(tmp_path)
    assert len(entries) == 1
    e = entries[0]
    assert e["total_prompt_tokens"] == 300
    assert e["total_predicted_tokens"] == 130
    assert e["cumulative_total"] == 430
    assert e["last_usage"]["model"] == "llama-3"
    assert e["last_usage"]["prompt_tokens"] == 200
    assert e["last_usage"]["predicted_tokens"] == 80


def test_parse_conversations_multiple_files(tmp_path):
    _write_conversation(tmp_path, "a.json", CONV_WITH_STATS)
    conv2 = {
        "assistantLastMessagedAt": 1700000002000,
        "userLastMessagedAt": 1700000003000,
        "messages": [
            {
                "currentlySelected": 0,
                "versions": [
                    {
                        "senderInfo": {"senderName": "mistral"},
                        "steps": [
                            {
                                "genInfo": {
                                    "stats": {
                                        "promptTokensCount": 50,
                                        "predictedTokensCount": 25,
                                        "totalTokensCount": 75,
                                    }
                                }
                            }
                        ],
                    }
                ],
            }
        ],
    }
    _write_conversation(tmp_path, "b.json", conv2)
    entries = parse_conversations(tmp_path)
    assert len(entries) == 1
    e = entries[0]
    assert e["total_prompt_tokens"] == 350
    assert e["total_predicted_tokens"] == 155
    # Last usage should be from conv2 (later timestamp)
    assert e["last_usage"]["model"] == "mistral"


def test_parse_conversations_empty_dir(tmp_path):
    assert parse_conversations(tmp_path) == []


def test_parse_conversations_nonexistent(tmp_path):
    assert parse_conversations(tmp_path / "nope") == []


def test_parse_conversations_bad_json(tmp_path):
    (tmp_path / "bad.json").write_text("not json")
    assert parse_conversations(tmp_path) == []


def test_parse_conversations_no_stats(tmp_path):
    data = {
        "assistantLastMessagedAt": 1700000000000,
        "messages": [
            {"currentlySelected": 0, "versions": [{"steps": [{}]}]},
        ],
    }
    _write_conversation(tmp_path, "empty.json", data)
    assert parse_conversations(tmp_path) == []


def test_parse_conversations_missing_sender(tmp_path):
    data = {
        "assistantLastMessagedAt": 1700000000000,
        "userLastMessagedAt": 0,
        "messages": [
            {
                "currentlySelected": 0,
                "versions": [
                    {
                        "steps": [
                            {
                                "genInfo": {
                                    "stats": {
                                        "promptTokensCount": 10,
                                        "predictedTokensCount": 5,
                                    }
                                }
                            }
                        ]
                    }
                ],
            }
        ],
    }
    _write_conversation(tmp_path, "nosender.json", data)
    entries = parse_conversations(tmp_path)
    assert entries[0]["last_usage"]["model"] == "Unknown"


def test_fmt_short():
    entries = [{"total_prompt_tokens": 1234, "total_predicted_tokens": 567, "cumulative_total": 1801}]
    result = fmt_short(entries)
    assert "1,234" in result
    assert "567" in result
    assert "1,801" in result


def test_fmt_short_empty():
    assert fmt_short([]) == "lmstudio: no data"


def test_fmt_slack():
    entries = [
        {
            "total_prompt_tokens": 1000,
            "total_predicted_tokens": 500,
            "cumulative_total": 1500,
            "last_usage": {"model": "llama-3", "time": "2023-11-14T22:13:20"},
        }
    ]
    result = fmt_slack(entries)
    assert "*LM Studio Usage*" in result
    assert "llama-3" in result


def test_fmt_slack_empty():
    assert ":warning:" in fmt_slack([])
