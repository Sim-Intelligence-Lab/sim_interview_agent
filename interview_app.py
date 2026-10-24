"""Interview Studio: a local web UI for interviewing generative agents."""

import csv
import io
import json
import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, abort, jsonify, render_template, request, send_file, url_for

from questions.trang_thai import (
    factual_questions as trang_factual,
    reflective_questions as trang_reflective,
)
from questions.raju_nekadi import (
    factual_questions as raju_factual,
    reflective_questions as raju_reflective,
)
from generative_agent.generative_agent import GenerativeAgent
from simulation_engine.settings import EMBEDDING_MODEL, LLM_VERS


ROOT = Path(__file__).resolve().parent
SESSION_DIR = ROOT / "interviews"
PEOPLE = {
    "trang_thai": {
        "name": "Trang Thai",
        "population": "interviewees",
        "factual": trang_factual,
        "reflective": trang_reflective,
        "intro": "Environmental advocate, organizer, and community leader.",
    },
    "raju_nekadi": {
        "name": "Raju Nekadi",
        "population": "interviewees",
        "factual": raju_factual,
        "reflective": raju_reflective,
        "intro": "Austin real estate agent, father, and local political advocate.",
    },
}

app = Flask(__name__, template_folder="interview_templates", static_folder="interview_static")
_agents = {}
_sessions = {}


def _questions(person_id):
    person = PEOPLE[person_id]
    return ([{"text": q, "kind": "factual"} for q in person["factual"]]
            + [{"text": q, "kind": "reflective"} for q in person["reflective"]])


def _agent(person_id):
    if person_id not in _agents:
        person = PEOPLE[person_id]
        agent = GenerativeAgent(person["population"], person_id)
        if not hasattr(agent, "memory_stream"):
            raise RuntimeError(f"Saved memories for {person['name']} were not found.")
        _agents[person_id] = agent
    return _agents[person_id]


def _save_session(session):
    SESSION_DIR.mkdir(parents=True, exist_ok=True)
    target = SESSION_DIR / f"{session['id']}.json"
    fd, temp_name = tempfile.mkstemp(prefix=".interview-", suffix=".tmp", dir=SESSION_DIR)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            json.dump(session, output, ensure_ascii=False, indent=2)
            output.write("\n")
        os.replace(temp_name, target)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def _get_session(session_id):
    session = _sessions.get(session_id)
    if session is None:
        abort(404, description="Interview session not found. Start a new interview.")
    return session


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/people")
def people():
    return jsonify([
        {"id": person_id, "name": person["name"], "intro": person["intro"],
         "question_count": len(_questions(person_id)),
         "avatar_url": url_for("static", filename=f"avatars/{person_id}.svg"),
         "questions": _questions(person_id)}
        for person_id, person in PEOPLE.items()
    ])


@app.post("/api/sessions")
def start_session():
    data = request.get_json(silent=True) or {}
    person_id = data.get("person_id")
    if person_id not in PEOPLE:
        return jsonify(error="Choose a supported interview subject."), 400

    session_id = str(uuid.uuid4())
    questions = _questions(person_id)
    session = {
        "id": session_id,
        "person_id": person_id,
        "person_name": PEOPLE[person_id]["name"],
        "started_at": datetime.now(timezone.utc).isoformat(),
        "status": "in_progress",
        "current_index": 0,
        "questions": questions,
        "question_status": ["pending"] * len(questions),
        "answers": [],
    }
    _sessions[session_id] = session
    _save_session(session)
    return jsonify({
        "session_id": session_id,
        "person_name": session["person_name"],
        "questions": questions,
        **_progress(session),
    })


def _progress(session):
    """Where the interview stands, sent back after every change."""
    status = session["question_status"]
    return {
        "current_index": session["current_index"],
        "question_status": status,
        "answered_count": status.count("answered"),
        "skipped_count": status.count("skipped"),
        "question_count": len(status),
        "complete": session["status"] == "complete",
    }


def _advance(session):
    """Move to the next pending question after the current one, wrapping
    around. If none are left, mark the interview complete."""
    status = session["question_status"]
    count = len(status)
    for step in range(1, count + 1):
        index = (session["current_index"] + step) % count
        if status[index] == "pending":
            session["current_index"] = index
            return
    session["status"] = "complete"
    session["completed_at"] = datetime.now(timezone.utc).isoformat()


def _question_index(session, data):
    index = data.get("question_index", session["current_index"])
    if not isinstance(index, int) or not 0 <= index < len(session["questions"]):
        abort(400, description="Unknown question.")
    return index


