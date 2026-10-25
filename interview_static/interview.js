const state = {
  person: null, sessionId: null, questions: [], status: [], index: 0,
  complete: false, busy: false, awaitingNext: false,
};
const $ = (id) => document.getElementById(id);
const show = (id, visible) => $(id).classList.toggle("hidden", !visible);
const EMPTY_STATE = '<div class="empty-state"><span class="wave" aria-hidden="true"><i></i><i></i><i></i><i></i><i></i></span><p>Ready when you are.</p><small>Ask the question to hear the response.</small></div>';

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
  ["ask", "next", "skip", "random"].forEach((id) => { $(id).disabled = busy; });
  $("ask").textContent = busy ? "thinking…" : "ask this question";
  $("question-list").classList.toggle("locked", busy);
  if (busy) setMood("thinking");
  else if (!delivery) setMood("listening");
}

// ---------- Portrait: thinking and speaking ----------

const portraitCache = {};
let delivery = null;

async function loadPortrait(person) {
  const portrait = $("subject-avatar");
  portrait.setAttribute("aria-label", `${person.name}, pixel portrait`);
  try {
    if (!portraitCache[person.id]) portraitCache[person.id] = await (await fetch(person.avatar_url)).text();
    portrait.innerHTML = portraitCache[person.id];
  } catch {
    portrait.replaceChildren(Object.assign(document.createElement("img"), { src: person.avatar_url, alt: "" }));
  }
}

function setMood(mood) {
  $("interview").classList.toggle("thinking", mood === "thinking");
  $("interview").classList.toggle("speaking", mood === "speaking");
  $("speaker-status").textContent = { thinking: "thinking…", speaking: "speaking…" }[mood] || "listening";
}

// Types the answer into `element` while her mouth moves, then calls onDone.
function deliver(element, text, onDone) {
  stopDelivery();
  const run = { shown: 0, done: false };
  delivery = run;
  setMood("speaking");
  run.finish = () => {
    if (run.done) return;
    run.done = true;
    clearInterval(run.timer);
    element.textContent = text;
    if (delivery === run) {
      delivery = null;
      setMood(state.busy ? "thinking" : "listening");
    }
    onDone?.();
  };
  // About a natural speaking pace: one word every ~180 ms.
  const words = text.split(/(?<=\s)/);
  let count = 0;
  run.timer = setInterval(() => {
    count += 1;
    element.textContent = words.slice(0, count).join("");
    if (count >= words.length) run.finish();
  }, 180);
}

function stopDelivery() {
  delivery?.finish();
}

// ---------- People ----------

