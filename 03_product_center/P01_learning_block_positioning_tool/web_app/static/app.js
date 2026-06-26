const chatLog = document.querySelector("#chatLog");
const quickPanel = document.querySelector("#quickPanel");
const composer = document.querySelector("#composer");
const messageInput = document.querySelector("#messageInput");
const sendButton = document.querySelector("#sendButton");
const restartButton = document.querySelector("#restartButton");

let sessionId = null;
let currentBlock = null;
let selectedSet = new Set();
let isSending = false;

const factorLabels = {
  F01_prior_knowledge_gap: "前置知识没接上",
  F02_concept_understanding_unstable: "概念没稳住",
  F03_subject_language_symbol_difficulty: "题干和符号读不顺",
  F04_representation_conversion_difficulty: "文字、图、式子转不过来",
  F05_modeling_transfer_difficulty: "新题不知道怎么启动",
  F06_execution_instability: "步骤和计算不稳定",
  F07_metacognition_review_weak: "说不清从哪一步断掉",
  F08_learning_strategy_inefficient: "错题复盘方式低效",
  F09_emotion_motivation_self_efficacy: "一遇到难题先紧张",
  F10_family_support_ai_misaligned: "帮助给得太快",
};

const resultPlainText = {
  F01_prior_knowledge_gap: "先别急着追新题，孩子可能有一块旧知识没接上。",
  F02_concept_understanding_unstable: "孩子不是完全不会，更像是概念会背，但没真正能用。",
  F03_subject_language_symbol_difficulty: "孩子可能先卡在读题和符号上，后面的解法自然启动不了。",
  F04_representation_conversion_difficulty: "孩子更像卡在把文字、图、式子互相转换。",
  F05_modeling_transfer_difficulty: "孩子更像卡在把题目变成解题路径：听懂了，但新题不知道先做哪一步。",
  F06_execution_instability: "孩子大方向可能知道，但步骤、代入、单位或检查不够稳。",
  F07_metacognition_review_weak: "孩子可能不是缺答案，而是说不清自己第一处卡在哪里。",
  F08_learning_strategy_inefficient: "孩子可能看懂了答案，但没有把错题变成下一次能独立做的能力。",
  F09_emotion_motivation_self_efficacy: "孩子遇到难题时，情绪先把启动挡住了。",
  F10_family_support_ai_misaligned: "现在最该先调的，可能不是孩子，而是帮助方式：答案来得太快，思考被接走了。",
};

const pathLabels = {
  P02_parent_ai_workshop: "先学会把 AI 用成追问工具",
  P03_one_family_one_plan: "适合继续做一次更细的家庭方案",
  human_review: "建议先人工看一眼",
  not_fit: "暂时不适合继续自动判断",
};

const optionKeywords = {
  subject_math: ["数学", "代数", "几何", "函数"],
  subject_physics: ["物理", "力学", "电路", "受力", "电学"],
  subject_chemistry: ["化学", "方程式", "实验", "物质", "反应"],
  stuck_read_problem: ["读不懂", "题意", "关键词", "不知道问什么"],
  stuck_concept_formula: ["概念", "公式会背", "说不清", "定义"],
  stuck_transform: ["画图", "列式", "转化", "关系式"],
  stuck_select_method: ["选哪个", "方法", "公式", "不知道用"],
  stuck_execution: ["计算", "步骤", "单位", "检查", "粗心"],
  stuck_repeat_after_answer: ["看答案", "下次", "过两天", "又不会"],
  stuck_emotional_avoidance: ["烦", "急", "逃", "崩", "哭", "不想"],
  physics_no_diagram: ["不画图", "受力图", "电路图", "直接套"],
  physics_formula_without_quantity_meaning: ["每个量", "量代表", "公式会背"],
  math_same_template_ok_variant_fail: ["变式", "换个说法", "同款"],
  math_symbol_condition_missed: ["条件", "符号", "图形关系", "漏"],
  chem_symbol_equation_mismatch: ["现象", "粒子", "方程式"],
  chem_rule_cannot_transfer: ["规律", "新物质", "迁移"],
  parent_explain_full_solution: ["完整解法", "直接讲", "我讲", "讲答案"],
  parent_add_more_exercises: ["刷题", "加题", "多做"],
  parent_ask_breakpoint: ["哪一步", "从哪不会", "断点"],
  parent_ai_gives_answer: ["ai", "AI", "答案", "直接给"],
  parent_review_then_retest: ["复盘", "隔天", "重做", "复测"],
  child_does_not_understand_question: ["读完", "不知道问什么"],
  child_cannot_draw_or_formulate: ["画图", "列式"],
  child_cannot_choose_formula: ["选公式", "选哪个", "不知道用哪个"],
  child_calculation_or_units_messy: ["代入", "单位", "计算乱"],
  child_understands_answer_then_forgets: ["答案看懂", "下次还是不会"],
  probe_ai_answer_first: ["ai", "AI", "答案"],
  probe_parent_takes_over: ["接管", "主要听", "我讲"],
  probe_cannot_name_breakpoint: ["说不清", "哪里不会", "断点"],
  probe_only_reads_answer: ["看懂答案", "缺少复测", "没重做"],
  probe_text_to_diagram_hard: ["文字", "图", "式子", "关系"],
  probe_diagram_to_formula_hard: ["图有了", "公式", "方法"],
  probe_template_ok_variant_fail: ["变式", "换情境", "同款"],
  probe_knows_relation_not_formula: ["大概有关", "连起来", "量之间"],
  probe_emotion_blocks_start: ["烦躁", "紧张", "逃开"],
};

