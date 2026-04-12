const API_BASE = 'http://localhost:8000';
const PER_PAGE = 10;

let allComments = [];
let currentPage = 0;
let lastResult = null;
let currentUrl = null;
let activeSentiment = 'all'; // "all" | "positive" | "neutral" | "negative"
let activeFilter    = 'all'; // "all" | "Content" | "Technical" | "General" | keyword string

document.addEventListener('DOMContentLoaded', () => {
  const titleEl    = document.getElementById('videoTitle');
  const analyzeBtn = document.getElementById('analyzeBtn');
  const exportBtn  = document.getElementById('exportPdf');
  const urlInput   = document.getElementById('urlInput');
  const urlConfirm = document.getElementById('urlConfirm');

  // Tab switching
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
      btn.classList.add('active');
      document.getElementById(`tab-${btn.dataset.tab}`).classList.add('active');
    });
  });

  // Detect active tab
  chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
    const currentTab = tabs[0];
    // DONT REMOVE MY YT SHORTS CHECKER
    const isYouTube = currentTab?.url &&
      (currentTab.url.includes('youtube.com/watch') ||
       currentTab.url.includes('youtube.com/shorts'));

    if (isYouTube) {
      currentUrl = currentTab.url;
      titleEl.textContent = currentTab.title?.replace(' - YouTube', '').trim() || 'Unknown Video';
      titleEl.className = 'video-title';
    } else {
      disableButton();
    }
  });

  // URL confirm button
  urlConfirm.addEventListener('click', async () => {
    const val = urlInput.value.trim();
    if (!val) return;
    const isValid = val.includes('youtube.com/watch') ||
                    val.includes('youtube.com/shorts') ||
                    val.includes('youtu.be/');
    if (!isValid) {
      titleEl.textContent = 'Invalid YouTube URL.';
      titleEl.className = 'video-title error';
      return;
    }
    currentUrl = val;
    titleEl.textContent = 'Loading title...';
    titleEl.className = 'video-title loading';
    analyzeBtn.disabled = false;
    analyzeBtn.style.opacity = '1';
    analyzeBtn.style.cursor = 'pointer';
    try {
      const res = await fetch(`https://www.youtube.com/oembed?url=${encodeURIComponent(val)}&format=json`);
      const json = await res.json();
      titleEl.textContent = json.title || val;
    } catch {
      titleEl.textContent = val;
    }
    titleEl.className = 'video-title';
  });

  // Analyze button
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
      lastResult.video_title = document.getElementById('videoTitle').textContent;

      renderSentiment(data.sentiment_summary);
      renderKeywords(data.keywords || []);
      renderChart(data.cluster_summary);

      allComments = data.comments;
      currentPage = 0;
      renderPage(currentPage);

    } catch (err) {
      titleEl.textContent = err.message || 'Backend error.';
      titleEl.className = 'video-title error';
    } finally {
      setLoading(false);
    }
  });

  // Export PDF
  exportBtn.addEventListener('click', async () => {
    if (!lastResult) return alert("Run analysis first!");
    exportBtn.disabled = true;
    exportBtn.textContent = "Generating...";
    await generatePDF();
    exportBtn.disabled = false;
    exportBtn.textContent = "Export";
  });

  // Sentiment filter buttons
  document.getElementById('sentimentRow').addEventListener('click', (e) => {
    const btn = e.target.closest('.sent-btn');
    if (!btn) return;
    setSentimentFilter(btn.dataset.sentiment);
  });
  // Category filter buttons
  document.getElementById('filterRow').addEventListener('click', (e) => {
    const btn = e.target.closest('.filter-btn');
    if (!btn) return;
    setFilter(btn.dataset.filter);
  });
  
  document.getElementById('prevBtn').onclick = () => {
    if (currentPage > 0) { renderPage(--currentPage); }
  };
  document.getElementById('nextBtn').onclick = () => {
    if (currentPage < Math.ceil(filteredComments().length / PER_PAGE) - 1) {
      renderPage(++currentPage);
    }
  };
});

