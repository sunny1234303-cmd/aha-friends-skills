// 모든 프레임(iframe 포함)에 주입됨. 프레임별로 독립 실행.
(() => {
  if (window.__beonyeogiInjected) return;
  window.__beonyeogiInjected = true;

  const HANGUL_RE = /[가-힣]/;
  const LATIN_RE = /[a-zA-Z]/;
  const SKIP_TAGS = new Set([
    "SCRIPT",
    "STYLE",
    "NOSCRIPT",
    "TEXTAREA",
    "INPUT",
    "CODE",
    "PRE",
  ]);

  const processed = new WeakSet();
  let active = false;
  let observer = null;
  let toastTimer = null;

  function ensureToast() {
    if (window.top !== window) return null; // 최상위 프레임에서만 토스트 표시
    let toast = document.getElementById("beonyeogi-toast");
    if (toast) return toast;

    const style = document.createElement("style");
    style.textContent = `
      @font-face {
        font-family: 'Beonyeogi-Toast';
        src: url('${chrome.runtime.getURL("fonts/Pretendard-Medium.woff2")}') format('woff2');
        font-weight: 500;
      }
      #beonyeogi-toast {
        all: initial;
        position: fixed;
        right: 20px;
        top: 20px;
        z-index: 2147483647;
        background: #1A1A1A;
        color: #FAF9F6;
        border: 2.25px solid #222222;
        padding: 10px 16px;
        font-family: 'Beonyeogi-Toast', -apple-system, sans-serif;
        font-size: 13px;
        font-weight: 500;
        letter-spacing: -0.02em;
        line-height: 1.6;
        opacity: 0;
        transform: translateY(-8px);
        transition: opacity 0.25s ease, transform 0.25s ease;
        pointer-events: none;
      }
      #beonyeogi-toast.show {
        opacity: 1;
        transform: translateY(0);
      }
    `;
    document.documentElement.appendChild(style);

    toast = document.createElement("div");
    toast.id = "beonyeogi-toast";
    document.documentElement.appendChild(toast);
    return toast;
  }

  function showToast(text, holdMs = 2200) {
    const toast = ensureToast();
    if (!toast) return;
    toast.textContent = text;
    toast.classList.add("show");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toast.classList.remove("show"), holdMs);
  }

  function isTranslatable(node) {
    const text = node.nodeValue;
    if (!text || !text.trim()) return false;
    if (HANGUL_RE.test(text)) return false; // 이미 한국어 포함 → 건너뜀
    if (!LATIN_RE.test(text)) return false; // 영문자 없는 텍스트(숫자·기호만)는 스킵

    const parent = node.parentElement;
    if (!parent) return false;
    if (SKIP_TAGS.has(parent.tagName)) return false;
    if (parent.isContentEditable) return false;
    if (parent.closest('[contenteditable="true"]')) return false;

    return true;
  }

  function collectTextNodes(root) {
    if (root.nodeType === Node.TEXT_NODE) {
      return !processed.has(root) && isTranslatable(root) ? [root] : [];
    }
    if (root.nodeType !== Node.ELEMENT_NODE) return [];

    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, null);
    const nodes = [];
    let n;
    while ((n = walker.nextNode())) {
      if (!processed.has(n) && isTranslatable(n)) nodes.push(n);
    }
    return nodes;
  }

  const CHUNK_SIZE = 12; // 청크 단위로 나눠 동시에 보내면 화면에 결과가 순차적으로 빨리 채워짐

  function chunkArray(arr, size) {
    const chunks = [];
    for (let i = 0; i < arr.length; i += size) chunks.push(arr.slice(i, i + size));
    return chunks;
  }

  async function translateChunk(nodes) {
    const texts = [...new Set(nodes.map((n) => n.nodeValue))];
    let result;
    try {
      result = await chrome.runtime.sendMessage({
        type: "BEONYEOGI_TRANSLATE",
        texts,
      });
    } catch (e) {
      return; // 확장 컨텍스트 무효화 등
    }
    if (!result?.map) return;

    nodes.forEach((n) => {
      const translated = result.map[n.nodeValue];
      if (translated) n.nodeValue = translated;
    });
  }

  function translateNodes(nodes) {
    if (!nodes.length) return;
    nodes.forEach((n) => processed.add(n));
    // 청크마다 별도 메시지로 동시 발송 → 실제 동시 요청 수 제한은 background.js의 전역 세마포어가 담당
    chunkArray(nodes, CHUNK_SIZE).forEach((group) => translateChunk(group));
  }

  function translatePage() {
    translateNodes(collectTextNodes(document.body));
  }

  function startObserving() {
    if (observer) return;
    observer = new MutationObserver((mutations) => {
      const newNodes = [];
      for (const m of mutations) {
        m.addedNodes.forEach((added) => {
          newNodes.push(...collectTextNodes(added));
        });
      }
      if (newNodes.length) translateNodes(newNodes);
    });
    observer.observe(document.body, { childList: true, subtree: true });
  }

  function stopObserving() {
    if (observer) {
      observer.disconnect();
      observer = null;
    }
  }

  // YouTube 자막(캡션) 자동 켜기 — 자막 텍스트도 일반 DOM 텍스트라
  // 위 translateNodes/observer 로직이 그대로 번역해준다. 여기선 "꺼져있는
  // 자막을 켜는 것"만 담당한다 (라이브 스트리밍 중 실시간 갱신되는 자막은
  // 범위 밖 — MutationObserver는 새로 추가되는 자막 노드만 감지한다).
  function isYouTubePlayerPage() {
    if (!/(^|\.)youtube\.com$/.test(location.hostname)) return false;
    return location.pathname === "/watch" || location.pathname.startsWith("/embed/");
  }

  let ccAttempted = false;
  let ytNavListenerAdded = false;

  function tryEnableYouTubeCaptions() {
    const btn = document.querySelector(".ytp-subtitles-button");
    if (!btn) return false;
    if (btn.getAttribute("aria-pressed") !== "true") btn.click();
    return true;
  }

  function watchYouTubeCaptions() {
    if (!isYouTubePlayerPage()) return;

    const attempt = () => {
      if (ccAttempted) return;
      if (tryEnableYouTubeCaptions()) ccAttempted = true;
    };

    attempt();
    const poll = setInterval(() => {
      attempt();
      if (ccAttempted) clearInterval(poll);
    }, 500);
    setTimeout(() => clearInterval(poll), 15000); // 플레이어가 안 뜨면 포기

    if (!ytNavListenerAdded) {
      ytNavListenerAdded = true;
      // 유튜브는 SPA라 다른 영상으로 넘어가도 페이지가 새로 로드되지 않음
      document.addEventListener("yt-navigate-finish", () => {
        ccAttempted = false;
        setTimeout(attempt, 800);
      });
    }
  }

  function start() {
    active = true;
    showToast("번역이가 번역 중...");
    translatePage();
    startObserving();
    watchYouTubeCaptions();
  }

  function stop() {
    active = false;
    showToast("번역이 중지됨", 1400);
    stopObserving();
  }

  chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
    if (msg?.type === "BEONYEOGI_TOGGLE") {
      if (active) stop();
      else start();
      sendResponse({ active });
    } else if (msg?.type === "BEONYEOGI_STATUS") {
      sendResponse({ active });
    }
  });

  start(); // 페이지 열리면 자동 시작 (필요하면 팝업/단축키로 끌 수 있음)
})();
