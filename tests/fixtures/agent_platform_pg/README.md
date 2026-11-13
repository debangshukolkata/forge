# AgentHub PG

A small agent platform, closer to a real one than AgentHub: the agents are LangGraph tool-calling agents on a
real Azure OpenAI model, and the agents, their system prompts and their tools are rows in PostgreSQL.

## Start

```
venv\Scripts\python -m agenthub_pg.server
```

It listens on `http://127.0.0.1:8766` (`APP_PORT` changes it) and reads its settings from the environment and
from the `.env` file in this folder (a pydantic settings class: every name starts with `APP_`):

- `APP_DATABASE_URL` the PostgreSQL URL, `APP_SCHEMA_NAME` the schema to use (default `public`);
- `APP_CONSOLE_TOKEN_SHA256` the SHA-256 of the console token;
- `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_API_VERSION`, `AZURE_OPENAI_DEPLOYMENT` the model
  the agents use.

The tables are created (and the agents, prompts and tools filled) from `agenthub_pg/seed.sql` the first time the server starts on an empty schema. The deployment system's state is the `applications` table; the seed creates it empty, a real database holds the applications (`agenthub_pg/sample_data.py` generates rows for a test database).
The fixture's own packages are in `requirements.txt` (the test suite makes `venv` from it).

## Use

Every call needs a token from the AgentHub console: `Authorization: Bearer <token>`.

- `GET /api/agents` lists the agents (`ops`, `billing`, `support`).
- `POST /api/agents/<name>/run` with `{"question": "..."}` runs an agent.
- `POST /api/agents/<name>/stream` runs it the same way and answers as server-sent events, one per step (`run_started`, `tool_call`, `tool_result`, then `final` or `error`).

Every run is written to `logs/runs.jsonl`.

## Two things that do not work

- The `ops` agent cannot answer "What are the names of the deployments?".
- The `support` agent does not answer in the language its customer writes in.
