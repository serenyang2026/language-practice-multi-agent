"""Streamlit chat UI for the language practice multi-agent."""

import logging
import uuid

import streamlit as st
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage

# Read .env when running locally. In Azure the same values come from the
# Container App's environment variables, and this line simply does nothing.
load_dotenv()

from agent import EXPLAIN_IN, LANGUAGES, LEVELS, build_graph  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

AGENT_LABELS = {
    "writing_corrector": "✍️ Writing corrector",
    "vocab": "📖 Vocab coach",
    "grammar_teacher": "🧑‍🏫 Grammar teacher",
    "quiz": "📝 Quiz master",
}

st.set_page_config(page_title="Language Practice", page_icon="🗣️")


@st.cache_resource
def get_graph():
    """Build the graph once per app process and share it across sessions."""
    return build_graph()


# --- Sidebar: learner settings --------------------------------------------
with st.sidebar:
    st.header("Settings")
    target = st.selectbox("Language to practise", LANGUAGES)
    explain_in = st.selectbox("Explanations in", EXPLAIN_IN)
    level = st.selectbox("Level", LEVELS)
    new_chat = st.button("New conversation", use_container_width=True)

settings = {"target": target, "explain_in": explain_in, "level": level}

# Start a fresh conversation on first load, on request, or when settings change,
# so an old German conversation doesn't mix into a new French one.
if (
    "thread_id" not in st.session_state
    or new_chat
    or st.session_state.get("settings") != settings
):
    st.session_state.thread_id = str(uuid.uuid4())
    st.session_state.history = []
    st.session_state.settings = settings

# --- Main area --------------------------------------------------------------
st.title(f"🗣️ {target} practice")
st.caption(
    "Write a text to get it corrected, ask about a word or a grammar topic, "
    "or ask for a quiz. A supervisor picks the right specialist."
)

for role, content, agent_name in st.session_state.history:
    with st.chat_message(role):
        if agent_name:
            st.caption(AGENT_LABELS.get(agent_name, agent_name))
        st.markdown(content)

if prompt := st.chat_input(f"Write in {target}, or ask a question…"):
    st.session_state.history.append(("user", prompt, None))
    with st.chat_message("user"):
        st.markdown(prompt)

    config = {"configurable": {"thread_id": st.session_state.thread_id, "settings": settings}}

    with st.chat_message("assistant"):
        try:
            with st.spinner("Thinking…"):
                result = get_graph().invoke({"messages": [HumanMessage(prompt)]}, config)
            reply = result["messages"][-1]
            st.caption(AGENT_LABELS.get(reply.name, reply.name or ""))
            st.markdown(reply.content)
            st.session_state.history.append(("assistant", reply.content, reply.name))
        except Exception as exc:  # show the problem in the UI instead of a blank page
            logging.exception("Agent call failed")
            st.error(f"Something went wrong: {exc}")
