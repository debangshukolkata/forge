# AgentHub

A small agent platform. Agents answer questions by calling tools; the tools and the agents are rows in a
database, not code.

## Start

```
python -m agenthub.server
```

It listens on `http://127.0.0.1:8765` (set `PORT` to change it) and reads its settings from the `.env` file in
this folder. The database is the SQLite file named by `HUB_DATABASE` (default `data/hub.db`); it is created and
filled from `agenthub/seed.sql` the first time the server starts.

## Use

Every call needs a token from the AgentHub console: `Authorization: Bearer <token>`.

- `GET /api/agents` lists the agents.
- `POST /api/agents/<name>/run` with `{"question": "..."}` runs an agent.

Every run is written to `logs/runs.jsonl`.