function renderPeople(people) {
  const container = $("people");
  const counts = [...new Set(people.map((person) => person.question_count))];
  $("question-total").textContent = counts.length === 1 ? `${counts[0]} questions` : "";
  container.replaceChildren();
  people.forEach((person) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "person-option";
    button.dataset.person = person.id;
    button.innerHTML = '<span class="titlebar"><span class="dots" aria-hidden="true"><i></i><i></i><i></i></span><span class="pixel"></span></span><span class="person-media"><img class="person-avatar" alt=""></span><span class="person-info"><b></b><small></small></span>';
    button.querySelector(".titlebar .pixel").textContent = `${person.question_count} questions`;
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
  if (people.length === 1) container.querySelector(".person-option").click();
}

// ---------- Progress and question list ----------

function applyProgress(progress) {
  state.index = progress.current_index;
  state.status = progress.question_status;
  state.complete = progress.complete;
  const skipped = progress.skipped_count ? ` · ${progress.skipped_count} skipped` : "";
  $("progress-label").textContent = `${progress.answered_count} / ${progress.question_count}${skipped}`;
  $("progress-bar").style.width = `${(progress.answered_count / progress.question_count) * 100}%`;
  updateQuestionList();
}

function updateQuestionList() {
  [...$("question-list").children].forEach((item, index) => {
    const status = state.status[index];
    item.classList.toggle("answered", status === "answered");
    item.classList.toggle("skipped", status === "skipped");
    item.classList.toggle("current", !state.complete && !state.awaitingNext && index === state.index);
    item.querySelector(".question-check").textContent = status === "skipped" ? "↷" : "✓";
    item.title = status === "answered" ? "Already answered" : "Go to this question";
  });
}

function buildQuestionList() {
  const list = $("question-list");
  list.replaceChildren();
  state.questions.forEach((question, index) => {
    const item = document.createElement("li");
    item.className = "question-item";
    item.innerHTML = '<span class="question-number"></span><span class="question-preview"></span><span class="question-check">✓</span>';
    item.querySelector(".question-number").textContent = String(index + 1).padStart(2, "0");
    item.querySelector(".question-preview").textContent = question.text;
    item.addEventListener("click", () => goToQuestion(index));
    list.append(item);
  });
}

// ---------- Interview screen ----------

function renderQuestion() {
  state.awaitingNext = false;
  const question = state.questions[state.index];
  $("question-type").textContent = `Question ${String(state.index + 1).padStart(2, "0")} · ${question.kind}`;
  $("current-question").textContent = question.text;
  if (!$("answer-area").querySelector(".answer-card")) $("answer-area").innerHTML = EMPTY_STATE;
  const pendingLeft = state.status.filter((status, index) => status !== "answered" && index !== state.index).length;
  show("ask", true);
  show("skip", pendingLeft > 0);
  show("random", pendingLeft > 0);
  show("next", false);
  show("download-json", false);
  show("restart", false);
  $("interview-error").textContent = "";
  $("action-note").textContent = state.status[state.index] === "skipped"
    ? "You skipped this one earlier · ask it now or move on."
    : "Each response is saved as you go.";
  updateQuestionList();
}

function renderComplete() {
  state.awaitingNext = false;
  ["ask", "skip", "random", "next"].forEach((id) => show(id, false));
  show("download-json", true);
  show("restart", true);
  $("download-json").href = `/api/sessions/${state.sessionId}/download?format=json`;
  const skipped = state.status.filter((status) => status === "skipped").length;
  $("action-note").textContent = skipped
    ? `Interview complete · ${skipped} skipped (click one in the list to answer it) · `
    : "Interview complete · your transcript is ready · ";
  const csv = document.createElement("a");
  csv.className = "text-link";
  csv.href = `/api/sessions/${state.sessionId}/download?format=csv`;
  csv.download = "";
  csv.textContent = "CSV version";
  $("action-note").append(csv);
  updateQuestionList();
}

function meter(label, value, title) {
  const row = document.createElement("span");
  row.className = "meter";
  row.title = title;
  const name = document.createElement("span");
  name.className = "meter-label";
  name.textContent = label;
  const track = document.createElement("span");
  track.className = "meter-track";
  const fill = document.createElement("span");
  fill.className = "meter-fill";
  fill.style.width = `${Math.max(0, Math.min(1, value)) * 100}%`;
  track.append(fill);
  const number = document.createElement("span");
  number.className = "meter-value";
  number.textContent = value.toFixed(2);
  row.append(name, track, number);
  return row;
}

function renderMemory(memory, rank) {
  const item = document.createElement("li");
  item.className = rank === 0 ? "memory top" : "memory";
  const text = document.createElement("p");
  text.className = "memory-text";
  text.textContent = memory.content;
  item.append(text);
  if (rank === 0) {
    const badge = document.createElement("span");
    badge.className = "memory-badge";
    badge.textContent = "best match";
    item.prepend(badge);
  }
  if (typeof memory.score !== "number") return item;

  const total = document.createElement("span");
  total.className = "memory-score";
  total.title = "Combined score: 0.5 × recency + 3 × relevance + 0.5 × importance";
  total.textContent = `${memory.score.toFixed(2)} / ${memory.max_score}`;
  const meters = document.createElement("div");
  meters.className = "memory-meters";
  meters.append(
    meter("relevance", memory.relevance, `How close in meaning to the question (cosine similarity ${memory.similarity.toFixed(3)})`),
    meter("importance", memory.importance, `Saved importance rating: ${memory.raw_importance}`),
    meter("recency", memory.recency, "How recently this memory was used"),
  );
  item.append(total, meters);
  return item;
}

const firstName = () => state.person.name.split(" ")[0];
const seconds = (ms) => (ms >= 1000 ? `${(ms / 1000).toFixed(1)} s` : `${ms} ms`);

function resetTrace() {
  $("trace-title").textContent = `how ${firstName().toLowerCase()} answered`;
  $("trace-question").textContent = "";
  $("trace-body").innerHTML = '<p class="trace-empty"></p>';
  $("trace-body").firstChild.textContent = `Ask a question to see each step ${firstName()} took to answer it.`;
}

function traceStep(number, title, detail, extra) {
  const step = document.createElement("li");
  step.className = "trace-step";
  const marker = document.createElement("span");
  marker.className = "trace-number";
  marker.textContent = number;
  const body = document.createElement("div");
  const heading = document.createElement("h4");
  heading.textContent = title;
  const text = document.createElement("p");
  text.textContent = detail;
  body.append(heading, text);
  if (extra) body.append(extra);
  step.append(marker, body);
  return step;
}

function codeBlock(label, content) {
  const details = document.createElement("details");
  details.className = "trace-code";
  const summary = document.createElement("summary");
  summary.textContent = label;
  const pre = document.createElement("pre");
  pre.textContent = content || "(not recorded)";
  details.append(summary, pre);
  return details;
}

function renderTrace(answer) {
  const trace = answer.trace;
  $("trace-question").textContent = `question ${String(answer.question_index + 1).padStart(2, "0")}`;
  document.querySelectorAll(".answer-card").forEach((card) => {
    card.classList.toggle("traced", Number(card.dataset.index) === answer.question_index);
  });
  const body = $("trace-body");
  body.replaceChildren();
  if (!trace) {
    resetTrace();
    body.firstChild.textContent = "No step details were saved for this answer.";
    return;
  }
  const best = answer.memory_scores?.[0];
  const steps = document.createElement("ol");
  steps.className = "trace-steps";
  steps.append(
    traceStep(1, "Searched her memories",
      `Scored all ${trace.memories_searched} memories against the question in ${seconds(trace.retrieval_ms)} `
      + `(embeddings: ${trace.embedding_model}) and kept the top ${trace.memories_used}.`
      + (best ? ` Best match scored ${best.score.toFixed(2)} / ${best.max_score}.` : "")),
    traceStep(2, "Built the prompt",
      `Combined ${firstName()}'s self-description, speech pattern, those ${trace.memories_used} memories, `
      + `the question, and the answering rules (${answer.kind} question).`,
      codeBlock("show full prompt", trace.prompt)),
    traceStep(3, "Model replied",
      `${trace.model} returned a JSON reply in ${seconds(trace.generation_ms)}.`,
      codeBlock("show raw reply", trace.raw_reply)),
    traceStep(4, "Final answer",
      "The reply text was pulled out of the JSON and shown in the chat."),
  );
  const final = document.createElement("blockquote");
  final.className = "trace-final";
  final.textContent = answer.response;
  steps.lastElementChild.querySelector("div").append(final);
  body.append(steps);
}

function renderAnswer(answer, { animate = false } = {}) {
  const bubble = document.createElement("article");
  bubble.className = "answer-card";
  const question = document.createElement("p");
  question.className = "answer-question";
  question.textContent = answer.question;
  const label = document.createElement("div");
  label.className = "answer-person";
  const avatar = document.createElement("img");
  avatar.className = "answer-avatar";
  avatar.src = state.person.avatar_url;
  avatar.alt = "";
  const name = document.createElement("span");
  name.className = "answer-label";
  name.textContent = state.person.name;
  label.append(avatar, name);
  const text = document.createElement("p");
  text.className = "answer-text";
  text.textContent = answer.response;
  const details = document.createElement("details");
  details.className = "answer-memories";
  details.open = true;
  const summary = document.createElement("summary");
  summary.textContent = `Memories retrieved (${answer.supporting_memories.length}) · ranked by score`;
  const list = document.createElement("ol");
  const scored = answer.memory_scores || answer.supporting_memories.map((content) => ({ content }));
  scored.forEach((memory, rank) => list.append(renderMemory(memory, rank)));
  details.append(summary, list);
  bubble.dataset.index = answer.question_index;
  const how = document.createElement("button");
  how.type = "button";
  how.className = "trace-link";
  how.textContent = "see how this answer was made ↓";
  how.addEventListener("click", () => {
    renderTrace(answer);
    document.querySelector(".trace-window").scrollIntoView({ behavior: "smooth", block: "start" });
  });
  bubble.append(question, label, text, details, how);
  if (animate) {
    details.hidden = true;
    how.hidden = true;
    deliver(text, answer.response, () => {
      details.hidden = false;
      how.hidden = false;
    });
  }
  $("answer-area").querySelector(".empty-state")?.remove();
  $("answer-area").append(bubble);
  bubble.scrollIntoView({ behavior: "smooth", block: "start" });
  renderTrace(answer);
}

// ---------- Actions ----------

async function startInterview() {
  if (!state.person || state.busy) return;
  $("start").disabled = true;
  $("setup-error").textContent = "";
  try {
    const session = await api("/api/sessions", {
      method: "POST", body: JSON.stringify({ person_id: state.person.id }),
    });
    state.sessionId = session.session_id;
    state.questions = [...session.questions];
    state.awaitingNext = false;
    $("answer-area").replaceChildren();
    $("subject-name").textContent = session.person_name;
    await loadPortrait(state.person);
    setMood("listening");
    $("subject-intro").textContent = state.person.intro;
    buildQuestionList();
    resetTrace();
    applyProgress(session);
    show("setup", false);
    show("interview", true);
    renderQuestion();
    window.scrollTo({ top: 0, behavior: "smooth" });
  } catch (error) {
    $("setup-error").textContent = error.message;
    $("start").disabled = false;
  }
}

async function run(action) {
  if (!state.sessionId || state.busy) return;
  setBusy(true);
  $("interview-error").textContent = "";
  try {
    await action();
  } catch (error) {
    $("interview-error").textContent = error.message;
  } finally {
    setBusy(false);
  }
}

const post = (path, body = {}) => api(`/api/sessions/${state.sessionId}/${path}`, {
  method: "POST", body: JSON.stringify(body),
});

function askQuestion() {
  return run(async () => {
    stopDelivery();
    const result = await post("answer", { question_index: state.index });
    renderAnswer(result.answer, { animate: true });
    applyProgress(result);
    if (state.complete) return renderComplete();
    state.awaitingNext = true;
    updateQuestionList();
    ["ask", "skip"].forEach((id) => show(id, false));
    show("next", true);
    show("random", state.status.filter((status) => status !== "answered").length > 1);
    $("action-note").textContent = "Response saved · the green memory is the best match it used.";
  });
}

function skipQuestion() {
  stopDelivery();
  return run(async () => {
    applyProgress(await post("skip"));
    state.complete ? renderComplete() : renderQuestion();
  });
}

function goToQuestion(index) {
  if (state.status[index] === "answered" || state.busy) return;
  if (index === state.index && !state.awaitingNext && !state.complete) return;
  stopDelivery();
  return run(async () => {
    applyProgress(await post("select", { question_index: index }));
    renderQuestion();
  });
}

function randomQuestion() {
  const open = state.status
    .map((status, index) => (status !== "answered" && index !== state.index ? index : -1))
    .filter((index) => index >= 0);
  // After answering, the current question is already the next open one, so it's fair game.
  if (state.awaitingNext && state.status[state.index] !== "answered") open.push(state.index);
  if (!open.length) return;
  goToQuestion(open[Math.floor(Math.random() * open.length)]);
}

function backToPeople() {
  if (state.busy) return;
  stopDelivery();
  const started = state.status.some((status) => status !== "pending");
  if (state.sessionId && !state.complete && started
      && !window.confirm("Leave this interview? Answers so far are saved, but you can't resume it.")) return;
  state.person = null;
  state.sessionId = null;
  state.complete = false;
  state.status = [];
  const options = document.querySelectorAll(".person-option");
  options.forEach((item) => item.classList.remove("selected"));
  $("start").disabled = true;
  if (options.length === 1) options[0].click();
  show("interview", false);
  show("setup", true);
  window.scrollTo({ top: 0, behavior: "smooth" });
}

$("start").addEventListener("click", startInterview);
$("back").addEventListener("click", backToPeople);
$("restart").addEventListener("click", backToPeople);
$("ask").addEventListener("click", askQuestion);
$("skip").addEventListener("click", skipQuestion);
$("random").addEventListener("click", randomQuestion);
$("next").addEventListener("click", () => {
  if (state.busy) return;
  stopDelivery();
  renderQuestion();
  window.scrollTo({ top: 0, behavior: "smooth" });
});
api("/api/people").then(renderPeople).catch((error) => { $("setup-error").textContent = error.message; });