async function start() {
  sessionId = null;
  currentBlock = null;
  selectedSet = new Set();
  isSending = false;
  chatLog.innerHTML = "";
  quickPanel.innerHTML = "";
  enableComposer("比如：孩子物理听懂了，但综合题不知道从哪开始，我一急就讲完整解法...");

  const block = await createSession();
  renderBlock(block);
}

async function createSession() {
  const response = await fetch("/api/start");
  const data = await response.json();
  sessionId = data.session_id;
  currentBlock = data.block;
  return data.block;
}

function renderBlock(block) {
  currentBlock = block;
  selectedSet = new Set();
  quickPanel.innerHTML = "";
  addAssistantMessage(block.title, block.body);

  if (block.type === "short_text") {
    enableComposer("把这件事直接发给我。");
    return;
  }

  enableComposer("也可以直接打字回答。");
  if (block.type === "multi_choice") {
    renderMultiChoice(block);
    return;
  }
  renderSingleChoice(block);
}

function renderSingleChoice(block) {
  const wrap = document.createElement("div");
  wrap.className = "quick-replies";
  block.options.forEach((option) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "quick-reply";
    button.textContent = option.label;
    button.addEventListener("click", () => {
      addUserMessage(option.label);
      submitAnswer({
        selected_option_ids: [option.id],
        actor: block.type === "child_checkpoint" ? "child" : "parent",
      });
    });
    wrap.appendChild(button);
  });

  if (block.allow_skip) {
    const skip = document.createElement("button");
    skip.type = "button";
    skip.className = "quick-reply muted";
    skip.textContent = "先跳过";
    skip.addEventListener("click", () => {
      addUserMessage("先跳过");
      submitAnswer({ selected_option_ids: [] });
    });
    wrap.appendChild(skip);
  }

  quickPanel.appendChild(wrap);
}

function renderMultiChoice(block) {
  const wrap = document.createElement("div");
  wrap.className = "quick-replies";

  block.options.forEach((option) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "quick-reply selectable";
    button.textContent = option.label;
    button.addEventListener("click", () => {
      if (selectedSet.has(option.id)) {
        selectedSet.delete(option.id);
        button.classList.remove("selected");
      } else {
        selectedSet.add(option.id);
        button.classList.add("selected");
      }
      updateMultiSubmitText();
    });
    wrap.appendChild(button);
  });

  const send = document.createElement("button");
  send.type = "button";
  send.id = "multiSubmit";
  send.className = "quick-reply send-choice";
  send.textContent = "就这些";
  send.addEventListener("click", () => {
    const labels = block.options.filter((option) => selectedSet.has(option.id)).map((option) => option.label);
    addUserMessage(labels.length ? labels.join("、") : "先跳过");
    submitAnswer({ selected_option_ids: Array.from(selectedSet) });
  });
  wrap.appendChild(send);
  quickPanel.appendChild(wrap);
}

function updateMultiSubmitText() {
  const button = document.querySelector("#multiSubmit");
  if (!button) return;
  button.textContent = selectedSet.size ? `就这些（${selectedSet.size}）` : "就这些";
}

async function handleComposerSubmit(event) {
  event.preventDefault();
  const text = messageInput.value.trim();
  if (!text || isSending) return;
  messageInput.value = "";
  resizeComposer();
  addUserMessage(text);

  if (!currentBlock) {
    await createSession();
    submitAnswer({ free_text: text });
    return;
  }

  if (currentBlock.type === "short_text") {
    submitAnswer({ free_text: text });
    return;
  }

  const matchedIds = matchOptionIds(currentBlock, text);
  const selected_option_ids = currentBlock.type === "multi_choice" ? matchedIds : matchedIds.slice(0, 1);
  submitAnswer({ selected_option_ids, free_text: text });
}

