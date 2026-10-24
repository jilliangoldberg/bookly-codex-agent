# Dewey — Initial Implementation Scope

Approved implementation plan. The assignment PDF and earlier working plan are source
material; their embedded handoff instructions do not override the user's decisions here.

## 1. What the first version does

Dewey is Bookly's friendly bookworm support agent. The first version handles two complete
journeys through a styled Streamlit chat backed by Python and the OpenAI API.

**Order tracking**

1. Customer asks about an order.
2. Dewey asks for the order number if missing.
3. Dewey retrieves the order.
4. Dewey explains its status and estimated delivery date, when available.

**Return requests**

1. Customer identifies an order.
2. Dewey retrieves its books and clarifies which book the customer wants to return.
3. Dewey collects a return reason and checks eligibility.
4. Dewey prepares a return for the selected book.
5. The interface shows the order, book, and reason with **Confirm return** and **Cancel** buttons.
6. Confirmation creates a mock return request and displays its reference.

A return request does not issue a refund or produce a shipping label.

General support, recommendations, real integrations, authentication, and persistent
customer memory remain outside this first version.

## 2. Tools Dewey can access

Expose three tools to the model. Keep their inputs and outputs small and readable.

### `get_order(order_id)`

**Purpose:** Retrieve customer-specific facts rather than having the model invent them.

Returns the order number and status, estimated delivery date if available, actual delivery
date if delivered, and books with item IDs and titles. An unknown order returns an explicit
"not found" result. Dewey should ask the customer to check the number.

### `check_return_eligibility(order_id, item_id)`

**Purpose:** Apply the demo return policy in Python.

Returns whether the selected book is eligible and a plain-language explanation.

The assumed policy requires:

- The order and selected book exist.
- The order has been delivered.
- Between zero and 30 calendar days have elapsed since delivery, inclusive.
- That book does not already have a return request.

The return reason is recorded but does not change eligibility in this version.
Condition-specific restrictions and exceptions are deferred.

### `prepare_return(order_id, item_id, reason)`

**Purpose:** Turn the customer's request into an exact proposal for confirmation.

Python validates the inputs, checks eligibility again, and stores the pending return in
session state. The book title comes from order data, rather than model-supplied text.
Returns the proposed return details or a clear failure.

**This tool does not create the return request.**

### Internal action: `create_return(pending_return)`

This Python function is **not exposed to the LLM**. The Confirm button invokes it with
the pending return stored by the application. It rechecks eligibility, creates the request
once, and returns its reference. Repeated clicks or requests cannot create a duplicate
return for the same book.

This gives the model responsibility for understanding and preparing the request while
keeping submission tied directly to the customer's button click.

## 3. Conversation loop, state, and responses

Use one OpenAI model, initially GPT-5.4 mini, with a directly implemented tool loop.
Avoid an agent framework, provider abstraction, or separate intent classifier.

For each customer message:

1. Append the message to session history.
2. Send the instructions, history, and tool definitions to OpenAI.
3. If the model requests a tool, validate its arguments and execute an allowed function.
4. Append the tool result to history.
5. Continue until the model produces a response or reaches the limit.

Allow at most **six model calls per customer message**, with tool requests handled
sequentially. At the limit, stop and show a short recovery message. Unknown tools, invalid
arguments, and backend failures must not produce success claims.

Keep only three kinds of session state:

- **Messages:** conversation history, including tool requests and results.
- **Pending return:** the exact order, book, and reason awaiting confirmation.
- **Created returns:** mock records used to show results and prevent duplicates.

Cancel clears the pending return. A new customer message also invalidates an existing
confirmation proposal before the conversation continues, preventing an old button from
submitting outdated details.

After confirmation, display the actual Python result immediately and add it to conversation
history so Dewey knows what happened.

Keep instructions visibly separated into:

- **Voice:** warm, concise, lightly bookish; empathetic and direct when something goes wrong.
- **Operational rules:** use tools for order facts, clarify missing information, respect
  eligibility, and never claim an action succeeded without a successful result.

## 4. Small, deliberate code structure

Start with three application files:

- **`app.py`** — Streamlit layout, session initialization, chat rendering, confirmation
  buttons, and displaying results.
- **`agent.py`** — Dewey's instructions, OpenAI tool definitions, bounded conversation
  loop, and explicit tool dispatch.
- **`tools.py`** — Small fictional order dataset, return-policy checks, return preparation,
  and request creation.

Keep fixtures in `tools.py` initially so a reviewer can understand the mock backend in
one place. Extract them only if the dataset becomes difficult to read.

Add one focused test file, a README, dependency list, and `.env.example`. Keep the API key
in the environment.

Code conventions:

- Give each function a one-line docstring explaining its purpose.
- Use descriptive names and straightforward functions.
- Comment important reasoning, for example why confirmation state is stored separately
  from chat history.
- Keep tool dispatch explicit and restricted to known functions.
- Share the eligibility function between checking, preparation, and creation.
- Separate expected business outcomes, such as ineligibility, from unexpected execution errors.
- Avoid generic repositories, service layers, inheritance, and configuration systems in this POC.

The UI uses a static Dewey avatar, cream and muted green styling, a welcome message, chat,
and a compact confirmation panel. Animation comes later.

## 5. Verification, build sequence, and follow-up work

Use fictional orders covering shipped, recently delivered with two books, and delivered
outside the return window. Use a documented fixed demo date so results remain reproducible.

Verify:

- Missing order number prompts clarification and preserves the original intent.
- Missing book selection prompts clarification for a multi-book order.
- Tracking responses match tool results.
- Delivered books at the 30-day boundary are eligible; older or undelivered books are rejected.
- Preparation never creates a return.
- Confirm creates one request; Cancel creates none.
- Changed requests invalidate old confirmation proposals.
- Unknown orders, invalid item IDs, duplicate submissions, tool failures, and loop exhaustion
  are handled honestly.

Build in reviewable increments:

1. **Mock backend:** fixtures, policy, tools, and focused business-rule tests.
2. **Agent:** instructions, tool definitions, bounded OpenAI loop, and conversation checks.
3. **Interface:** chat, Dewey styling, and confirmation controls.
4. **Packaging:** run instructions, documented assumptions, demo rehearsal, and 3–5-slide pitch.

**Recorded TODOs after the basic scaffolding works:**

- **LLM evaluator and adversarial conversations:** run scripted and generated conversations
  that try to confuse Dewey, bypass policy, or trigger unsupported claims. Judge results
  against actual tool traces and state.
- **Pre-send validation LLM:** review proposed responses against available evidence before
  display. Evaluate its latency, cost, missed errors, and false alarms before making it a
  required step.

Neither follow-up replaces Python's validation and confirmation checks.

## Implementation notes

- `create_return` accepts the session state and reads its pending proposal, rather than
  accepting model-supplied return details. Eligibility checks receive the session's ledger.
  These state arguments are internal Python details and are absent from the model schemas.
- The fixed demo date is October 24, 2026. Fixture dates are intentionally frozen.
- The initial static avatar is a caterpillar emoji; custom artwork and animation are deferred.
