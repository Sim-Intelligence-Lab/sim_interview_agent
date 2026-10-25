# Interview Studio

A Flask interface for interviewing Trang, a generative agent. It uses the AgentBank memory stream to retrieve relevant
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

Start an interview with Trang, an environmental advocate who is now a law
student, and work through the 12 factual and 6 reflective questions. You can skip a question, jump to a random one, or click any question
in the list. Answers and their retrieved memory notes are saved after
every question in `interviews/`. At the end, download
the transcript as JSON or CSV. These generated interview records are kept local
and are excluded from Git.

## Project layout

```
interview_app.py        Flask app and API
interview_templates/    Page HTML
interview_static/       CSS, JS, and avatars
questions/              Interview questions
agent_bank/interviewees/ Trang's saved memories and embeddings
generative_agent/       Memory retrieval and answer generation
simulation_engine/      Settings, Ollama client, and prompt templates
interviews/             Saved transcripts (local only, not in Git)
```
