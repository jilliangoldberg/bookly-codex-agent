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
browser. No live OpenAI call was made because an OpenAI API key was not configured.
