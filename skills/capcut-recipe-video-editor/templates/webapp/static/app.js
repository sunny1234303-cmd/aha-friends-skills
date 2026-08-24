const STAGE_ORDER = [
  ["1", "영상 삽입"],
  ["2", "자막 스크립트 생성"],
  ["3", "무자막 구간 컷 편집"],
  ["4_5", "총 60초 클립 편집 + 식재료 사용 구간 분석"],
  ["6", "미리 제시해준 내용(.md) 활용하여 내용 추가"],
  ["7", "자막 글꼴/크기/위치/확대"],
  ["8", "자동 효과음 추가"],
  ["9", "종료 2-3초 전 사전 캡쳐본 추가"],
  ["10", "클립 삭제 가능한 상태로 프로그램 저장"],
];

const form = document.getElementById("run-form");
const runBtn = document.getElementById("run-btn");
const progressPanel = document.getElementById("progress-panel");
const stageList = document.getElementById("stage-list");
const summaryPanel = document.getElementById("summary-panel");
const summaryList = document.getElementById("summary-list");
const errorPanel = document.getElementById("error-panel");
const errorBox = document.getElementById("error-box");

// Dropzones: click-to-browse works natively (label wraps input), this adds
// drag & drop plus the "file selected" visual state.
document.querySelectorAll(".dropzone").forEach((zone) => {
  const input = zone.querySelector("input[type='file']");
  const filenameEl = zone.querySelector(".dz-filename");

  function showFile(file) {
    zone.classList.toggle("filled", !!file);
    filenameEl.textContent = file ? file.name : "";
  }

  input.addEventListener("change", () => showFile(input.files[0]));

  zone.addEventListener("dragover", (e) => {
    e.preventDefault();
    zone.classList.add("drag-over");
  });
  zone.addEventListener("dragleave", () => zone.classList.remove("drag-over"));
  zone.addEventListener("drop", (e) => {
    e.preventDefault();
    zone.classList.remove("drag-over");
    if (e.dataTransfer.files.length) {
      input.files = e.dataTransfer.files;
      showFile(input.files[0]);
    }
  });
});

// Prevent an accidental drop outside a dropzone from navigating the page.
["dragover", "drop"].forEach((evt) =>
  document.addEventListener(evt, (e) => e.preventDefault())
);

// Populate the caption/overlay font dropdowns from the curated list the
// backend exposes (recipe_pipeline/style_utils.py CAPTION_FONTS).
fetch("/api/fonts")
  .then((r) => r.json())
  .then((fonts) => {
    document.querySelectorAll("select.font-select").forEach((select) => {
      for (const [label, value] of Object.entries(fonts)) {
        const opt = document.createElement("option");
        opt.value = value;
        opt.textContent = label;
        if (value === "Arimo_Regular") opt.selected = true;
        select.appendChild(opt);
      }
    });
  });

function renderStageList(doneKeys, messages) {
  stageList.innerHTML = "";
  for (const [key, label] of STAGE_ORDER) {
    const done = doneKeys.has(key);
    const row = document.createElement("div");
    row.className = "stage-item";
    row.innerHTML = `
      <span class="mark">${done ? "✓" : "·"}</span>
      <span class="label">${label}</span>
      <span class="msg">${done ? (messages.get(key) || "") : ""}</span>
    `;
    stageList.appendChild(row);
  }
}

function renderSummary(summary) {
  const rows = [
    ["draft 위치", summary.draft_dir],
    ["최종 길이", `${summary.final_duration_sec.toFixed(1)}초`],
    ["선택된 구간", `${summary.kept_segment_count}개`],
    ["감지된 식재료", summary.ingredient_keywords_found.join(", ") || "없음"],
    ["SRT", summary.srt_path],
    ["로그", summary.log_path],
  ];
  summaryList.innerHTML = rows
    .map(([k, v]) => `<div class="summary-row"><div class="k">${k}</div><div class="v">${v}</div></div>`)
    .join("");
  summaryList.innerHTML += `<div class="sub" style="margin-top:16px">CapCut 데스크톱 앱을 재시작한 뒤 draft 목록에서 위 이름의 draft를 열어 확인하세요.</div>`;
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  runBtn.disabled = true;
  progressPanel.classList.remove("hidden");
  summaryPanel.classList.add("hidden");
  errorPanel.classList.add("hidden");

  const doneKeys = new Set();
  const messages = new Map();
  renderStageList(doneKeys, messages);

  const formData = new FormData(form);

  const res = await fetch("/api/runs", {
    method: "POST",
    body: formData,
  });
  if (!res.ok) {
    runBtn.disabled = false;
    errorPanel.classList.remove("hidden");
    errorBox.textContent = await res.text();
    return;
  }
  const { run_id } = await res.json();

  const events = new EventSource(`/api/runs/${run_id}/events`);
  events.onmessage = (ev) => {
    const stage = JSON.parse(ev.data);
    doneKeys.add(stage.stage_key);
    messages.set(stage.stage_key, stage.message);
    renderStageList(doneKeys, messages);
  };
  events.addEventListener("done", async (ev) => {
    events.close();
    const { status } = JSON.parse(ev.data);
    runBtn.disabled = false;
    if (status === "done") {
      const summaryRes = await fetch(`/api/runs/${run_id}/summary`);
      const summary = await summaryRes.json();
      summaryPanel.classList.remove("hidden");
      renderSummary(summary);
    } else {
      const statusRes = await fetch(`/api/runs/${run_id}/status`);
      const state = await statusRes.json();
      errorPanel.classList.remove("hidden");
      errorBox.textContent = state.error || "알 수 없는 오류";
    }
  });
});