@app.post("/api/sessions/<session_id>/select")
def select_question(session_id):
    """Jump to any question that hasn't been answered yet, including skipped ones."""
    session = _get_session(session_id)
    index = _question_index(session, request.get_json(silent=True) or {})
    if session["question_status"][index] == "answered":
        return jsonify(error="That question has already been answered."), 409
    session["current_index"] = index
    session["status"] = "in_progress"
    _save_session(session)
    return jsonify(_progress(session))


@app.post("/api/sessions/<session_id>/skip")
def skip_question(session_id):
    session = _get_session(session_id)
    if session["status"] == "complete":
        return jsonify(error="This interview is already complete."), 409
    session["question_status"][session["current_index"]] = "skipped"
    _advance(session)
    _save_session(session)
    return jsonify(_progress(session))


@app.post("/api/sessions/<session_id>/answer")
def answer_question(session_id):
    session = _get_session(session_id)
    question_index = _question_index(session, request.get_json(silent=True) or {})
    if session["question_status"][question_index] == "answered":
        return jsonify(error="That question has already been answered."), 409
    session["current_index"] = question_index
    question = session["questions"][question_index]
    try:
        agent = _agent(session["person_id"])
        memory_scores = agent.memory_stream.retrieve_with_scores(question["text"], n_count=5)
        memory_notes = [memory["content"] for memory in memory_scores]
        evidence = "\n".join(f"- {memory}" for memory in memory_notes)
        if question["kind"] == "factual":
            guidance = (
                "Answer this factual interview question using only what the memories "
                "explicitly state. If they do not contain the answer, say you do not recall."
            )
        else:
            guidance = (
                "This is a reflective interview question. Consider the relevant memories "
                "and explain what those documented experiences taught you. Do not invent events."
            )
        context = (
            f"{guidance}\n\nRelevant memories retrieved for this question:\n{evidence}\n\n"
            "Think through the memories privately, then give a concise first-person answer. "
            "Do not reveal private reasoning or mention this context."
        )
        response = agent.utterance([["Interviewer", question["text"]]], context=context)
        if not isinstance(response, str) or not response.strip():
            raise RuntimeError("The agent returned an empty answer.")
    except Exception as exc:
        message = str(exc)
        if "Connection error" in message or "Connection refused" in message:
            message = "Ollama is not running. Start it with `ollama serve` and try again."
        elif "model" in message and "not found" in message:
            message = f"Missing Ollama model. Run: ollama pull {LLM_VERS} && ollama pull {EMBEDDING_MODEL}"
        app.logger.exception("Interview answer generation failed")
        return jsonify(error=message), 503

    answer = {
        "question_index": question_index,
        "kind": question["kind"],
        "question": question["text"],
        "response": response.strip(),
        "supporting_memories": memory_notes,
        "memory_scores": [
            {key: round(value, 4) if isinstance(value, float) else value
             for key, value in memory.items()}
            for memory in memory_scores
        ],
        "answered_at": datetime.now(timezone.utc).isoformat(),
    }
    session["answers"].append(answer)
    session["question_status"][question_index] = "answered"
    _advance(session)
    _save_session(session)
    return jsonify({"answer": answer, **_progress(session)})


@app.get("/api/sessions/<session_id>/download")
def download_session(session_id):
    session = _get_session(session_id)
    export_format = request.args.get("format", "json").lower()
    if export_format == "csv":
        stream = io.StringIO(newline="")
        writer = csv.writer(stream)
        writer.writerow(["subject", "question_type", "question", "response",
                         "supporting_memories", "memory_scores"])
        for answer in session["answers"]:
            scores = " | ".join(f"{m['score']:.2f}" for m in answer.get("memory_scores", []))
            writer.writerow([
                session["person_name"], answer["kind"], answer["question"],
                answer["response"], " | ".join(answer["supporting_memories"]), scores,
            ])
        payload = io.BytesIO(stream.getvalue().encode("utf-8-sig"))
        return send_file(payload, mimetype="text/csv", as_attachment=True,
                         download_name=f"{session['person_id']}_{session_id}.csv")
    if export_format != "json":
        return jsonify(error="format must be json or csv"), 400
    path = SESSION_DIR / f"{session_id}.json"
    return send_file(path, mimetype="application/json", as_attachment=True,
                     download_name=f"{session['person_id']}_{session_id}.json")


@app.errorhandler(400)
@app.errorhandler(404)
def api_error(error):
    if request.path.startswith("/api/"):
        return jsonify(error=error.description), error.code
    return error


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "5000")), debug=False)
