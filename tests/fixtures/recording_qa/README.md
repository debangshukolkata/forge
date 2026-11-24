# RecQA

A small service for recordings. A recording is a text file in `recordings/<id>.txt`: one line per moment,
`HH:MM:SS | speech: ... | screen: ...` (what is said and what is seen), as a video would be given to a model.

- `recqa/server.py` the HTTP API, `recqa/recordings.py` reads a recording, `recqa/store.py` SQLite,
  `recqa/model.py` the language model (`complete(prompt)`).
- Start: `python -m recqa.server` (port from `RECQA_PORT`, default 8790). Needs the AZURE_OPENAI_* variables.
