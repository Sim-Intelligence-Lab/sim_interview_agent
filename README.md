# Simulated Interview Agent

A Flask interface for interviewing the Jasmine Carter and Matthew Jacobs
SyntheticCS222 agents. It uses the AgentBank memory stream to retrieve relevant
experiences, asks the prepared factual and reflective questions, and saves each
answer with the supporting memories used to produce it.

## Run locally

Install the packages in `requirements.txt`, then choose a model backend.

For OpenAI:

```sh
export OPENAI_API_KEY="your-api-key"
python interview_app.py
```

For a local Ollama server, start Ollama and make sure its chat and embedding
models are available, then run:

```sh
MODEL_BACKEND=ollama python interview_app.py
```

The app opens at <http://127.0.0.1:5000>. Set `PORT` to use a different port.

## Interviews

Choose Jasmine or Matthew, then ask each of the 10 factual and 5 reflective
questions in order. Answers and their retrieved memory notes are saved after
every question in `cs222_assignment_1/report/interviews/`. At the end, download
the transcript as JSON or CSV. These generated interview records are kept local
and are excluded from Git.

The saved agent memories live in `agent_bank/populations/SyntheticCS222/`.