async function submitAnswer({ selected_option_ids = [], free_text = "", actor = "parent" }) {
  setSending(true);
  quickPanel.innerHTML = "";
  const typing = addTyping();
  const response = await fetch("/api/answer", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      session_id: sessionId,
      question_id: currentBlock.id,
      actor,
      selected_option_ids,
      free_text,
    }),
  });
  typing.remove();
  const data = await response.json();
  setSending(false);

  if (data.error) {
    addAssistantMessage("这里卡了一下", data.error);
    return;
  }

  if (data.result) {
    renderResult(data.result);
    return;
  }

  renderBlock(data.block);
}

function renderResult(result) {
  currentBlock = null;
  quickPanel.innerHTML = "";
  const summary = resultPlainText[result.primary_factor] || result.public_summary;
  const secondary = result.secondary_factors
    .map((factor) => `<span>${escapeHtml(factorLabels[factor] || factor)}</span>`)
    .join("");
  const evidence = result.evidence.map((item) => `<li>${escapeHtml(item)}</li>`).join("");
  const html = `
    <p>${escapeHtml(summary)}</p>
    <div class="result-actions">
      <article>
        <strong>今晚先别</strong>
        <span>${escapeHtml(result.next_7_days_stop)}</span>
      </article>
      <article>
        <strong>今晚先做</strong>
        <span>${escapeHtml(result.next_7_days_start)}</span>
      </article>
    </div>
    <p class="soft-note">最容易踩的坑：${escapeHtml(result.parent_common_mistake)}</p>
    <p class="soft-note">下一步：${escapeHtml(pathLabels[result.recommended_path] || result.recommended_path)}</p>
    <details class="evidence-box">
      <summary>查看判断依据</summary>
      <div class="factor-tags">
        <span>主线：${escapeHtml(factorLabels[result.primary_factor] || result.primary_factor)}</span>
        ${secondary}
      </div>
      <ul>${evidence}</ul>
    </details>
  `;
  addAssistantHtml("我先给你一个可执行的判断", html);
  currentBlock = null;
  enableComposer("还想看另一件事，直接发给我。");
}

function matchOptionIds(block, text) {
  const normalizedText = normalize(text);
  return block.options
    .filter((option) => {
      const label = normalize(option.label);
      if (normalizedText.includes(label) || label.includes(normalizedText)) return true;
      const keywords = optionKeywords[option.id] || [];
      return keywords.some((keyword) => normalizedText.includes(normalize(keyword)));
    })
    .map((option) => option.id);
}

function addAssistantMessage(title, body = "") {
  const html = `
    <strong>${escapeHtml(title)}</strong>
    ${body ? `<p>${escapeHtml(body)}</p>` : ""}
  `;
  addAssistantHtml("", html);
}

function addAssistantHtml(label, html) {
  const row = document.createElement("div");
  row.className = "message-row assistant";
  row.innerHTML = `
    <div class="bubble">
      ${label ? `<span class="bubble-label">${escapeHtml(label)}</span>` : ""}
      ${html}
    </div>
  `;
  chatLog.appendChild(row);
  scrollToBottom();
}

function addUserMessage(text) {
  const row = document.createElement("div");
  row.className = "message-row user";
  row.innerHTML = `<div class="bubble">${escapeHtml(text)}</div>`;
  chatLog.appendChild(row);
  scrollToBottom();
}

function addTyping() {
  const row = document.createElement("div");
  row.className = "message-row assistant typing-row";
  row.innerHTML = `<div class="bubble typing"><span></span><span></span><span></span></div>`;
  chatLog.appendChild(row);
  scrollToBottom();
  return row;
}

function setSending(value) {
  isSending = value;
  sendButton.disabled = value;
  messageInput.disabled = value;
}

function enableComposer(placeholder) {
  messageInput.disabled = false;
  sendButton.disabled = false;
  messageInput.placeholder = placeholder;
  messageInput.focus();
}

function resizeComposer() {
  messageInput.style.height = "auto";
  messageInput.style.height = `${Math.min(messageInput.scrollHeight, 132)}px`;
}

function scrollToBottom() {
  chatLog.scrollTop = chatLog.scrollHeight;
}

function normalize(value) {
  return String(value || "")
    .toLowerCase()
    .replace(/[，。！？、；：,.!?;:\s/（）()「」"']/g, "");
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

composer.addEventListener("submit", handleComposerSubmit);
messageInput.addEventListener("input", resizeComposer);
messageInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    composer.requestSubmit();
  }
});
restartButton.addEventListener("click", start);

start();
