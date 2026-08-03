(() => {
  'use strict';

  const SAVER_CLASS = 'ig-saver-btn-container';
  const CDN_PATTERN = /scontent[^"'\s]*/;
  const MIN_RES = 1000;

  const processedArticles = new WeakSet();

  function init() {
    document.querySelectorAll('article').forEach(tryInject);

    let debounceTimer = null;
    const observer = new MutationObserver(() => {
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(() => {
        document.querySelectorAll('article').forEach(tryInject);
      }, 200);
    });

    // childList: new articles (feed scroll, modal open)
    // attributes src/srcset: lazy-loaded images getting real URLs after DOM insertion
    observer.observe(document.body, {
      childList: true,
      subtree: true,
      attributes: true,
      attributeFilter: ['src', 'srcset']
    });
  }

  function tryInject(article) {
    if (processedArticles.has(article)) return;

    const mediaArea = findMediaArea(article);
    if (!mediaArea) return; // images not loaded yet — observer will retry

    processedArticles.add(article);
    article._igSaverMediaArea = mediaArea; // scope for image collection

    const existingPosition = getComputedStyle(mediaArea).position;
    if (existingPosition === 'static') {
      mediaArea.style.position = 'relative';
    }

    const btnContainer = document.createElement('div');
    btnContainer.className = SAVER_CLASS;

    const btn = document.createElement('button');
    btn.className = 'ig-saver-btn';
    btn.title = '이미지 저장 (Instagram Image Saver)';
    btn.innerHTML = '<span class="ig-saver-icon">&#8659;</span>';

    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      e.preventDefault();
      handleSave(article, btn);
    });

    btnContainer.appendChild(btn);
    mediaArea.appendChild(btnContainer);
  }

  function findMediaArea(article) {
    // Find the first post image (scontent CDN = actual post content)
    const postImg = [...article.querySelectorAll('img')].find(img =>
      img.src.includes('scontent') || (img.srcset && img.srcset.includes('scontent'))
    );
    if (!postImg) return null;

    // Walk up from the image, expanding the candidate as long as the container
    // does NOT yet contain a comment form or timestamp — those live exclusively
    // in the info/sidebar panel, never in the pure media panel.
    // This correctly handles user-tag overlays (they have profile links but no form/time)
    // and works for both feed view and modal/lightbox view.
    let el = postImg.parentElement;
    let best = el;

    while (el && el !== article) {
      const hasInfoPanel = el.querySelector(
        'form, textarea, [role="textbox"], time'
      ) !== null;

      if (hasInfoPanel) break;

      best = el;
      el = el.parentElement;
    }

    return best;
  }

  async function handleSave(article, btn) {
    if (btn.dataset.loading === 'true') return;
    btn.dataset.loading = 'true';

    const originalHTML = btn.innerHTML;
    setButtonState(btn, 'loading', '⏳');

    try {
      const username = getUsername(article);
      if (!username) {
        showToast('계정 이름을 찾을 수 없습니다.');
        return;
      }

      const images = await collectAllImages(article, btn);

      if (images.length === 0) {
        showToast('저장할 이미지를 찾을 수 없습니다.');
        return;
      }

      const highRes = images.filter(img => img.width >= MIN_RES);
      const lowRes = images.filter(img => img.width < MIN_RES);

      let urlsToSave;

      if (lowRes.length > 0) {
        const choice = await showLowResModal(lowRes, highRes.length);
        if (choice === null) {
          // User dismissed without choosing
          return;
        }
        urlsToSave = choice === 'all'
          ? [...highRes, ...lowRes].map(i => i.url)
          : highRes.map(i => i.url);
      } else {
        urlsToSave = highRes.map(i => i.url);
      }

      if (urlsToSave.length === 0) {
        showToast('저장할 이미지가 없습니다.');
        return;
      }

      setButtonState(btn, 'loading', '💾');

      chrome.runtime.sendMessage(
        { action: 'saveImages', username, urls: urlsToSave },
        (response) => {
          if (chrome.runtime.lastError) {
            showToast('저장 중 오류가 발생했습니다.');
            return;
          }
          showToast(`${response.count}장 저장 완료! (@${username})`);
          setButtonState(btn, 'done', '✓');
          setTimeout(() => {
            btn.innerHTML = originalHTML;
            btn.dataset.loading = 'false';
          }, 2000);
        }
      );
      return; // Avoid finally reset below (handled in callback)

    } catch (err) {
      console.error('[IG Saver]', err);
      showToast('오류가 발생했습니다.');
    }

    btn.innerHTML = originalHTML;
    btn.dataset.loading = 'false';
  }

  function setButtonState(btn, state, icon) {
    btn.innerHTML = `<span class="ig-saver-icon">${icon}</span>`;
    btn.dataset.state = state;
  }

  function getUsername(article) {
    // Instagram often uses <div> not <header>, so search the entire article.
    // querySelectorAll returns nodes in DOM order — author link is always first.
    const RESERVED = new Set([
      'p', 'reel', 'reels', 'stories', 'explore', 'accounts',
      'about', 'login', 'direct', 'tags', 'locations', 'tv',
      'legal', 'privacy', 'safety', 'support', 'help', 'press',
      'checkout', 'graphql', 'api', 'static'
    ]);

    // Exclude links inside the media area — user-tag overlays on images
    // (/own_account/ links) appear in DOM order BEFORE the author link in the
    // info panel, causing tagged posts to be filed under the wrong account.
    const mediaArea = article._igSaverMediaArea;

    const links = article.querySelectorAll('a[href]');
    for (const link of links) {
      if (mediaArea && mediaArea.contains(link)) continue; // skip user-tag links
      try {
        const url = new URL(link.href);
        if (url.hostname !== location.hostname) continue;
        const parts = url.pathname.split('/').filter(Boolean);
        if (
          parts.length === 1 &&
          !RESERVED.has(parts[0].toLowerCase()) &&
          /^[\w.]+$/.test(parts[0]) &&
          parts[0].length <= 30
        ) {
          return parts[0];
        }
      } catch (_) {}
    }

    return null;
  }

  async function collectAllImages(article, btn) {
    const collected = new Map();

    function collectCurrent() {
      // Scope to mediaArea only — excludes profile pics, comment avatars, etc.
      const scope = article._igSaverMediaArea;
      if (!scope) return;

      const allImgs = [...scope.querySelectorAll('img')];
      const postImgs = allImgs.filter(img =>
        img.src.includes('scontent') || (img.srcset && img.srcset.includes('scontent'))
      );

      postImgs.forEach(img => {
        const result = getBestUrl(img);
        if (result && result.url && !collected.has(result.url)) {
          collected.set(result.url, result);
        }
      });
    }

    collectCurrent();

    // Auto-traverse carousel slides
    let slideIndex = 1;
    while (true) {
      const nextBtn = findNextButton(article);
      if (!nextBtn) break;

      nextBtn.click();
      await sleep(500);
      slideIndex++;

      // Update button to show progress
      setButtonState(btn, 'loading', slideIndex.toString());

      collectCurrent();

      // Safety limit
      if (slideIndex > 30) break;
    }

    return [...collected.values()];
  }

  function findNextButton(article) {
    // Search within mediaArea — carousel controls live inside the media section
    const scope = article._igSaverMediaArea || article;

    const ariaPatterns = [
      'Next', '다음', 'Suivant', 'Siguiente', 'Nächste',
      'Avançar', '次へ', '下一个', '다음 콘텐츠'
    ];

    for (const label of ariaPatterns) {
      const btn = scope.querySelector(`button[aria-label*="${label}"]`);
      if (btn && !btn.disabled && btn.offsetParent !== null) return btn;
    }

    // Fallback: any visible button whose aria-label contains next/다음
    for (const btn of scope.querySelectorAll('button')) {
      if (!btn.disabled && btn.offsetParent !== null) {
        const label = (btn.getAttribute('aria-label') || '').toLowerCase();
        if (label.includes('next') || label.includes('다음')) return btn;
      }
    }

    return null;
  }

  function getBestUrl(img) {
    if (img.srcset) {
      const entries = img.srcset.split(',')
        .map(s => {
          const parts = s.trim().split(/\s+/);
          return { url: parts[0], width: parseInt(parts[1]) || 0 };
        })
        .filter(e => e.url && e.url.startsWith('http'))
        .sort((a, b) => b.width - a.width);

      if (entries.length > 0) return entries[0];
    }

    if (img.src && img.src.startsWith('http')) {
      const match = img.src.match(/_s(\d+)x\d+/);
      return { url: img.src, width: match ? parseInt(match[1]) : 0 };
    }

    return null;
  }

  function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  function showToast(message) {
    const existing = document.querySelector('.ig-saver-toast');
    if (existing) existing.remove();

    const toast = document.createElement('div');
    toast.className = 'ig-saver-toast';
    toast.textContent = message;
    document.body.appendChild(toast);

    // Force reflow before adding visible class for transition
    toast.getBoundingClientRect();
    toast.classList.add('ig-saver-toast-visible');

    setTimeout(() => {
      toast.classList.remove('ig-saver-toast-visible');
      setTimeout(() => toast.remove(), 300);
    }, 2500);
  }

  function showLowResModal(lowResImages, highResCount) {
    return new Promise(resolve => {
      const overlay = document.createElement('div');
      overlay.className = 'ig-saver-overlay';

      const modal = document.createElement('div');
      modal.className = 'ig-saver-modal';

      const title = document.createElement('p');
      title.className = 'ig-saver-modal-title';
      title.textContent = `⚠️  저해상도 이미지 ${lowResImages.length}장 포함`;

      const desc = document.createElement('p');
      desc.className = 'ig-saver-modal-desc';
      desc.textContent = `1000px 미만의 이미지가 감지되었습니다. 아래 이미지를 확인 후 저장 여부를 선택해 주세요.`;

      const grid = document.createElement('div');
      grid.className = 'ig-saver-thumb-grid';

      lowResImages.forEach(imgData => {
        const wrapper = document.createElement('div');
        wrapper.className = 'ig-saver-thumb-wrapper';

        const thumb = document.createElement('img');
        thumb.src = imgData.url;
        thumb.className = 'ig-saver-thumb';
        thumb.alt = `저해상도 이미지 (${imgData.width || '?'}px)`;

        const label = document.createElement('span');
        label.className = 'ig-saver-thumb-label';
        label.textContent = imgData.width ? `${imgData.width}px` : '크기 미상';

        wrapper.appendChild(thumb);
        wrapper.appendChild(label);
        grid.appendChild(wrapper);
      });

      const btnRow = document.createElement('div');
      btnRow.className = 'ig-saver-modal-btns';

      const btnAll = document.createElement('button');
      btnAll.className = 'ig-saver-btn-primary';
      btnAll.textContent = '예, 모두 저장';
      btnAll.onclick = () => { overlay.remove(); resolve('all'); };

      const btnHighOnly = document.createElement('button');
      btnHighOnly.className = 'ig-saver-btn-secondary';
      btnHighOnly.textContent = highResCount > 0
        ? `고해상도만 저장 (${highResCount}장)`
        : '고해상도 이미지 없음';
      btnHighOnly.disabled = highResCount === 0;
      btnHighOnly.onclick = () => { overlay.remove(); resolve('high-only'); };

      const btnCancel = document.createElement('button');
      btnCancel.className = 'ig-saver-btn-cancel';
      btnCancel.textContent = '취소';
      btnCancel.onclick = () => { overlay.remove(); resolve(null); };

      btnRow.appendChild(btnAll);
      btnRow.appendChild(btnHighOnly);
      btnRow.appendChild(btnCancel);

      modal.appendChild(title);
      modal.appendChild(desc);
      modal.appendChild(grid);
      modal.appendChild(btnRow);
      overlay.appendChild(modal);
      document.body.appendChild(overlay);

      // Close on overlay click
      overlay.addEventListener('click', (e) => {
        if (e.target === overlay) { overlay.remove(); resolve(null); }
      });
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
