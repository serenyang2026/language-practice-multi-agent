# langagent – Language Practice Multi-Agent

A small multi-agent app for practising a foreign language. A **supervisor** reads each message and routes it to one of four specialists:

| Agent | Handles |
|---|---|
| `writing_corrector` | Your own text (e.g. a diary entry) to correct |
| `vocab` | "What does X mean?" / "How do I say Y?" |
| `grammar_teacher` | Explaining a grammar topic |
| `quiz` | Creating a quiz, and grading your answers |

Built with LangGraph and Streamlit. Deployed to Azure Container Apps (dev / test / prod) via Azure Pipelines.

## Project structure

```
agent.py           # graph: supervisor + 4 specialists, model setup
app.py             # Streamlit chat UI
requirements.txt   # Python dependencies
.env.example       # configuration template (copy to .env, never commit .env)
```

## Run locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # then fill in the values
streamlit run app.py
```

## Configuration

All settings come from environment variables (see `.env.example`):

| Variable | Purpose |
|---|---|
| `LLM_PROVIDER` | `azure` (target) or `anthropic` (temporary local testing) |
| `AZURE_OPENAI_ENDPOINT` / `AZURE_OPENAI_DEPLOYMENT` / `AZURE_OPENAI_API_VERSION` | Azure OpenAI model. Auth via Entra ID, no API key |
| `ANTHROPIC_API_KEY` / `ANTHROPIC_MODEL` | Only when `LLM_PROVIDER=anthropic` |
