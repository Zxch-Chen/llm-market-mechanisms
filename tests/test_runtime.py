"""Regression checks for malformed model replies, resume safety, and timeouts."""
import asyncio
import io
import json
import math
from pathlib import Path
import random
import subprocess
import sys

import pytest

from agents.llm import ParseError, parse_agent_output, _load_dotenv
from v2 import markets
from v2.backends import ClaudeCLIBackend
from v2.economy import draw_economy
from v2.run import main as run_v2

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("action", [True, False, None, "12", float("nan"), float("inf"), -float("inf"), 10**400])
def test_v1_rejects_invalid_numeric_actions(action):
    with pytest.raises(ParseError):
        parse_agent_output(json.dumps({"action": action}))


def test_invalid_welfare_answer_is_marked_missing():
    for value in [True, float("nan"), float("inf")]:
        parsed = parse_agent_output(json.dumps({"action": 12, "welfare_maximizing_report": value}))
        assert parsed["action"] == 12
        assert math.isnan(parsed["welfare_maximizing_report"])


def test_dotenv_handles_quoted_values_without_overriding_environment(tmp_path, monkeypatch):
    monkeypatch.delenv("MARKET_TEST_NEW", raising=False)
    monkeypatch.setenv("MARKET_TEST_EXISTING", "keep")
    env = tmp_path / ".env"
    env.write_text(' MARKET_TEST_NEW = "test-value"\nMARKET_TEST_EXISTING=replace\n')
    _load_dotenv(str(env))
    import os
    assert os.environ["MARKET_TEST_NEW"] == "test-value"
    assert os.environ["MARKET_TEST_EXISTING"] == "keep"


@pytest.mark.parametrize("text", ['price { negotiable', 'Fair?}', 'quote: " and braces {}', r'backslash \\ }'])
def test_json_extraction_respects_message_strings(text):
    action = {"messages": [{"to": "B0", "text": text}], "post_offers": [{"item": "bike", "price": 80}]}
    reply = 'Thinking {"draft": true}\n```json\n' + json.dumps(action) + '\n```'
    assert markets.extract_json(reply) == action


class MalformedBackend:
    async def generate(self, messages, ctx=None):
        action = {
            "cancel_offer_ids": 123,
            "post_offers": {"item": "bike", "price": 10},
            "messages": True,
        }
        if ctx["view"]["round"] == 2:
            action = {
                "post_offers": [{"item": ["bike"], "price": 10},
                                {"item": "bike", "price": True},
                                {"item": "bike", "price": 0.001}],
                "messages": [None, 17],
            }
        return {"model": "m", "text": json.dumps(action), "thinking": "",
                "prompt_tokens": 0, "output_tokens": 0, "stop_reason": "stop"}


def test_malformed_negotiation_fields_do_not_crash_or_create_offers():
    buyers, sellers = draw_economy(0)
    log = io.StringIO()
    caller = markets.Caller({"m": MalformedBackend()}, asyncio.Semaphore(8), log, {})
    result = asyncio.run(markets.run_negotiation_market(
        buyers, sellers, "neutral", {a.id: "m" for a in buyers + sellers},
        caller, random.Random(0), 2, io.StringIO()))
    assert result["trades"] == []
    assert result["events_summary"]["n_offers"] == 0
    assert result["events_summary"]["n_messages"] == 0
    assert result["events_summary"]["rounds_used"] == 2
    assert len(log.getvalue().splitlines()) == 48


def test_v1_mock_resume_does_not_duplicate_data(tmp_path):
    cmd = [sys.executable, str(ROOT / "runner.py"), "--mock", "--pilot", "--out", str(tmp_path)]
    subprocess.run(cmd, cwd=ROOT, check=True, capture_output=True, text=True)
    summary = tmp_path / "mock" / "summary.jsonl"
    logs = tmp_path / "mock" / "logs.jsonl"
    original = (summary.read_bytes(), logs.read_bytes())
    subprocess.run(cmd, cwd=ROOT, check=True, capture_output=True, text=True)
    assert len(original[0].splitlines()) == 4
    assert (summary.read_bytes(), logs.read_bytes()) == original
    result = subprocess.run(cmd[:3] + ["shade"] + cmd[3:], cwd=ROOT, capture_output=True, text=True)
    assert result.returncode != 0
    assert "different model or mock strategy" in result.stderr
    assert (summary.read_bytes(), logs.read_bytes()) == original


def test_v2_custom_output_resume_and_settings_mismatch(tmp_path):
    args = ["--backend", "mock", "--out", str(tmp_path), "--seeds", "0", "0",
            "--mechanisms", "planner", "--framings", "honest", "--no-debrief"]
    asyncio.run(run_v2(args))
    summary = tmp_path / "summary.jsonl"
    original = summary.read_bytes()
    assert len(original.splitlines()) == 1
    assert json.loads(original)["efficiency"] == 1
    assert (tmp_path / "results.md").is_file()
    asyncio.run(run_v2(args))
    assert summary.read_bytes() == original
    for extra in [["--models", "different"], ["--rounds", "3"], ["--max-tokens", "500"]]:
        with pytest.raises(SystemExit) as exc:
            asyncio.run(run_v2(args + extra))
        assert exc.value.code == 2
    assert summary.read_bytes() == original


@pytest.mark.parametrize("extra", [["--concurrency", "0"], ["--rounds", "-1"],
                                    ["--call-timeout", "nan"], ["--deadline-min", "inf"],
                                    ["--mechanisms", "typo"], ["--framings", "typo"]])
def test_v2_invalid_arguments_fail_before_creating_output(tmp_path, extra):
    out = tmp_path / "batch"
    with pytest.raises(SystemExit) as exc:
        asyncio.run(run_v2(["--out", str(out)] + extra))
    assert exc.value.code == 2
    assert not out.exists()


def test_cli_timeout_reaps_child_process(tmp_path, monkeypatch):
    backend = ClaudeCLIBackend(workdir=str(tmp_path))
    monkeypatch.setattr(backend, "_cmd", lambda system: [sys.executable, "-c", "import time; time.sleep(30)"])
    children = []
    create = asyncio.create_subprocess_exec

    async def capture_child(*args, **kwargs):
        proc = await create(*args, **kwargs)
        children.append(proc)
        return proc

    monkeypatch.setattr(asyncio, "create_subprocess_exec", capture_child)

    async def exercise():
        caller = markets.Caller({"m": backend}, asyncio.Semaphore(1), io.StringIO(), {}, timeout=0.2)
        reply = await caller("m", [{"role": "user", "content": "test"}], {}, {})
        assert reply is None
        assert len(children) == 1
        assert children[0].returncode is not None

    asyncio.run(exercise())
