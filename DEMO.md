# Dewey demo rehearsal

Use this after adding an OpenAI key and starting Streamlit. The automated suite uses
simulated responses; this rehearsal checks the actual model before an interview submission.

## Roughly two-minute walkthrough

**0:00–0:15 — Set the context**

“This is Dewey, Bookly's bookworm. I focused on order tracking and returns. The model
handles the conversation; Python controls the tools and actions.”

**0:15–0:40 — Track an order**

Type “Where's my order?” and wait for Dewey to request its number. Reply “BK-1001”.
Confirm Dewey reports shipped status and an *estimated* October 28, 2026 delivery.
Open **Behind the scenes** to show the actual `get_order` request and result.

**0:40–1:20 — Prepare and submit a return**

Type “I want to return a book from BK-1002”. Dewey should ask which book. Reply
“The Hobbit; it arrived damaged”. Show the eligibility result and pending proposal.
Point out that no return exists yet. Click **Confirm return**, then show `RET-0001`.
“The submission came from Python after my button click. It created a return request,
not a refund or shipping label.”

**1:20–1:45 — Show a policy boundary**

Type “Can I return The Secret History from BK-1003? I changed my mind.” Dewey should
explain that the window has expired, without presenting a confirmation card.

**1:45–2:00 — Explain the next step**

“For production I would first authenticate the customer and connect owned-order APIs
with durable, idempotent submission. Then I would add adversarial conversation evals
and trial a pre-send evidence checker.”

## Before recording or presenting

- Start a fresh demo so the created-return ledger is empty.
- Confirm the live model asks for the missing order ID and missing book.
- Confirm its wording matches dates, statuses, and eligibility results in the trace.
- Confirm Cancel creates nothing and a new chat message invalidates an old proposal.
- Do not present an API error as a bookstore failure or claim an escalation happened.
- Keep the fixed demo date visible in the assumptions, even if presenting on another date.
- Update slide 4 after live rehearsal if you want to report live verification.

## Verification at handoff

34 local automated checks passed, including an actual SDK request round trip through a
mock HTTP transport and Streamlit widget tests. The initial UI was inspected in the
browser. No live OpenAI call was made at initial handoff because an OpenAI API key was not configured.

After a key was added, the live request reached OpenAI but returned HTTP 429 with
`credit_balance_exhausted` / `insufficient_quota`. Live conversation acceptance remains
pending API credits. The app now distinguishes exhausted credits from temporary rate
limiting, with three added regression cases (37 automated checks total).

## Limited live verification after credits were added

Four scripted customer messages were attempted against `gpt-5.4-mini`, using the actual
production prompt, tools, and request settings. A shared test-only guard allowed at most
eight requests and conservatively reserved at most $0.10 of token cost. It stopped after
seven requests because its cumulative worst-case reservations reached that ceiling.

Observed results:

- Dewey asked for the missing order number and retained the tracking intent.
- `get_order(BK-1001)` was called and the reply correctly stated shipped status and the
  estimated October 28, 2026 delivery date.
- For BK-1002, Dewey retrieved the order and asked which of its two books to return.
- After “The Hobbit; it arrived damaged”, it successfully called eligibility and preparation
  with the correct order, item ID, and reason. Preparation created no return record.
- Replaying the actual canonical proposal through Python confirmation created `RET-0001`
  once and rejected a second confirmation, without another API call.

**Limits:** the budget guard stopped before the final customer-facing return reply.
Confirmation was checked locally from actual live proposal evidence; a complete live
browser return journey remains unverified. The expired-return path is covered offline,
but was not paid-tested here. No simulator or judge requests were made, and the hotel
agent's paid evaluations were not run.

Usage: **7 requests, 7,032 input tokens (including 2,048 cached), and 288 output tokens**.
Estimated cost: **$0.005188**, approximately half a cent. This uses the
[published GPT-5.4 mini rates](https://developers.openai.com/api/docs/models/gpt-5.4-mini)
of $0.75 / million input, $0.075 / million cached input, and $4.50 / million output tokens;
it is an estimate, not an invoice. The detailed transcript remains local in ignored `tmp/`.