// CLEAN TEXT (FIX BUGGED CHARACTERS)
function cleanText(text) {
  return (text || "")
    .replace(/[^\x20-\x7E]/g, '')
    .replace(/\s+/g, ' ')
    .trim();
}

// PDF GENERATOR
async function generatePDF() {
  const { jsPDF } = window.jspdf;
  const doc = new jsPDF();

  const summary = lastResult.sentiment_summary;
  const videoId = lastResult.video_id;
  const videoUrl = `https://www.youtube.com/watch?v=${videoId}`;
  const title = document.getElementById('videoTitle').textContent;

  let y = 15;

  doc.setFontSize(18);
  doc.text("YouTube Sentiment Report", 10, y);
  y += 10;

  doc.setFontSize(11);
  doc.text(cleanText(title), 10, y);
  y += 8;

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
  const imgHeight = usableWidth * (9 / 16);

  doc.addImage(imgData, 'JPEG', margin, y, usableWidth, imgHeight);
  y += imgHeight + 8;

  // Summary
  doc.text(`Positive: ${summary.positive_pct}%`, 10, y); y += 6;
  doc.text(`Neutral:  ${summary.neutral_pct}%`, 10, y); y += 6;
  doc.text(`Negative: ${summary.negative_pct}%`, 10, y); y += 6;
  doc.text(`Confidence: ${summary.avg_confidence}`, 10, y); y += 10;

  // Keywords
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
      doc.text(`${k.word} (${k.count})`, 10 + (i % 3) * 65, y + Math.floor(i / 3) * 6);
    });
    y += Math.ceil(Math.min(20, keywords.length) / 3) * 6 + 8;
  }

  // Comments
  doc.setFontSize(12);
  doc.setFont(undefined, 'bold');
  doc.text("Top Comments", 10, y);
  y += 8;
  doc.setFontSize(10);
  doc.setFont(undefined, 'normal');

  const count = Math.min(lastResult.comments.length, 50);
  lastResult.comments.slice(0, count).forEach((c, i) => {
    doc.setFont(undefined, 'bold');
    doc.text(`${i+1}. ${c.sentiment.toUpperCase()} (${Math.round(c.confidence*100)}%)`, 10, y);
    y += 5;
    doc.setFont(undefined, 'normal');
    const wrapped = doc.splitTextToSize(cleanText(c.text), 180);
    doc.text(wrapped, 10, y);
    y += wrapped.length * 5 + 4;
    if (y > 270) { doc.addPage(); y = 15; }
  });

  const safeTitle = cleanText(title)
    .replace(/[<>:"/\\|?*\x00-\x1F]/g, '')
    .trim().replace(/\.$/, '').slice(0, 60);
  doc.save(`${safeTitle} - Sentiment Report.pdf`);
}

// Render cluster charts
let _scatterChart = null;

function renderChart(cluster) {
  if (!cluster) return;
  const emptyMsg = document.getElementById('modelEmpty');
  if (emptyMsg) emptyMsg.style.display = 'none';

  const COLOURS = {
    'Content':   { border: '#7c6af7', bg: 'rgba(124,106,247,0.7)' },
    'Technical': { border: '#ffd740', bg: 'rgba(255,215,64,0.7)'  },
    'General':   { border: '#40c4ff', bg: 'rgba(64,196,255,0.7)'  },
  };

  const groups = { Content: [], Technical: [], General: [] };
  (lastResult.comments || []).forEach(c => {
    if (groups[c.category]) groups[c.category].push(c);
  });

  const scatterDatasets = Object.entries(groups).map(([cat, comments]) => ({
    label: cat,
    data: comments.map(c => ({ x: c.x, y: c.y, text: c.text, sentiment: c.sentiment })),
    backgroundColor: COLOURS[cat].bg,
    borderColor: COLOURS[cat].border,
    borderWidth: 1,
    pointRadius: 4,
    pointHoverRadius: 6,
  }));

  const scatterCanvas = document.getElementById('scatterChart');
  if (_scatterChart) { _scatterChart.destroy(); _scatterChart = null; }

  _scatterChart = new Chart(scatterCanvas, {
    type: 'scatter',
    data: { datasets: scatterDatasets },
    options: {
      responsive: true,
      plugins: {
        legend: {
          display: true,
          labels: { color: '#afafaf', font: { size: 10 }, boxWidth: 10 },
        },
        tooltip: {
          callbacks: {
            label: ctx => {
              const d = ctx.raw;
              const preview = (d.text || '').slice(0, 60) + (d.text?.length > 60 ? '…' : '');
              return [`[${ctx.dataset.label}] ${d.sentiment}`, preview];
            },
          },
        },
      },
      scales: {
        x: { ticks: { color: '#afafaf', font: { size: 9 } }, grid: { color: '#242424' } },
        y: { ticks: { color: '#afafaf', font: { size: 9 } }, grid: { color: '#242424' } },
      },
    },
  });
}

// Filter helpers
function filteredComments() {
  let results = allComments;

    // Sentiment filter
  if (activeSentiment !== 'all') {
    results = results.filter(c => c.sentiment === activeSentiment);
  }

  // Category / keyword filter
  if (activeFilter !== 'all') {
    const cats = ['Content', 'Technical', 'General'];
    if (cats.includes(activeFilter)) {
      results = results.filter(c => c.category === activeFilter);
    } else {
      results = results.filter(c => c.text.toLowerCase().includes(activeFilter.toLowerCase()));
    }
  }

  return results;
}

function setFilter(filter) {
  activeFilter = filter;
  currentPage  = 0;

  // Update category filter button states (exclude sent-btn to avoid conflicts)
  document.querySelectorAll('#filterRow .filter-btn').forEach(b => {
    b.classList.toggle('active', b.dataset.filter === filter);
  });

  // Update keyword tag states
  document.querySelectorAll('.keyword-tag').forEach(t => {
    t.classList.toggle('active', t.dataset.keyword === filter);
  });

  renderPage(0);
}

function setSentimentFilter(sentiment) {
  activeSentiment = sentiment;
  currentPage     = 0;

  document.querySelectorAll('.sent-btn').forEach(b => {
    b.classList.toggle('active', b.dataset.sentiment === sentiment);
  });

  renderPage(0);
}

// Render functions
function renderSentiment(summary) {
  document.getElementById('posVal').textContent = `${summary.positive_pct}%`;
  document.getElementById('neuVal').textContent = `${summary.neutral_pct}%`;
  document.getElementById('negVal').textContent = `${summary.negative_pct}%`;
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
    tag.dataset.keyword = k.word;
    tag.innerHTML = `${k.word} <span class="keyword-count">${k.count}</span>`;
    tag.addEventListener('click', () => {
      // Toggle off if already active
      setFilter(activeFilter === k.word ? 'all' : k.word);
    });
    list.appendChild(tag);
  });
}

function renderPage(page) {
  const list       = document.getElementById('commentsList');
  const pageInfo   = document.getElementById('pageInfo');
  const prevBtn    = document.getElementById('prevBtn');
  const nextBtn    = document.getElementById('nextBtn');
  const visible    = filteredComments();
  const totalPages = Math.ceil(visible.length / PER_PAGE) || 1;
  const slice      = visible.slice(page * PER_PAGE, page * PER_PAGE + PER_PAGE);

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
  btn.style.cursor = 'not-allowed';
}

function setLoading(isLoading) {
  const btn = document.getElementById('analyzeBtn');
  btn.disabled = isLoading;
  btn.textContent = isLoading ? 'Analyzing...' : 'Analyze Comments';
}