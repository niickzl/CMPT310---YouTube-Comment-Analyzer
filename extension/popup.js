const API_BASE = 'http://localhost:8000';
const PER_PAGE = 10;

let allComments = [];
let currentPage = 0;
let lastResult = null;
let currentUrl = null;

document.addEventListener('DOMContentLoaded', () => {
  const titleEl    = document.getElementById('videoTitle');
  const analyzeBtn = document.getElementById('analyzeBtn');
  const exportBtn  = document.getElementById('exportPdf');

  // ── Detect active tab ──────────────────────────────────────
  chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
    const currentTab = tabs[0];

    if (!currentTab || !currentTab.url) {
      titleEl.textContent = 'No active tab found.';
      titleEl.className = 'video-title error';
      disableButton();
      return;
    }

    // DONT REMOVE MY YT SHORTS CHECKER
    currentUrl = currentTab.url;
    const isYouTube = currentUrl.includes('youtube.com/watch') ||
                      currentUrl.includes('youtube.com/shorts');

    if (!isYouTube) {
      titleEl.textContent = 'Open a YouTube video to begin.';
      titleEl.className = 'video-title error';
      disableButton();
      return;
    }

    titleEl.textContent = currentTab.title?.replace(' - YouTube', '').trim() || 'Unknown Video';
    titleEl.className = 'video-title';
  });

  // ── Analyze button ─────────────────────────────────────────
  analyzeBtn.addEventListener('click', async () => {
    if (!currentUrl) return;
    setLoading(true);

    try {
      const response = await fetch(`${API_BASE}/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: currentUrl, max_results: 100 }),
      });

      // Dont remove my error checker
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || `Server error: ${response.status}`);
      }
      lastResult = data;

      renderSentiment(data.sentiment_summary);
      renderKeywords(data.keywords || []);

      allComments = data.comments;
      currentPage = 0;
      renderPage(currentPage);

    } catch (err) {
      titleEl.textContent = 'Backend error.';
      titleEl.className = 'video-title error';
    } finally {
      setLoading(false);
    }
  });

  // ── Export PDF ─────────────────────────────────────────────
  exportBtn.addEventListener('click', async () => {
    if (!lastResult) return alert("Run analysis first!");

    exportBtn.disabled = true;
    exportBtn.textContent = "Generating...";

    await generatePDF();

    exportBtn.disabled = false;
    exportBtn.textContent = "Export as PDF";
  });

  // Pagination
  document.getElementById('prevBtn').onclick = () => {
    if (currentPage > 0) renderPage(--currentPage);
  };

  document.getElementById('nextBtn').onclick = () => {
    if (currentPage < Math.ceil(allComments.length / PER_PAGE) - 1)
      renderPage(++currentPage);
  };
});

// ── CLEAN TEXT (FIX BUGGED CHARACTERS) ───────────────────────
function cleanText(text) {
  return (text || "")
    .replace(/[^\x20-\x7E]/g, '')
    .replace(/\s+/g, ' ')
    .trim();
}

// ── PDF GENERATOR ───────────────────────────────────────────
async function generatePDF() {
  const { jsPDF } = window.jspdf;
  const doc = new jsPDF();

  const summary = lastResult.sentiment_summary;
  const videoId = lastResult.video_id;
  const videoUrl = `https://www.youtube.com/watch?v=${videoId}`;
  const title = document.getElementById('videoTitle').textContent;

  let y = 15;

  // Title
  doc.setFontSize(18);
  doc.text("YouTube Sentiment Report", 10, y);
  y += 10;

  doc.setFontSize(11);
  doc.text(cleanText(title), 10, y);
  y += 8;

  // Link
  doc.setTextColor(0, 102, 204);
  doc.textWithLink("Open Video", 10, y, { url: videoUrl });
  doc.setTextColor(0, 0, 0);
  y += 10;

  // Thumbnail
  const imgData = await fetch(`https://img.youtube.com/vi/${videoId}/0.jpg`)
    .then(r => r.blob())
    .then(blob => new Promise(res => {
      const reader = new FileReader();
      reader.onload = () => res(reader.result);
      reader.readAsDataURL(blob);
    }));

  const pageWidth = doc.internal.pageSize.getWidth();
  const margin = 10;
  const usableWidth = pageWidth - (margin * 2);

  // 16:9 aspect ratio
  const imgHeight = usableWidth * (9 / 16);

  doc.addImage(imgData, 'JPEG', margin, y, usableWidth, imgHeight);
  y += imgHeight + 8;

  // Summary
  doc.text(`Positive: ${summary.positive_pct}%`, 10, y); y += 6;
  doc.text(`Negative: ${summary.negative_pct}%`, 10, y); y += 6;
  doc.text(`Confidence: ${summary.avg_confidence}`, 10, y); y += 10;

  // ── Keywords Section ─────────────────────────────
  doc.setFontSize(12);
  doc.setFont(undefined, 'bold');
  doc.text("Top Keywords", 10, y);
  y += 8;

  doc.setFontSize(10);
  doc.setFont(undefined, 'normal');

  const keywords = lastResult.keywords || [];

  if (keywords.length === 0) {
    doc.text("No keywords available.", 10, y);
    y += 6;
  } else {
    keywords.slice(0, 20).forEach((k, i) => {
      doc.text(
        `${k.word} (${k.count})`,
        10 + (i % 3) * 65,                 // 3 columns
        y + Math.floor(i / 3) * 6          // rows
      );
    });

    y += Math.ceil(Math.min(20, keywords.length) / 3) * 6 + 8;
  }

  // Comments
  doc.setFontSize(12);
  doc.text("Top Comments", 10, y);
  y += 8;

  doc.setFontSize(10);

  const totalComments = lastResult.comments.length;

  let count;
  if (totalComments < 30) {
    count = totalComments;
  } else if (totalComments <= 50) {
    count = totalComments;
  } else {
    count = 50;
  }

  lastResult.comments.slice(0, count).forEach((c, i) => {
    const text = `${i+1}. ${c.sentiment.toUpperCase()} (${Math.round(c.confidence*100)}%)`;

    doc.setFont(undefined, 'bold');
    doc.text(text, 10, y);
    y += 5;

    doc.setFont(undefined, 'normal');

    const wrapped = doc.splitTextToSize(cleanText(c.text), 180);

    doc.text(wrapped, 10, y);
    y += wrapped.length * 5 + 4;

    if (y > 270) {
      doc.addPage();
      y = 15;
    }
  });

const rawTitle = document.getElementById('videoTitle').textContent || "YouTube Video";

const safeTitle = rawTitle
  .replace(/[<>:"/\\|?*\x00-\x1F]/g, '') // remove illegal characters
  .replace(/\s+/g, ' ')
  .trim()
  .replace(/\.$/, '') // remove trailing dot
  .slice(0, 60); // prevent super long filenames

const fileName = `${safeTitle} - Sentiment Report.pdf`;

doc.save(fileName);
}

// ── EXISTING FUNCTIONS (UNCHANGED) ───────────────────────────
function renderSentiment(summary) {
  document.getElementById('posVal').textContent = `${summary.positive_pct}%`;
  document.getElementById('negVal').textContent = `${summary.negative_pct}%`;

  const bar = document.getElementById('sentimentBar');
  bar.style.width = '0%';
  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      bar.style.width = `${summary.positive_pct}%`;
    });
  });
}

function renderKeywords(keywords) {
  const list = document.getElementById('keywordsList');
  list.innerHTML = '';

  if (!keywords.length) {
    list.innerHTML = '<div class="comments-empty">No keywords found.</div>';
    return;
  }

  keywords.forEach(k => {
    const tag = document.createElement('span');
    tag.className = 'keyword-tag';
    tag.innerHTML = `${k.word} <span class="keyword-count">${k.count}</span>`;
    list.appendChild(tag);
  });
}

// fix pages
function renderPage(page) {
  const list      = document.getElementById('commentsList');
  const pageInfo  = document.getElementById('pageInfo');
  const prevBtn   = document.getElementById('prevBtn');
  const nextBtn   = document.getElementById('nextBtn');
  const totalPages = Math.ceil(allComments.length / PER_PAGE);
  const start = page * PER_PAGE;
  const slice = allComments.slice(start, start + PER_PAGE);

  list.innerHTML = '';

  slice.forEach(c => {
    const item = document.createElement('div');
    item.className = 'comment-item';

    item.innerHTML = `
      <span class="sentiment-badge ${c.sentiment}">
        ${c.sentiment} ${Math.round(c.confidence * 100)}%
      </span>
      <span class="comment-text">${c.text}</span>
    `;

    list.appendChild(item);
  });

  pageInfo.textContent = `${page + 1} / ${totalPages}`;
  prevBtn.disabled = page === 0;
  nextBtn.disabled = page >= totalPages - 1;
}

function disableButton() {
  const btn = document.getElementById('analyzeBtn');
  btn.disabled = true;
  btn.style.opacity = '0.3';
}

function setLoading(isLoading) {
  const btn = document.getElementById('analyzeBtn');
  btn.disabled = isLoading;
  btn.textContent = isLoading ? 'Analyzing...' : 'Analyze Comments';
}