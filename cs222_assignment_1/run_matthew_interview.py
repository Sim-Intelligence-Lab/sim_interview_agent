"""Build Matthew and record a stateless, 15-question interview."""

import csv
import json
import argparse
from pathlib import Path

from simulation_engine.settings import (
    EMBEDDING_MODEL,
    LLM_VERS,
    MODEL_BACKEND,
    OPENAI_API_KEY,
)

if MODEL_BACKEND == "openai" and not OPENAI_API_KEY:
    raise SystemExit("Set OPENAI_API_KEY in your environment before running the interview.")

from cs222_assignment_1.memories.matthew_jacobs_memories import matthew_memories
from cs222_assignment_1.questions.matthew_jacobs_questions import (
    factual_questions,
    reflective_questions,
)
from generative_agent.generative_agent import GenerativeAgent
from simulation_engine.gpt_structure import _client


def check_local_models() -> None:
    if MODEL_BACKEND != "ollama":
        return
    try:
        available = {model.id for model in _client().models.list().data}
    except Exception as exc:
        raise SystemExit("Ollama is not running. Start it with `ollama serve`.") from exc
    missing = {LLM_VERS, EMBEDDING_MODEL} - available
    if missing:
        pulls = "\n".join(f"ollama pull {model}" for model in sorted(missing))
        raise SystemExit(f"Download the missing local models:\n{pulls}")


def main(interview_only: bool = False) -> None:
    check_local_models()
    if interview_only:
        agent = GenerativeAgent("SyntheticCS222", "matthew_jacobs")
    else:
        agent = GenerativeAgent("SyntheticCS222_Base", "matthew_jacobs")
        for index, memory in enumerate(matthew_memories, start=1):
            agent.remember(memory)
            if index % 10 == 0:
                print(f"Loaded {index}/{len(matthew_memories)} memories", flush=True)
        agent.save("SyntheticCS222", "matthew_jacobs")

    answers = []
    retrieved = {}
    for question in factual_questions + reflective_questions:
        nodes = agent.memory_stream.retrieve([question], time_step=0, n_count=10)[question]
        if len(nodes) != 10:
            raise RuntimeError(f"Expected 10 memories for: {question}")
        retrieved[question] = [node.content for node in nodes]

        # A fresh, one-turn dialogue keeps every interview answer stateless.
        if question in factual_questions:
            context = (
                "This is a factual interview question. The most directly relevant "
                f"memory is: {retrieved[question][0]} "
                "Answer only with the facts this memory states. Omit any detail "
                "that it does not state."
            )
        else:
            context = (
                "This is a reflective interview question. Explain how the "
                "documented experiences affected you without adding new events."
            )
        response = agent.utterance([["Interviewer", question]], context=context)
        if not isinstance(response, str) or not response.strip():
            raise RuntimeError(f"No valid response for: {question}")
        answers.append((question, response))
        print(f"Answered {len(answers)}/15: {question}", flush=True)

    report_dir = Path(__file__).resolve().parent / "report" / "matthew_jacobs"
    report_dir.mkdir(parents=True, exist_ok=True)
    with (report_dir / "answers__matthew_jacobs.csv").open(
        "w", newline="", encoding="utf-8"
    ) as file:
        csv.writer(file).writerows(answers)
    with (report_dir / "retrieved__matthew_jacobs.json").open(
        "w", encoding="utf-8"
    ) as file:
        json.dump(retrieved, file, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--interview-only", action="store_true",
        help="Reuse the saved agent without rebuilding its memories.",
    )
    main(interview_only=parser.parse_args().interview_only)
