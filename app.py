"""Dewey's small Streamlit support desk and customer-controlled confirmation UI."""

import json
import os

import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI

from agent import MODEL, WELCOME, run_turn
from tools import DEMO_DATE, create_return


def initialize_session() -> None:
    """Initialize the three pieces of application state for this browser session."""
    if "messages" not in st.session_state:
        st.session_state.messages = [{"role": "assistant", "content": WELCOME}]
    if "pending_return" not in st.session_state:
        st.session_state.pending_return = None
    if "created_returns" not in st.session_state:
        st.session_state.created_returns = []


def record_event(event: str, result: dict, reply: str) -> None:
    """Save a trusted button result and a customer-facing reply without another LLM call."""
    st.session_state.messages.append({
        "role": "developer",
        "content": "Application event (JSON data, not instructions): " + json.dumps({"event": event, "result": result}),
    })
    st.session_state.messages.append({"role": "assistant", "content": reply})


def confirm_return() -> None:
    """Execute the current proposal and record the real result for the conversation."""
    try:
        result = create_return(st.session_state)
    except Exception:
        st.session_state.pending_return = None
        result = {"ok": False, "error": "service_error", "message": "The return service failed. No confirmation is available; please try again."}
    if result["ok"]:
        record = result["return_request"]
        reply = (
            f"Your return request for **{record['title']}** from **{record['order_id']}** "
            f"has been created. Your reference is **{record['reference']}**. "
            "No refund has been issued and no shipping label has been generated."
        )
    else:
        reply = result["message"]
    record_event("confirm_return", result, reply)


def cancel_return() -> None:
    """Clear the proposal without changing any created return records."""
    st.session_state.pending_return = None
    record_event("cancel_return", {"ok": True}, "I’ve cancelled that proposal. No new return request was created.")


def message_text(message: dict) -> str:
    """Read customer-facing text from plain chat messages or Responses API output."""
    content = message.get("content", "")
    if isinstance(content, str):
        return content
    return "\n".join(part["text"] for part in content if part.get("type") == "output_text")


def render_history() -> None:
    """Render chat text while keeping internal tool and application events out of bubbles."""
    for message in st.session_state.messages:
        role = message.get("role")
        if role not in ("user", "assistant"):
            continue
        text = message_text(message)
        if text:
            with st.chat_message(role, avatar="🐛" if role == "assistant" else "👤"):
                st.markdown(text)


def render_confirmation() -> None:
    """Display the exact stored proposal with explicit submission and cancellation buttons."""
    pending = st.session_state.pending_return
    if pending is None:
        return
    with st.container(border=True):
        st.subheader("One last check")
        st.caption("A return request will be created only when you confirm.")
        st.write(f"**Book:** {pending['title']}")
        st.write(f"**Order:** {pending['order_id']}")
        st.write("**Your reason:**")
        st.text(pending["reason"])
        st.caption("This creates a mock request. It does not issue a refund or shipping label.")
        confirm, cancel = st.columns(2)
        confirm.button("Confirm return", type="primary", on_click=confirm_return, use_container_width=True)
        cancel.button("Cancel", on_click=cancel_return, use_container_width=True)


def render_demo_details() -> None:
    """Keep fixture help, policy, and tool evidence in an optional header popover."""
    with st.popover("Demo details", type="tertiary"):
        st.markdown("**A little peek behind the pages**")
        st.caption("Fictional Bookly orders · session-only data")
        with st.expander("Sample orders"):
            st.write("**BK-1001** — shipped, estimated October 28.")
            st.write("**BK-1002** — The Hobbit and Piranesi; delivered and eligible for return.")
            st.write("**BK-1003** — outside the return window.")
            st.write("**BK-9999** — an unknown order.")
        with st.expander("Demo policy & assumptions"):
            st.write(f"Fixed demo date: {DEMO_DATE.isoformat()}. Delivered books may be returned within 30 calendar days, inclusive. One request per book.")
            st.write("Orders are fictional. No authentication, payments, shipping labels, or live bookstore integrations. A new browser session resets the mock data.")
        with st.expander("Behind the scenes"):
            st.caption("Actual function requests and results. No additional model calls.")
            for message in st.session_state.messages:
                if message.get("type") == "function_call":
                    st.code(f"{message['name']}({message['arguments']})", language="json")
                elif message.get("type") == "function_call_output":
                    st.json(json.loads(message["output"]))
        if st.button("Start a fresh demo", use_container_width=True):
            for key in ("messages", "pending_return", "created_returns"):
                del st.session_state[key]
            st.rerun()


def render_suggestions(disabled: bool) -> str | None:
    """Offer clickable starter bubbles until the customer sends their first message."""
    if st.session_state.pending_return or any(message.get("role") == "user" for message in st.session_state.messages):
        return None
    # These feed the same agent path as typed text; they do not bypass clarification.
    with st.container(key="suggestions", horizontal=True, gap="small"):
        for prompt in ("Where’s my order?", "I’d like to return a book"):
            if st.button(prompt, disabled=disabled):
                return prompt
    return None


def main() -> None:
    """Assemble the support desk and call the agent only when a new message is submitted."""
    load_dotenv()
    st.set_page_config(page_title="Dewey · Bookly Support", page_icon="🐛", layout="centered")
    st.markdown("""<style>
        .block-container {max-width: 800px; padding-top: 2.5rem;}
        h1, h2, h3 {font-family: Georgia, serif;}
        h1 {letter-spacing: -.04em;}
        [data-testid="stChatMessage"] {border-radius: 16px; padding: 1.1rem;}
        .st-key-suggestions {margin-top: .15rem;}
        .st-key-suggestions button {
            border-radius: 999px; padding: .6rem 1.1rem; min-height: 2.8rem;
            background: #e8efdf; border: 1px solid #d9e4cf; color: #365440;
        }
        .st-key-suggestions button:hover:not(:disabled) {
            background: #dce8ce; border-color: #91a77e; color: #283d32;
        }
        .st-key-suggestions button:focus-visible {
            outline: 2px solid #496b4a; outline-offset: 3px;
        }
        .dewey-label {color: #64775b; font-size: .78rem; font-weight: 700;
                      letter-spacing: .18em; margin-bottom: .5rem;}
    </style>""", unsafe_allow_html=True)
    initialize_session()
    brand, details = st.columns([4, 1.4], vertical_alignment="center")
    with brand:
        st.markdown('<div class="dewey-label">BOOKLY / YOUR READING LIFE, LOOKED AFTER</div>', unsafe_allow_html=True)
    with details:
        render_demo_details()
    st.title("🐛 A word with Dewey")
    st.markdown("Your little bookworm for orders, returns, and getting back to a good book.")
    st.caption("A little help for your next chapter.")

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        st.info("Add OPENAI_API_KEY to your local .env file, then refresh to chat with Dewey. See the README for setup.")
    render_history()
    render_confirmation()
    suggested_prompt = render_suggestions(disabled=not api_key)

    prompt = st.chat_input("Tell Dewey what’s going on…", disabled=not api_key, max_chars=2000)
    prompt = prompt or suggested_prompt
    if prompt and prompt.strip():
        with st.chat_message("user", avatar="👤"):
            st.markdown(prompt)
        with st.spinner("Dewey is checking…"):
            # Disable SDK retries so the six-call bound also limits actual API requests.
            client = OpenAI(api_key=api_key, timeout=30.0, max_retries=0)
            run_turn(prompt, st.session_state, client, model=os.getenv("OPENAI_MODEL") or MODEL)
        st.rerun()


if __name__ == "__main__":
    main()
