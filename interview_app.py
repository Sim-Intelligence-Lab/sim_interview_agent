"""Local web interview UI for the SyntheticCS222 generative agents."""

import csv
import io
import json
import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, abort, jsonify, render_template, request, send_file

from cs222_assignment_1.questions.jasmine_carter_questions import (
    factual_questions as jasmine_factual,
    reflective_questions as jasmine_reflective,
)
from cs222_assignment_1.questions.matthew_jacobs_questions import (
    factual_questions as matthew_factual,
    reflective_questions as matthew_reflective,
)
from generative_agent.generative_agent import GenerativeAgent
from simulation_engine.settings import MODEL_BACKEND, OPENAI_API_KEY


ROOT = Path(__file__).resolve().parent
SESSION_DIR = ROOT / "cs222_assignment_1" / "report" / "interviews"
PEOPLE = {
    "jasmine_carter": {
        "name": "Jasmine Carter",
        "population": "SyntheticCS222",
        "factual": jasmine_factual,
        "reflective": jasmine_reflective,
        "intro": "Environmental advocate, organizer, and community leader.",
    },
    "matthew_jacobs": {
        "name": "Matthew Jacobs",
        "population": "SyntheticCS222",
        "factual": matthew_factual,
        "reflective": matthew_reflective,
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
        "answers": [],
    }
    _sessions[session_id] = session
    _save_session(session)
    return jsonify({
        "session_id": session_id,
        "person_name": session["person_name"],
        "question_count": len(questions),
        "question_index": 0,
        "question": questions[0],
        "questions": questions,
    })


@app.post("/api/sessions/<session_id>/answer")
def answer_question(session_id):
    session = _get_session(session_id)
    if session["status"] == "complete":
        return jsonify(error="This interview is already complete."), 409

    question_index = session["current_index"]
    question = session["questions"][question_index]
    try:
        agent = _agent(session["person_id"])
        retrieved = agent.memory_stream.retrieve(
            [question["text"]], time_step=len(session["answers"]), n_count=5
        )[question["text"]]
        memory_notes = [node.content for node in retrieved]
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
        if MODEL_BACKEND == "openai" and not OPENAI_API_KEY:
            message = "Set OPENAI_API_KEY (or configure a local backend) before asking questions."
        app.logger.exception("Interview answer generation failed")
        return jsonify(error=message), 503

    answer = {
        "question_index": question_index,
        "kind": question["kind"],
        "question": question["text"],
        "response": response.strip(),
        "supporting_memories": memory_notes,
        "answered_at": datetime.now(timezone.utc).isoformat(),
    }
    session["answers"].append(answer)
    session["current_index"] += 1
    complete = session["current_index"] == len(session["questions"])
    if complete:
        session["status"] = "complete"
        session["completed_at"] = datetime.now(timezone.utc).isoformat()
    _save_session(session)

    next_question = (
        session["questions"][session["current_index"]]
        if not complete else None
    )
    return jsonify({
        "answer": answer,
        "complete": complete,
        "answered_count": len(session["answers"]),
        "question_count": len(session["questions"]),
        "next_question_index": session["current_index"],
        "next_question": next_question,
    })


@app.get("/api/sessions/<session_id>/download")
def download_session(session_id):
    session = _get_session(session_id)
    export_format = request.args.get("format", "json").lower()
    if export_format == "csv":
        stream = io.StringIO(newline="")
        writer = csv.writer(stream)
        writer.writerow(["subject", "question_type", "question", "response", "supporting_memories"])
        for answer in session["answers"]:
            writer.writerow([
                session["person_name"], answer["kind"], answer["question"],
                answer["response"], " | ".join(answer["supporting_memories"]),
            ])
        payload = io.BytesIO(stream.getvalue().encode("utf-8-sig"))
        return send_file(payload, mimetype="text/csv", as_attachment=True,
                         download_name=f"{session['person_id']}_{session_id}.csv")
    if export_format != "json":
        return jsonify(error="format must be json or csv"), 400
    path = SESSION_DIR / f"{session_id}.json"
    return send_file(path, mimetype="application/json", as_attachment=True,
                     download_name=f"{session['person_id']}_{session_id}.json")


@app.errorhandler(404)
def not_found(error):
    if request.path.startswith("/api/"):
        return jsonify(error=error.description), 404
    return error


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "5000")), debug=False)
