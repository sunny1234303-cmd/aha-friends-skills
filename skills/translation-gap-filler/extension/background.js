// 무료 비공식 Google 번역 엔드포인트 호출 + 캐싱 + 동시 요청 제한.
// service worker 재시작 시 캐시는 초기화되지만, 성능 최적화용일 뿐 정확도에는 영향 없음.
//
// content.js가 큰 페이지를 여러 개의 작은 메시지(청크)로 나눠 동시에 보내므로,
// 동시 요청 수는 메시지 단위가 아니라 전역 세마포어로 제한한다 — 그래야 청크가
// 몇 개든 실제 fetch 동시 실행 수는 항상 GLOBAL_CONCURRENCY 이하로 유지된다.

const cache = new Map();
const GLOBAL_CONCURRENCY = 10;
let inFlight = 0;
const waiters = [];

function acquireSlot() {
  if (inFlight < GLOBAL_CONCURRENCY) {
    inFlight++;
    return Promise.resolve();
  }
  return new Promise((resolve) => waiters.push(resolve));
}

function releaseSlot() {
  inFlight--;
  const next = waiters.shift();
  if (next) {
    inFlight++;
    next();
  }
}

const REQUEST_TIMEOUT_MS = 4000;

// 요청이 멈춰버리면(무료 비공식 엔드포인트라 버스트 시 응답이 느려질 수 있음)
// 전역 세마포어 슬롯을 무한정 붙잡아 뒤에 대기 중인 다른 청크들까지 줄줄이
// 밀리는 문제가 있었다. AbortController로 상한을 둬서 슬롯이 반드시 풀리게 한다.
async function fetchWithTimeout(url, timeoutMs) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, { signal: controller.signal });
  } finally {
    clearTimeout(timer);
  }
}

async function translateRequest(text) {
  const url =
    "https://translate.googleapis.com/translate_a/single" +
    "?client=gtx&sl=auto&tl=ko&dt=t&q=" +
    encodeURIComponent(text);
  const res = await fetchWithTimeout(url, REQUEST_TIMEOUT_MS);
  if (!res.ok) throw new Error("translate http " + res.status);
  const data = await res.json();
  return data[0].map((seg) => seg[0]).join("");
}

async function translateOne(text) {
  if (cache.has(text)) return cache.get(text);

  await acquireSlot();
  try {
    let translated;
    try {
      translated = await translateRequest(text);
    } catch (e) {
      translated = await translateRequest(text); // 타임아웃/일시 오류 시 한 번 재시도
    }
    if (translated && translated !== text) cache.set(text, translated);
    return translated;
  } catch (e) {
    return null;
  } finally {
    releaseSlot();
  }
}

async function translateBatch(texts) {
  const map = {};
  await Promise.all(
    texts.map(async (text) => {
      const translated = await translateOne(text);
      if (translated) map[text] = translated;
    })
  );
  return map;
}

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg?.type === "BEONYEOGI_TRANSLATE") {
    translateBatch(msg.texts || []).then((map) => sendResponse({ map }));
    return true; // async 응답을 위해 채널 유지
  }
});

chrome.commands.onCommand.addListener(async (command) => {
  if (command !== "toggle-translate") return;
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab?.id) return;
  try {
    await chrome.tabs.sendMessage(tab.id, { type: "BEONYEOGI_TOGGLE" });
  } catch (e) {
    // 번역 대상이 아닌 페이지(chrome:// 등)일 수 있음
  }
});
