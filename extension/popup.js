const API_BASE = 'http://localhost:8000';
const PER_PAGE = 10;

let allComments = [];
let currentPage = 0;

document.addEventListener('DOMContentLoaded', () => {
  const titleEl    = document.getElementById('videoTitle');
  const analyzeBtn = document.getElementById('analyzeBtn');

  let currentUrl = null;

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
    const isYouTube = currentUrl.includes('youtube.com/watch');

    if (!isYouTube) {
      titleEl.textContent = 'Open a YouTube video to begin.';
      titleEl.className = 'video-title error';
      disableButton();
      return;
    }

    if (currentTab.title) {
      titleEl.textContent = currentTab.title.replace(' - YouTube', '').trim();
      titleEl.className = 'video-title';
    } else {
      titleEl.textContent = 'Unable to fetch title.';
      titleEl.className = 'video-title error';
    }

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
        body: JSON.stringify({ url: currentUrl, max_results: 100 }),
      });

      if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        throw new Error(err.detail || `Server error: ${response.status}`);
      }

      const data = await response.json();
      console.log('Analysis result:', data);

      // Load comments into paginator
      allComments = data.comments;
      currentPage = 0;
      renderPage(currentPage);

      // TODO: renderResults(data) for sentiment scores once ready

    } catch (err) {
      console.error('Analyze failed:', err);
      titleEl.textContent = err.message || 'Failed to reach backend.';
      titleEl.className = 'video-title error';
    } finally {
      setLoading(false);
    }
  });

  // ── Pagination buttons ─────────────────────────────────────────────────────
  document.getElementById('prevBtn').addEventListener('click', () => {
    if (currentPage > 0) {
      currentPage--;
      renderPage(currentPage);
    }
  });

  document.getElementById('nextBtn').addEventListener('click', () => {
    const totalPages = Math.ceil(allComments.length / PER_PAGE);
    if (currentPage < totalPages - 1) {
      currentPage++;
      renderPage(currentPage);
    }
  });
});

// ── Render a page of comments ────────────────────────────────────────────────
function renderPage(page) {
  const list      = document.getElementById('commentsList');
  const prevBtn   = document.getElementById('prevBtn');
  const nextBtn   = document.getElementById('nextBtn');
  const pageInfo  = document.getElementById('pageInfo');
  const pageDots  = document.getElementById('pageDots');

  const totalPages = Math.ceil(allComments.length / PER_PAGE);
  const start = page * PER_PAGE;
  const slice = allComments.slice(start, start + PER_PAGE);

  // Render comment items
  list.innerHTML = '';
  if (slice.length === 0) {
    list.innerHTML = '<div class="comments-empty">No comments found.</div>';
  } else {
    slice.forEach((text) => {
      const item = document.createElement('div');
      item.className = 'comment-item';
      item.textContent = text;
      list.appendChild(item);
    });
    // Scroll back to top on page change
    list.scrollTop = 0;
  }

  // Page info label
  pageInfo.textContent = `${page + 1} / ${totalPages}`;

  // Prev / next state
  prevBtn.disabled = page === 0;
  nextBtn.disabled = page >= totalPages - 1;

  // Dot indicators (max 7 visible dots)
  pageDots.innerHTML = '';
  const maxDots = Math.min(totalPages, 7);
  for (let i = 0; i < maxDots; i++) {
    const dot = document.createElement('div');
    dot.className = 'page-dot' + (i === page % maxDots ? ' active' : '');
    pageDots.appendChild(dot);
  }
}

// ── Helpers ──────────────────────────────────────────────────────────────────
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