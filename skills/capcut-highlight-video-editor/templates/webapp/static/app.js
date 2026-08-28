const STAGE_ORDER = [
  ["1", "영상 삽입"],
  ["2", "자막 스크립트 생성"],
  ["3", "무자막 구간 컷 편집"],
  ["4_5", "하이라이트 편집 + 키워드 등장 구간 분석"],
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

  function showFile() {
    const n = input.files.length;
    zone.classList.toggle("filled", n > 0);
    filenameEl.textContent = n > 1 ? `${n}개 파일` : (n === 1 ? input.files[0].name : "");
  }

  input.addEventListener("change", showFile);

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
      showFile();
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

// Animation dropdowns (generic names — recipe_pipeline/style_utils.py resolves
// them to CapCut enum members).
const ANIM_IN = [["none", "없음"], ["fade", "페이드"], ["pop", "팝"], ["slide-up", "위로 슬라이드"], ["typewriter", "타자기"], ["zoom", "확대"], ["karaoke", "카라오케"]];
const ANIM_OUT = [["none", "없음"], ["fade", "페이드"], ["scale-down", "축소"], ["slide-down", "아래로 슬라이드"]];
function fillAnim(selector, options) {
  document.querySelectorAll(selector).forEach((select) => {
    for (const [value, label] of options) {
      const opt = document.createElement("option");
      opt.value = value;
      opt.textContent = label;
      select.appendChild(opt);
    }
  });
}
fillAnim("select.anim-in-select", ANIM_IN);
fillAnim("select.anim-out-select", ANIM_OUT);

// Style profiles: list + prefill the advanced panel from a chosen profile's
// `applied.*` block so the user sees and can tweak the channel's look.
const profileSelect = document.getElementById("style-profile-select");
const profileFile = document.getElementById("style-profile-file");

fetch("/api/style-profiles")
  .then((r) => r.json())
  .then((profiles) => {
    for (const p of profiles) {
      const opt = document.createElement("option");
      opt.value = p.name;
      opt.textContent = p.channel_name ? `${p.name} (${p.channel_name})` : p.name;
      profileSelect.appendChild(opt);
    }
  })
  .catch(() => {});

function setField(name, value) {
  if (value === undefined || value === null) return;
  const el = form.elements[name];
  if (!el) return;
  if (el.type === "checkbox") el.checked = !!value;
  else el.value = String(value);
}

function prefillFromProfile(profile) {
  const a = (profile && profile.applied) || {};
  const cap = a.caption || {}, ov = a.overlay || {}, pac = a.pacing || {};
  const emph = a.caption_emphasis || {}, sfx = a.sfx || {};
  setField("target_duration_sec", a.target_duration_sec);
  setField("pause_gap_sec", pac.pause_gap_sec);
  setField("max_cue_sec", pac.max_cue_sec);
  setField("gap_threshold_sec", pac.gap_threshold_sec);

  setField("caption_font", cap.font);
  setField("caption_size", cap.size);
  setField("caption_color", cap.color);
  setField("caption_position", cap.position);
  setField("caption_all_caps", String(!!cap.all_caps));
  if (cap.outline && cap.outline.enabled) {
    setField("caption_outline_color", cap.outline.color || "#000000");
    setField("caption_outline_width", cap.outline.width);
  }
  setField("caption_shadow", String(!!(cap.shadow && cap.shadow.enabled)));
  setField("caption_bg", String(!!(cap.background && cap.background.enabled)));
  if (cap.background) setField("caption_bg_color", cap.background.color);
  if (cap.animation) { setField("caption_anim_in", cap.animation.in); setField("caption_anim_out", cap.animation.out); }
  setField("caption_zoom_trigger", emph.trigger);
  setField("caption_zoom_scale", emph.scale);

  setField("overlay_font", ov.font);
  setField("overlay_size", ov.size);
  setField("overlay_color", ov.color);
  setField("overlay_position", ov.position);
  setField("overlay_all_caps", String(!!ov.all_caps));
  if (ov.outline && ov.outline.enabled) {
    setField("overlay_outline_color", ov.outline.color || "#000000");
    setField("overlay_outline_width", ov.outline.width);
  }
  setField("overlay_bg", String(!!(ov.background && ov.background.enabled)));
  if (ov.animation) { setField("overlay_anim_in", ov.animation.in); setField("overlay_anim_out", ov.animation.out); }
  setField("sfx_volume", sfx.volume);
  setField("sfx_trigger", sfx.trigger);
  if (Array.isArray(sfx.map) && form.elements["sfx_map"]) {
    form.elements["sfx_map"].value = JSON.stringify(sfx.map);
  }
}

profileSelect.addEventListener("change", () => {
  if (!profileSelect.value) return;
  fetch(`/api/style-profiles/${profileSelect.value}`)
    .then((r) => r.json())
    .then(prefillFromProfile)
    .catch(() => {});
});
profileFile.addEventListener("change", () => {
  const f = profileFile.files[0];
  if (!f) return;
  const reader = new FileReader();
  reader.onload = () => {
    try { prefillFromProfile(JSON.parse(reader.result)); } catch (e) {}
  };
  reader.readAsText(f);
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
    ["감지된 키워드", summary.ingredient_keywords_found.join(", ") || "없음"],
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
