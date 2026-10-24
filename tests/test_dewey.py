"""Focused business, orchestration, and Streamlit tests; no network or API key needed."""

import json
from copy import deepcopy
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import httpx
from openai import APIConnectionError, OpenAI, RateLimitError
from streamlit.testing.v1 import AppTest

import agent
import tools

APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


@pytest.fixture
def state():
    """Give each test an independent conversation, proposal, and return ledger."""
    return {"messages": [], "pending_return": None, "created_returns": []}


def api_response(text="", calls=(), reasoning=False):
    """Build SDK-shaped Responses output for deterministic orchestration tests."""
    output = []
    if reasoning:
        raw = {"type": "reasoning", "id": "rs_test", "summary": []}
        output.append(SimpleNamespace(type="reasoning", model_dump=lambda raw=raw, **kwargs: raw))
    for index, (name, arguments) in enumerate(calls):
        raw = {
            "type": "function_call", "id": f"fc_{index}", "call_id": f"call_{index}",
            "name": name, "arguments": arguments if isinstance(arguments, str) else json.dumps(arguments),
        }
        output.append(SimpleNamespace(**raw, model_dump=lambda raw=raw, **kwargs: raw))
    if text:
        raw = {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": text, "annotations": []}]}
        output.append(SimpleNamespace(type="message", model_dump=lambda **kwargs: raw))
    return SimpleNamespace(output=output, output_text=text)


def fake_client(*responses):
    """Replay model responses and retain independent copies of each request's history."""
    snapshots = []
    iterator = iter(responses)

    def create(**kwargs):
        """Snapshot mutable input history before the agent appends subsequent results."""
        snapshots.append(deepcopy(kwargs))
        result = next(iterator)
        if isinstance(result, Exception):
            raise result
        return result

    return SimpleNamespace(responses=SimpleNamespace(create=Mock(side_effect=create)), snapshots=snapshots)


def test_order_lookup_normalizes_and_copies_data():
    result = tools.get_order(" bk-1001 ")
    assert result["order"]["estimated_delivery"] == "2026-10-28"
    result["order"]["items"].clear()
    assert len(tools.get_order("BK-1001")["order"]["items"]) == 2
    assert tools.get_order("BK-9999")["error"] == "order_not_found"


@pytest.mark.parametrize("days,eligible", [(0, True), (30, True), (31, False), (-1, False)])
def test_return_window_boundaries(monkeypatch, state, days, eligible):
    order = deepcopy(tools.ORDERS["BK-1002"])
    order["delivered_on"] = (tools.DEMO_DATE - timedelta(days=days)).isoformat()
    monkeypatch.setitem(tools.ORDERS, "BK-1002", order)
    assert tools.check_return_eligibility("BK-1002", "BK-1002-1", state["created_returns"])["eligible"] is eligible


@pytest.mark.parametrize("order_id,item_id,expected", [
    ("BK-1001", "BK-1001-1", "not_eligible"),
    ("BK-1003", "BK-1003-1", "not_eligible"),
    ("BK-9999", "anything", "order_not_found"),
    ("BK-1002", "BK-1001-1", "item_not_found"),
])
def test_invalid_returns_never_prepare_or_create(state, order_id, item_id, expected):
    result = tools.prepare_return(order_id, item_id, "Damaged", state)
    assert result["error"] == expected
    assert state["pending_return"] is None
    assert state["created_returns"] == []


def test_prepare_then_confirm_creates_once(state):
    result = tools.prepare_return("bk-1002", "bk-1002-1", "  Arrived damaged  ", state)
    assert result["pending_return"]["title"] == "The Hobbit"
    assert state["created_returns"] == []
    result["pending_return"]["title"] = "Tampered copy"
    created = tools.create_return(state)
    assert created["return_request"]["title"] == "The Hobbit"
    assert created["return_request"]["reason"] == "Arrived damaged"
    assert created["return_request"]["reference"] == "RET-0001"
    assert state["pending_return"] is None
    assert tools.create_return(state)["error"] == "no_pending_return"
    assert tools.prepare_return("BK-1002", "BK-1002-1", "Again", state)["error"] == "not_eligible"
    assert len(state["created_returns"]) == 1


def test_confirmation_rechecks_policy(monkeypatch, state):
    tools.prepare_return("BK-1002", "BK-1002-1", "Damaged", state)
    order = deepcopy(tools.ORDERS["BK-1002"])
    order["delivered_on"] = "2026-09-01"
    monkeypatch.setitem(tools.ORDERS, "BK-1002", order)
    assert tools.create_return(state)["error"] == "not_eligible"
    assert state["pending_return"] is None
    assert state["created_returns"] == []


@pytest.mark.parametrize("reason", ["", "   ", None, "x" * 1001])
def test_reason_is_required(state, reason):
    assert tools.prepare_return("BK-1002", "BK-1002-1", reason, state)["error"] == "invalid_reason"


@pytest.mark.parametrize("name,arguments,error", [
    ("create_return", "{}", "unknown_tool"),
    ("get_order", "{broken", "invalid_arguments"),
    ("get_order", "[]", "invalid_arguments"),
    ("get_order", '{"order_id": 12}', "invalid_arguments"),
    ("get_order", '{"order_id": "BK-1001", "admin": true}', "invalid_arguments"),
    ("prepare_return", '{"order_id": "BK-1002"}', "invalid_arguments"),
])
def test_tool_allowlist_and_argument_validation(state, name, arguments, error):
    assert agent.execute_tool(name, arguments, state)["error"] == error
    assert state["created_returns"] == []


def test_backend_failure_is_a_tool_result(monkeypatch, state):
    def broken_lookup(order_id):
        """Simulate an unavailable bookstore backend."""
        raise RuntimeError("Backend unavailable")
    monkeypatch.setattr(agent, "get_order", broken_lookup)
    assert agent.execute_tool("get_order", '{"order_id": "BK-1001"}', state)["error"] == "tool_failed"


def test_multiturn_history_and_grounded_tool_output(state):
    client = fake_client(
        api_response("What’s your order number?"),
        api_response(calls=[("get_order", {"order_id": "BK-1001"})], reasoning=True),
        api_response("Your order has shipped. Estimated delivery is October 28, 2026."),
    )
    agent.run_turn("Where is my order?", state, client)
    reply = agent.run_turn("BK-1001", state, client)
    assert "October 28" in reply
    second_history = client.snapshots[1]["input"]
    assert second_history[0]["content"] == "Where is my order?"
    assert second_history[-1]["content"] == "BK-1001"
    tool_output = client.snapshots[2]["input"][-1]
    assert json.loads(tool_output["output"])["order"]["status"] == "shipped"
    assert any(item.get("type") == "reasoning" for item in client.snapshots[2]["input"])
    assert all(not request["parallel_tool_calls"] and not request["store"] for request in client.snapshots)


def test_return_tools_prepare_but_cannot_submit(state):
    arguments = {"order_id": "BK-1002", "item_id": "BK-1002-1"}
    client = fake_client(
        api_response(calls=[("get_order", {"order_id": "BK-1002"})]),
        api_response(calls=[("check_return_eligibility", arguments)]),
        api_response(calls=[("prepare_return", {**arguments, "reason": "Damaged"})]),
        api_response("Please use Confirm return below."),
    )
    agent.run_turn("Return The Hobbit from BK-1002; it arrived damaged.", state, client)
    assert state["pending_return"]["title"] == "The Hobbit"
    assert state["created_returns"] == []
    assert {tool["name"] for tool in agent.TOOLS} == {"get_order", "check_return_eligibility", "prepare_return"}


def test_new_message_invalidates_proposal_even_when_it_says_yes(state):
    tools.prepare_return("BK-1002", "BK-1002-1", "Damaged", state)
    agent.run_turn("yes", state, fake_client(api_response("Please prepare a new proposal.")))
    assert state["pending_return"] is None
    assert state["created_returns"] == []


def test_api_failure_clears_proposal_and_records_fallback(state):
    tools.prepare_return("BK-1002", "BK-1002-1", "Damaged", state)
    client = fake_client(APIConnectionError(request=Mock()))
    reply = agent.run_turn("Try again", state, client)
    assert "couldn’t reach" in reply
    assert state["pending_return"] is None
    assert state["messages"][-1]["content"] == reply


@pytest.mark.parametrize("code,expected", [
    ("credit_balance_exhausted", "no credits available"),
    ("insufficient_quota", "no credits available"),
    ("rate_limit_exceeded", "too many requests"),
])
def test_quota_and_temporary_rate_limits_have_distinct_recovery(state, code, expected):
    error = RateLimitError(
        "Test API limit", response=httpx.Response(429, request=httpx.Request("POST", "https://api.openai.com/v1/responses")),
        body={"code": code},
    )
    reply = agent.run_turn("Where is my order?", state, fake_client(error))
    assert expected in reply
    assert state["pending_return"] is None
    assert state["created_returns"] == []


def test_six_call_bound_keeps_tool_results_paired(state):
    response = api_response(calls=[("get_order", {"order_id": "BK-1001"})])
    client = fake_client(*([response] * 6))
    reply = agent.run_turn("Check my order", state, client)
    assert client.responses.create.call_count == 6
    assert "reached my limit" in reply
    assert len([message for message in state["messages"] if message.get("type") == "function_call_output"]) == 6
    assert state["pending_return"] is None


def test_empty_response_uses_recovery(state):
    reply = agent.run_turn("Hello", state, fake_client(api_response()))
    assert "couldn’t finish" in reply


def test_incomplete_model_response_never_executes_a_tool(state):
    response = api_response(calls=[("prepare_return", {
        "order_id": "BK-1002", "item_id": "BK-1002-1", "reason": "Damaged",
    })])
    response.status = "incomplete"
    reply = agent.run_turn("Return my damaged Hobbit", state, fake_client(response))
    assert "interrupted" in reply
    assert state["pending_return"] is None
    assert state["messages"][-2]["type"] == "function_call_output"


def test_real_sdk_serialization_with_mock_http_transport(state):
    requests = []

    def respond(request):
        """Exercise the installed SDK over a local mock transport, never the network."""
        requests.append(json.loads(request.content))
        output = ([{
            "type": "function_call", "id": "fc_lookup", "call_id": "call_lookup",
            "name": "get_order", "arguments": '{"order_id": "BK-1001"}', "status": "completed",
        }] if len(requests) == 1 else [{
            "type": "message", "id": "msg_answer", "role": "assistant", "status": "completed",
            "content": [{"type": "output_text", "text": "Shipped; estimated October 28.", "annotations": []}],
        }])
        return httpx.Response(200, json={
            "id": f"resp_{len(requests)}", "object": "response", "created_at": 1792886400,
            "model": agent.MODEL, "status": "completed", "output": output,
            "parallel_tool_calls": False, "tool_choice": "auto", "tools": agent.TOOLS,
        })

    with OpenAI(api_key="test-not-a-real-key", max_retries=0,
                http_client=httpx.Client(transport=httpx.MockTransport(respond))) as client:
        reply = agent.run_turn("Track BK-1001", state, client)
    assert reply == "Shipped; estimated October 28."
    assert len(requests) == 2
    assert requests[0]["tools"][0]["strict"] is True
    assert requests[1]["input"][-1]["call_id"] == "call_lookup"
    assert json.loads(requests[1]["input"][-1]["output"])["order"]["order_id"] == "BK-1001"


def app_with_proposal(monkeypatch):
    """Open the real UI with no key and seed a validated confirmation proposal."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr("dotenv.load_dotenv", lambda: None)
    app = AppTest.from_file(APP_PATH).run()
    tools.prepare_return("BK-1002", "BK-1002-1", "Damaged", app.session_state)
    return app.run()


def test_ui_missing_key_is_clear_and_disables_chat(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr("dotenv.load_dotenv", lambda: None)
    app = AppTest.from_file(APP_PATH).run()
    assert not app.exception
    assert app.chat_input[0].disabled
    assert "OPENAI_API_KEY" in app.info[0].value
    assert next(button for button in app.button if button.label == "Where’s my order?").disabled


def test_ui_confirmation_records_actual_result(monkeypatch):
    app = app_with_proposal(monkeypatch)
    next(button for button in app.button if button.label == "Confirm return").click().run()
    assert not app.exception
    assert app.session_state["pending_return"] is None
    assert len(app.session_state["created_returns"]) == 1
    assert "RET-0001" in app.chat_message[-1].markdown[0].value
    assert any(message.get("role") == "developer" for message in app.session_state["messages"])
    assert not any(button.label == "Confirm return" for button in app.button)


def test_ui_cancel_and_reset(monkeypatch):
    app = app_with_proposal(monkeypatch)
    next(button for button in app.button if button.label == "Cancel").click().run()
    assert app.session_state["pending_return"] is None
    assert app.session_state["created_returns"] == []
    next(button for button in app.button if button.label == "Start a fresh demo").click().run()
    assert not app.exception
    assert len(app.session_state["messages"]) == 1


def test_ui_chat_calls_agent_and_displays_response(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "fake-test-key")
    client = fake_client(api_response("What’s your order number?"))
    monkeypatch.setattr("openai.OpenAI", lambda **kwargs: client)
    app = AppTest.from_file(APP_PATH).run()
    app.chat_input[0].set_value("Where is my order?").run()
    assert not app.exception
    assert "order number" in app.chat_message[-1].markdown[0].value
    assert client.responses.create.call_count == 1


@pytest.mark.parametrize("starter", ["Where’s my order?", "I’d like to return a book"])
def test_ui_starter_bubbles_send_once_and_reset_restores_them(monkeypatch, starter):
    monkeypatch.setenv("OPENAI_API_KEY", "fake-test-key")
    client = fake_client(api_response("What’s your order number?"))
    monkeypatch.setattr("openai.OpenAI", lambda **kwargs: client)
    app = AppTest.from_file(APP_PATH).run()
    next(button for button in app.button if button.label == starter).click().run()
    assert not app.exception
    assert client.responses.create.call_count == 1
    assert app.session_state["messages"][1] == {"role": "user", "content": starter}
    assert not any(button.label == starter for button in app.button)
    app.run()
    assert client.responses.create.call_count == 1
    next(button for button in app.button if button.label == "Start a fresh demo").click().run()
    assert any(button.label == starter for button in app.button)
    assert client.responses.create.call_count == 1
