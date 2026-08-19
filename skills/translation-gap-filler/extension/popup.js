const toggleBtn = document.getElementById("toggleBtn");
const statusText = document.getElementById("statusText");
const shortcutHint = document.getElementById("shortcutHint");

shortcutHint.textContent = navigator.platform.toUpperCase().includes("MAC")
  ? "⌘⇧Y"
  : "Ctrl+Shift+Y";

async function getActiveTab() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  return tab;
}

function render(active) {
  toggleBtn.textContent = active ? "번역 중지" : "이 페이지 번역하기";
  toggleBtn.classList.toggle("is-active", active);
  statusText.textContent = active
    ? "번역 중 · 새로 로드되는 콘텐츠도 자동 반영"
    : "대기 중";
  statusText.classList.toggle("is-active", active);
}

async function refreshStatus() {
  const tab = await getActiveTab();
  if (!tab?.id) return;
  try {
    const res = await chrome.tabs.sendMessage(tab.id, {
      type: "BEONYEOGI_STATUS",
    });
    render(!!res?.active);
  } catch (e) {
    statusText.textContent = "페이지를 새로고침한 후 다시 열어주세요";
  }
}

toggleBtn.addEventListener("click", async () => {
  const tab = await getActiveTab();
  if (!tab?.id) return;
  try {
    const res = await chrome.tabs.sendMessage(tab.id, {
      type: "BEONYEOGI_TOGGLE",
    });
    render(!!res?.active);
  } catch (e) {
    statusText.textContent = "페이지를 새로고침한 후 다시 시도해주세요";
  }
});

refreshStatus();
