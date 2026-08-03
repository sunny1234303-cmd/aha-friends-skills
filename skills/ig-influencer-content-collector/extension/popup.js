async function loadCounters() {
  const data = await chrome.storage.local.get('ig_counters');
  const counters = data.ig_counters || {};
  const list = document.getElementById('counter-list');

  if (Object.keys(counters).length === 0) {
    list.innerHTML = '<p class="empty-msg">아직 저장한 이미지가 없습니다.<br>피드 게시물의 💾 버튼을 눌러 저장하세요.</p>';
    return;
  }

  list.innerHTML = '';

  const entries = Object.entries(counters).sort((a, b) => b[1] - a[1]);

  entries.forEach(([username, count]) => {
    const row = document.createElement('div');
    row.className = 'counter-row';

    const nameEl = document.createElement('span');
    nameEl.className = 'username';
    nameEl.textContent = `@${username}`;

    const countEl = document.createElement('span');
    countEl.className = 'count';
    countEl.textContent = `${count}장`;

    const resetBtn = document.createElement('button');
    resetBtn.className = 'btn-reset-one';
    resetBtn.textContent = '초기화';
    resetBtn.dataset.username = username;
    resetBtn.addEventListener('click', () => resetOne(username));

    row.appendChild(nameEl);
    row.appendChild(countEl);
    row.appendChild(resetBtn);
    list.appendChild(row);
  });
}

async function resetOne(username) {
  const data = await chrome.storage.local.get('ig_counters');
  const counters = data.ig_counters || {};
  delete counters[username];
  await chrome.storage.local.set({ ig_counters: counters });
  loadCounters();
}

document.getElementById('reset-all-btn').addEventListener('click', async () => {
  const data = await chrome.storage.local.get('ig_counters');
  const counters = data.ig_counters || {};
  if (Object.keys(counters).length === 0) return;

  if (confirm('모든 채널의 저장 카운터를 초기화하시겠습니까?\n이 작업은 되돌릴 수 없습니다.')) {
    await chrome.storage.local.set({ ig_counters: {} });
    loadCounters();
  }
});

loadCounters();
