const state = { person: null, sessionId: null, questions: [], index: 0, busy: false };
const $ = (id) => document.getElementById(id);

async function api(url, options = {}) {
  const response = await fetch(url, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "The request could not be completed.");
  return data;
}

function setBusy(busy) {
  state.busy = busy;
  $("ask").disabled = busy;
  $("next").disabled = busy;
  $("ask").textContent = busy ? "Thinking…" : "Ask this question →";
}

function renderPeople(people) {
  const container = $("people");
  container.replaceChildren();
  people.forEach((person) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "person-option";
    button.dataset.person = person.id;
    button.innerHTML = '<img class="person-avatar" alt=""><span class="person-info"><b></b><small></small></span><span class="person-arrow">↗</span>';
    button.querySelector(".person-avatar").src = person.avatar_url;
    button.querySelector(".person-avatar").alt = `${person.name} illustrated avatar`;
    button.querySelector("b").textContent = person.name;
    button.querySelector("small").textContent = person.intro;
    button.addEventListener("click", () => {
      state.person = person;
      document.querySelectorAll(".person-option").forEach((item) => item.classList.toggle("selected", item === button));
      $("start").disabled = false;
      $("setup-error").textContent = "";
    });
    container.append(button);
  });
}

function renderQuestion() {
  const question = state.questions[state.index];
  $("question-type").textContent = `QUESTION ${String(state.index + 1).padStart(2, "0")} · ${question.kind.toUpperCase()}`;
  $("current-question").textContent = question.text;
  $("progress-label").textContent = `${state.index} / ${state.questions.length}`;
  $("progress-bar").style.width = `${(state.index / state.questions.length) * 100}%`;
  document.querySelectorAll(".question-item").forEach((item, index) => {
    item.classList.toggle("current", index === state.index);
    item.classList.toggle("answered", index < state.index);
  });
  if (!$("answer-area").querySelector(".answer-card")) {
    $("answer-area").innerHTML = '<div class="empty-state"><span class="sound-wave">〰</span><p>Your interviewee is ready when you are.</p><small>Ask the question to hear their response.</small></div>';
  }
  $("ask").classList.remove("hidden");
  $("next").classList.add("hidden");
  $("download-json").classList.add("hidden");
  $("interview-error").textContent = "";
  $("progress-label").textContent = `${state.index} / ${state.questions.length}`;
}

function renderAnswer(result) {
  const bubble = document.createElement("article");
  bubble.className = "answer-card";
  const question = document.createElement("p");
  question.className = "answer-question";
  question.textContent = result.answer.question;
  const label = document.createElement("div");
  label.className = "answer-person";
  const avatar = document.createElement("img");
  avatar.className = "answer-avatar";
  avatar.src = state.person.avatar_url;
  avatar.alt = "";
  const name = document.createElement("span");
  name.className = "answer-label";
  name.textContent = `${state.person.name} · RESPONSE`;
  label.append(avatar, name);
  const text = document.createElement("p");
  text.className = "answer-text";
  text.textContent = result.answer.response;
  const details = document.createElement("details");
  details.className = "answer-memories";
  const summary = document.createElement("summary");
  summary.textContent = `Memories considered (${result.answer.supporting_memories.length})`;
  const list = document.createElement("ul");
  result.answer.supporting_memories.forEach((memory) => {
    const item = document.createElement("li");
    item.textContent = memory;
    list.append(item);
  });
  details.append(summary, list);
  bubble.append(question, label, text, details);
  $("answer-area").querySelector(".empty-state")?.remove();
  $("answer-area").append(bubble);
  bubble.scrollIntoView({ behavior: "smooth", block: "nearest" });
  $("ask").classList.add("hidden");
  $("progress-label").textContent = `${result.answered_count} / ${result.question_count}`;
  $("progress-bar").style.width = `${(result.answered_count / result.question_count) * 100}%`;

  if (result.complete) {
    $("question-list").lastElementChild?.classList.add("answered");
    $("action-note").textContent = "Interview complete · your transcript is ready.";
    $("download-json").href = `/api/sessions/${state.sessionId}/download?format=json`;
    $("download-json").classList.remove("hidden");
    const csv = document.createElement("a");
    csv.className = "text-link";
    csv.href = `/api/sessions/${state.sessionId}/download?format=csv`;
    csv.download = "";
    csv.textContent = "CSV version";
    $("action-note").append(" · ", csv);
    $("next").classList.add("hidden");
  } else {
    state.index = result.next_question_index;
    $("question-list").children[state.index - 1]?.classList.add("answered");
    $("question-list").children[state.index]?.classList.add("current");
    $("next").classList.remove("hidden");
    $("action-note").textContent = "Response saved · review the memory notes or continue.";
  }
}

async function startInterview() {
  if (!state.person || state.busy) return;
  $("start").disabled = true;
  $("setup-error").textContent = "";
  try {
    const session = await api("/api/sessions", {
      method: "POST", body: JSON.stringify({ person_id: state.person.id }),
    });
    state.sessionId = session.session_id;
    state.index = 0;
    state.questions = [...session.questions];
    $("subject-name").textContent = session.person_name;
    $("subject-avatar").src = state.person.avatar_url;
    $("subject-avatar").alt = `${session.person_name} illustrated avatar`;
    $("subject-intro").textContent = state.person.intro;
    const list = $("question-list");
    list.replaceChildren();
    state.questions.forEach((question, index) => {
      const item = document.createElement("li");
      item.className = `question-item${index === 0 ? " current" : ""}`;
      item.innerHTML = `<span class="question-number">${String(index + 1).padStart(2, "0")}</span><span class="question-preview"></span><span class="question-check">✓</span>`;
      item.querySelector(".question-preview").textContent = question.text;
      list.append(item);
    });
    $("setup").classList.add("hidden");
    $("interview").classList.remove("hidden");
    $("action-note").textContent = "Each response is saved as you go.";
    renderQuestion();
    window.scrollTo({ top: 0, behavior: "smooth" });
  } catch (error) {
    $("setup-error").textContent = error.message;
    $("start").disabled = false;
  }
}

async function askQuestion() {
  if (!state.sessionId || state.busy) return;
  setBusy(true);
  $("interview-error").textContent = "";
  try {
    const result = await api(`/api/sessions/${state.sessionId}/answer`, { method: "POST", body: "{}" });
    renderAnswer(result);
  } catch (error) {
    $("interview-error").textContent = error.message;
  } finally {
    setBusy(false);
  }
}

$("start").addEventListener("click", startInterview);
$("ask").addEventListener("click", askQuestion);
$("next").addEventListener("click", () => {
  if (state.busy) return;
  $("action-note").textContent = "Each response is saved as you go.";
  renderQuestion();
  window.scrollTo({ top: 0, behavior: "smooth" });
});
api("/api/people").then(renderPeople).catch((error) => { $("setup-error").textContent = error.message; });
