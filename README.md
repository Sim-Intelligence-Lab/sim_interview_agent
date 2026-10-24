# Interview Studio

A Flask interface for interviewing the Trang Thai and Raju Nekadi
generative agents. It uses the AgentBank memory stream to retrieve relevant
experiences, asks the prepared factual and reflective questions, and saves each
answer with the supporting memories used to produce it.

## Run locally

Everything runs on your machine through [Ollama](https://ollama.com); no API key is needed.

```sh
ollama pull qwen3:4b-instruct
ollama pull qwen3-embedding:0.6b
pip install -r requirements.txt
PORT=5050 python interview_app.py
```

Open <http://127.0.0.1:5050>. On macOS, port 5000 is often taken by AirPlay.

The saved memories were embedded with `qwen3-embedding:0.6b`, so keep that
embedding model. You can swap the chat model with `LLM_MODEL`.

## Interviews

Choose Trang or Raju, then ask each of the 10 factual and 5 reflective
questions in order. Answers and their retrieved memory notes are saved after
every question in `interviews/`. At the end, download
the transcript as JSON or CSV. These generated interview records are kept local
and are excluded from Git.

## Project layout

```
interview_app.py        Flask app and API
interview_templates/    Page HTML
interview_static/       CSS, JS, and avatars
questions/              Interview questions for each person
agent_bank/interviewees/ Saved agent memories and embeddings
generative_agent/       Memory retrieval and answer generation
simulation_engine/      Settings, Ollama client, and prompt templates
interviews/             Saved transcripts (local only, not in Git)
```
