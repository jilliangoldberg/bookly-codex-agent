# Dewey · Bookly support

A small Python support agent for a fictional online bookstore. Dewey tracks orders and
prepares item-level returns through the OpenAI Responses API. Customers submit returns
with an explicit button; Python applies the policy and records the result.

## Run locally

Requires Python 3.11+ and an OpenAI API account with access to `gpt-5.4-mini`.

```sh
git clone https://github.com/jilliangoldberg/bookly-codex-agent.git
cd bookly-codex-agent
git switch codex/dewey-poc
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

Set `OPENAI_API_KEY` in `.env`, then run:

```sh
python -m streamlit run app.py
```

Open the localhost URL printed by Streamlit. Without a key, the interface opens with
setup instructions and chat disabled. The key stays on the Python server; `.env` is ignored
by Git. `OPENAI_MODEL` optionally overrides the default with another Responses-compatible
model that supports strict function calling.

Direct dependencies are pinned to the tested versions. Tests do not require an API key:

```sh
python -m pytest -q
```

If OpenAI reports `credit_balance_exhausted` or `insufficient_quota`, check API billing
for the account or project behind your key. Dewey displays this separately from temporary
rate limiting. A key being present does not establish available API credits.

## Read the code in this order

1. **`tools.py`**: three fixture orders, return eligibility, proposal preparation, submission.
2. **`agent.py`**: voice and operating rules, strict tool schemas, allowlisted dispatch,
   bounded OpenAI loop.
3. **`app.py`**: session initialization, chat, actual button results, confirmation controls.
4. **`tests/test_dewey.py`**: backend rules, simulated API conversations, and real Streamlit
   widget tests.

The approved scope is in [PLAN.md](PLAN.md), with a [two-minute demo rehearsal](DEMO.md).
The editable five-slide [pitch deck](output/Dewey_Bookly_Pitch_v1.pptx) is in `output/`.

## Architecture and ownership

```text
Customer → Streamlit chat → OpenAI Responses API
                              ↓ function request
                      Python validation + dispatch
                              ↓
               get_order / check_return_eligibility / prepare_return
                              ↓ tool result
                      OpenAI customer response

prepare_return → pending proposal → Confirm / Cancel buttons
                                     ↓ Confirm only
                              Python create_return
                                     ↓
                        Actual result in UI + history
```

The model interprets intent and asks clarifying questions. Python controls which tools
exist, validates their inputs, enforces eligibility, and creates records. There is no
agent framework, classifier, vector database, provider router, or additional LLM layer.

The three model tools accept strings: `get_order(order_id)`,
`check_return_eligibility(order_id, item_id)`, and
`prepare_return(order_id, item_id, reason)`. State is injected by Python. `create_return`
is not available to the model. A proposal contains the order, item, title, and customer
reason. Its title is derived from tool data.

Each turn allows at most six sequential model requests. SDK retries are disabled, each
request times out after 30 seconds, and parallel tool calls are disabled. Tool requests
and results, including model reasoning items required by the API, remain in history.
The header's **Demo details → Behind the scenes** exposes actual function requests and
results for review. Clickable starter bubbles in the chat use the same agent path as
typed messages and disappear after the first customer message. OpenAI response
storage is disabled with `store=False`; this is not a promise of zero provider retention.

## Demo journeys

All orders and policies are invented. The fixed demo clock is **October 24, 2026**.

- **BK-1001:** shipped; ETA October 28; A Psalm for the Wild-Built and The Bookshop on the Corner.
- **BK-1002:** delivered October 18; The Hobbit and Piranesi; eligible for returns.
- **BK-1003:** delivered September 10; The Secret History; outside the return window.
- **BK-9999:** intentionally missing.

Tracking: ask “Where’s my order?” then provide “BK-1001”. Dewey should retain the tracking
intent and retrieve the shipment status and estimated date.

Return: ask “I want to return a book from BK-1002”. Dewey should ask which book. Reply
“The Hobbit; it arrived damaged”. After eligibility and preparation, check the displayed
details and click **Confirm return**. The first request reference is `RET-0001`.

Exception: ask to return The Secret History from BK-1003. Dewey should explain the expired
window without preparing or creating a request.

## Policy and session behavior

Books must belong to the order, be delivered, and be within **0–30 calendar days** of
delivery, inclusive. Each book can have one request per session. Reasons are required
(1–1,000 characters), but do not alter eligibility. There are no condition exceptions.

Confirmation rechecks eligibility. Typing “yes” cannot submit a return. Cancel clears the
proposal. Any new chat message clears an old proposal before the model processes it.
The interface displays actual confirmation results without an additional model call.
No request issues money, creates a shipping label, or schedules a collection.

The only application session state is messages, a pending return, and created returns.
Everything is in memory. Refreshing/reconnecting into a new session or restarting the
server may lose it. **Start a fresh demo** clears all three, including the duplicate ledger.
Return references are local to a session, not globally unique production identifiers.

## What verification proves

Automated tests exercise the policy boundaries, item ownership within an order, no-write
preparation, confirmation, cancellation, duplicate protection, stale proposals, argument
validation, tool/backend failures, API failure recovery, and the six-call limit.
Streamlit tests exercise real confirmation controls and chat rendering with a simulated API.

Simulated model responses verify the orchestration, not the model's ability to choose the
right response. With a real key, rehearse the journeys above and check the trace in Demo details:
missing ID → clarification, missing book → disambiguation, correct dates, no unsupported
action claims, honest failures. Treat these as live acceptance checks before submission.

Prompts govern conversational grounding and tone. They are not a deterministic guarantee
against hallucinations or prompt injection. Python guarantees action restrictions within
this single-session mock; the proposed LLM validation layer is not implemented.

## Decisions and production next step

- **Direct OpenAI tool loop:** easy to inspect and explain; requires explicit history/error handling.
- **Deterministic policy plus confirmation:** predictable action behavior; more rigid than free-form exceptions.
- **Session-only memory:** enough for multi-turn resolution; no cross-device continuity or durable records.
- **Styled Streamlit:** a quick Python UI with Dewey's personality; less layout control than a custom frontend.

First production change: authenticate the customer and use an owned-order backend with
durable, idempotent return creation. Order IDs alone are not authentication. Production
would also need privacy controls, operational monitoring, human escalation, and evaluation.

## Follow-up TODOs

- [ ] **LLM evaluator / adversarial conversations:** generate attempts to confuse Dewey,
  bypass policy, change items mid-flow, or invent success. Judge transcripts against actual
  tool results and created records; retain reproducible failures as regression cases.
- [ ] **Pre-send validation LLM:** compare draft responses against tool evidence and allowed
  actions. Measure missed errors, false alarms, cost, and latency before putting it in the path.
- [ ] Custom Dewey artwork, animation, and richer order presentation after the POC works.

Both LLM ideas follow the basic scaffolding. Neither substitutes for Python validation.

## API references

- [OpenAI function calling](https://developers.openai.com/api/docs/guides/function-calling)
- [GPT-5.4 mini](https://developers.openai.com/api/docs/models/gpt-5.4-mini)
