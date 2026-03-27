const API_BASE = 'http://localhost:8000';
const PER_PAGE = 10;

let allComments = [];
let currentPage = 0;

document.addEventListener('DOMContentLoaded', () => {
  const titleEl    = document.getElementById('videoTitle');
  const analyzeBtn = document.getElementById('analyzeBtn');
  let currentUrl   = null;

  // ── Detect active tab ──────────────────────────────────────────────────────
  chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
    const currentTab = tabs[0];

    if (!currentTab || !currentTab.url) {
      titleEl.textContent = 'No active tab found.';
      titleEl.className = 'video-title error';
      disableButton();
      return;
    }

    currentUrl = currentTab.url;

    const isYouTube = currentUrl.includes('youtube.com/watch') || 
                      currentUrl.includes('youtube.com/shorts');

    if (!isYouTube) {
      titleEl.textContent = 'Open a YouTube video to begin.';
      titleEl.className = 'video-title error';
      disableButton();
      return;
    }

    titleEl.textContent = currentTab.title
      ? currentTab.title.replace(' - YouTube', '').trim()
      : 'Unable to fetch title.';
    titleEl.className = currentTab.title ? 'video-title' : 'video-title error';

    console.log('Active YouTube URL:', currentUrl);
  });

  // ── Analyze button ─────────────────────────────────────────────────────────
  analyzeBtn.addEventListener('click', async () => {
    if (!currentUrl) return;
    setLoading(true);

    try {
      const response = await fetch(`${API_BASE}/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: currentUrl, max_results: 250 }),
      });

      if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        throw new Error(err.detail || `Server error: ${response.status}`);
      }

      const data = await response.json();
      console.log('Analysis result:', data);

      renderSentiment(data.sentiment_summary);
      renderClusters(data.cluster_summary);

      allComments = data.comments;
      currentPage = 0;
      renderPage(currentPage);

    } catch (err) {
      console.error('Analyze failed:', err);
      titleEl.textContent = err.message || 'Failed to reach backend.';
      titleEl.className = 'video-title error';
    } finally {
      setLoading(false);
    }
  });

  // ── Pagination ─────────────────────────────────────────────────────────────
  document.getElementById('prevBtn').addEventListener('click', () => {
    if (currentPage > 0) { currentPage--; renderPage(currentPage); }
  });
  document.getElementById('nextBtn').addEventListener('click', () => {
    const total = Math.ceil(allComments.length / PER_PAGE);
    if (currentPage < total - 1) { currentPage++; renderPage(currentPage); }
  });
});

// ── Render sentiment summary ───────────────────────────────────────────────────
function renderSentiment(summary) {
  document.getElementById('posVal').textContent = `${summary.positive_pct}%`;
  document.getElementById('negVal').textContent = `${summary.negative_pct}%`;

  const bar = document.getElementById('sentimentBar');
  bar.style.width = '0%';
  requestAnimationFrame(() => requestAnimationFrame(() => {
    bar.style.width = `${summary.positive_pct}%`;
  }));
}

// ── Render cluster bars ────────────────────────────────────────────────────────
function renderClusters(summary) {
  const clusters = [
    { key: 'content',   pct: summary.content_pct },
    { key: 'technical', pct: summary.technical_pct },
    { key: 'general',   pct: summary.general_pct },
  ];

  clusters.forEach(({ key, pct }) => {
    document.getElementById(`pct-${key}`).textContent = `${pct}%`;
    const bar = document.getElementById(`bar-${key}`);
    bar.style.width = '0%';
    requestAnimationFrame(() => requestAnimationFrame(() => {
      bar.style.width = `${pct}%`;
    }));
  });
}

// ── Render a page of comments ──────────────────────────────────────────────────
function renderPage(page) {
  const list     = document.getElementById('commentsList');
  const prevBtn  = document.getElementById('prevBtn');
  const nextBtn  = document.getElementById('nextBtn');
  const pageInfo = document.getElementById('pageInfo');
  const pageDots = document.getElementById('pageDots');

  const totalPages = Math.ceil(allComments.length / PER_PAGE);
  const slice = allComments.slice(page * PER_PAGE, page * PER_PAGE + PER_PAGE);

  list.innerHTML = '';

  if (slice.length === 0) {
    list.innerHTML = '<div class="comments-empty">No comments found.</div>';
  } else {
    slice.forEach((comment) => {
      const item = document.createElement('div');
      item.className = 'comment-item';

      const badges = document.createElement('div');
      badges.className = 'comment-badges';

      const sentimentBadge = document.createElement('span');
      sentimentBadge.className = `sentiment-badge ${comment.sentiment}`;
      sentimentBadge.textContent = comment.sentiment;

      const categoryBadge = document.createElement('span');
      categoryBadge.className = `category-badge ${comment.category.toLowerCase()}`;
      categoryBadge.textContent = comment.category;

      const text = document.createElement('span');
      text.className = 'comment-text';
      text.textContent = comment.text;

      badges.appendChild(sentimentBadge);
      badges.appendChild(categoryBadge);
      item.appendChild(badges);
      item.appendChild(text);
      list.appendChild(item);
    });
    list.scrollTop = 0;
  }

  pageInfo.textContent = `${page + 1} / ${totalPages}`;
  prevBtn.disabled = page === 0;
  nextBtn.disabled = page >= totalPages - 1;

  pageDots.innerHTML = '';
  const maxDots = Math.min(totalPages, 7);
  for (let i = 0; i < maxDots; i++) {
    const dot = document.createElement('div');
    dot.className = 'page-dot' + (i === page % maxDots ? ' active' : '');
    pageDots.appendChild(dot);
  }
}

// ── Helpers ────────────────────────────────────────────────────────────────────
function disableButton() {
  const btn = document.getElementById('analyzeBtn');
  btn.disabled = true;
  btn.style.opacity = '0.3';
  btn.style.cursor = 'not-allowed';
}

function setLoading(isLoading) {
  const btn = document.getElementById('analyzeBtn');
  btn.disabled = isLoading;
  btn.textContent = isLoading ? 'Analyzing...' : 'Analyze Comments';
  btn.style.opacity = isLoading ? '0.6' : '1';
  btn.style.cursor = isLoading ? 'wait' : 'pointer';
}