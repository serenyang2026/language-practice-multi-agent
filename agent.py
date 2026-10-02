"""Language practice multi-agent.

A supervisor reads the learner's latest message and routes it to exactly one
of four specialists (writing corrector, vocab coach, grammar teacher, quiz master).

All configuration comes from environment variables, so the same code runs
locally, in a container, and in dev / test / prod without changes.
"""

import logging
import os
from typing import Literal

from langchain_core.messages import AIMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, MessagesState, StateGraph
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Options shown in the UI. The first entry of each list is the default.
LANGUAGES = ["German", "French", "Spanish", "Italian", "Japanese", "Korean", "English"]
EXPLAIN_IN = ["English", "Chinese", "German"]
LEVELS = ["intermediate", "beginner", "advanced"]

DEFAULT_SETTINGS = {"target": LANGUAGES[0], "explain_in": EXPLAIN_IN[0], "level": LEVELS[0]}


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------

def build_llm():
    """Create the chat model based on LLM_PROVIDER.

    azure      -> Azure OpenAI, authenticated with Entra ID (no API key).
                  Locally this uses your `az login`; in Azure it uses the
                  app's managed identity.
    anthropic  -> temporary option for local testing before the Azure OpenAI
                  resource exists (step 5). Needs ANTHROPIC_API_KEY.
    """
    provider = os.getenv("LLM_PROVIDER", "azure").lower()

    if provider == "azure":
        from azure.identity import DefaultAzureCredential, get_bearer_token_provider
        from langchain_openai import AzureChatOpenAI

        token_provider = get_bearer_token_provider(
            DefaultAzureCredential(), "https://cognitiveservices.azure.com/.default"
        )
        return AzureChatOpenAI(
            azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
            azure_deployment=os.environ["AZURE_OPENAI_DEPLOYMENT"],
            api_version=os.environ["AZURE_OPENAI_API_VERSION"],
            azure_ad_token_provider=token_provider,
        )

    if provider == "anthropic":
        from langchain.chat_models import init_chat_model

        model = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5-5")
        return init_chat_model(f"anthropic:{model}")

    raise ValueError(f"Unknown LLM_PROVIDER '{provider}'. Use 'azure' or 'anthropic'.")


# ---------------------------------------------------------------------------
# State, routing and prompts
# ---------------------------------------------------------------------------

class State(MessagesState):
    route: str  # the supervisor's decision


class Route(BaseModel):
    next: Literal["writing_corrector", "vocab", "grammar_teacher", "quiz"]


SUPERVISOR_PROMPT = """
You are the router of a {target} learning assistant.
Pick the specialist for the user's latest message. Do not answer it yourself.
- writing_corrector: the user submits their own {target} text (e.g. a diary entry) for correction
- vocab: the user asks what a {target} word means, or how to say something in {target}
- grammar_teacher: the user wants a {target} grammar topic explained
- quiz: the user asks for practice exercises, or is answering a quiz
"""

PROMPTS = {
    "writing_corrector": """You are a {target} writing tutor for a {level} learner. Correct the learner's text:
1. Give the fully corrected text.
2. List each error, what was wrong, and the rule behind it.
3. End with one or two things to focus on next time.
Explain in {explain_in}.""",

    "vocab": """You are a {target} vocabulary coach for a {level} learner. For the word or phrase asked about, give:
1. meaning(s)
2. the grammatical details that matter in {target} (e.g. gender, plural, irregular forms, reading/pronunciation)
3. 2-3 natural example sentences with translations
4. a few related words (synonyms, word family, common collocations)
Explain in {explain_in}. Keep it short.""",

    "grammar_teacher": """You are a {target} grammar teacher for a {level} learner.
Explain the requested topic systematically: when it is used, how it is formed,
examples, common mistakes, and 2-3 short exercises with answers at the end. Explain in {explain_in}.""",

    "quiz": """You are a {target} quiz master for a {level} learner.
If the user asks for a quiz: write 10 numbered questions (mixed: fill-in-the-blank, error correction,
translation) and do NOT show the answers.
If the user is answering: grade each answer, give the correct answer and a short explanation,
then the total score. Instructions and feedback in {explain_in}.""",
}


def get_settings(config: RunnableConfig) -> dict:
    """Read the learner's settings from the run config, falling back to defaults.

    In the notebook these were globals. In a web app every user has their own
    settings, so they travel with each call instead.
    """
    passed = config.get("configurable", {}).get("settings", {})
    return {**DEFAULT_SETTINGS, **passed}


def get_text(msg) -> str:
    """Return only the answer text, skipping any thinking blocks."""
    if isinstance(msg.content, str):
        return msg.content
    return "".join(block.get("text", "") for block in msg.content if block.get("type") == "text")


# ---------------------------------------------------------------------------
# Graph
# ---------------------------------------------------------------------------

def build_graph(llm=None):
    """Build and compile the supervisor + specialists graph."""
    llm = llm or build_llm()
    router = llm.with_structured_output(Route, method="json_schema")

    def supervisor(state: State, config: RunnableConfig):
        settings = get_settings(config)
        decision = router.invoke(
            [SystemMessage(SUPERVISOR_PROMPT.format(**settings)), *state["messages"][-4:]]
        )
        logger.info("route -> %s", decision.next)
        return {"route": decision.next}

    def make_agent(name: str):
        """Build a graph node for the agent 'name' from its prompt template."""
        def agent(state: State, config: RunnableConfig):
            settings = get_settings(config)
            prompt = PROMPTS[name].format(**settings)
            reply = llm.invoke([SystemMessage(prompt), *state["messages"][-6:]])
            return {"messages": [AIMessage(get_text(reply), name=name)]}
        return agent

    builder = StateGraph(State)
    builder.add_node("supervisor", supervisor)
    for name in PROMPTS:
        builder.add_node(name, make_agent(name))
        builder.add_edge(name, END)
    builder.add_edge(START, "supervisor")
    builder.add_conditional_edges("supervisor", lambda s: s["route"], list(PROMPTS))

    # In-memory conversation history, kept per thread_id.
    # It is lost when the app restarts; persistent memory comes later.
    return builder.compile(checkpointer=InMemorySaver())
