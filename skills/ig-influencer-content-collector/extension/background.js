// Service Worker - handles downloads and counter management

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.action === 'saveImages') {
    saveImages(message.username, message.urls)
      .then(count => sendResponse({ count }))
      .catch(err => {
        console.error('[IG Saver BG]', err);
        sendResponse({ count: 0, error: err.message });
      });
    return true; // Keep channel open for async response
  }
});

async function saveImages(username, urls) {
  const data = await chrome.storage.local.get('ig_counters');
  const counters = data.ig_counters || {};
  const startCount = counters[username] || 0;

  for (let i = 0; i < urls.length; i++) {
    const num = startCount + i + 1;
    const filename = `${username}/${username}(${num}).jpg`;
    await downloadFile(urls[i], filename);
  }

  counters[username] = startCount + urls.length;
  await chrome.storage.local.set({ ig_counters: counters });

  return urls.length;
}

function downloadFile(url, filename) {
  return new Promise((resolve, reject) => {
    chrome.downloads.download(
      { url, filename, conflictAction: 'overwrite' },
      (downloadId) => {
        if (chrome.runtime.lastError) {
          reject(new Error(chrome.runtime.lastError.message));
        } else {
          resolve(downloadId);
        }
      }
    );
  });
}
