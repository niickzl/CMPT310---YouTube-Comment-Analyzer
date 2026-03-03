document.addEventListener('DOMContentLoaded', () => {
  chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
    const currentTab = tabs[0];
    const titleEl = document.getElementById('videoTitle');

    if (!currentTab || !currentTab.url) {
      titleEl.textContent = 'No active tab found.';
      titleEl.className = 'video-title error';
      return;
    }

    const url = currentTab.url;
    const isYouTube = url.includes('youtube.com/watch');

    if (!isYouTube) {
      titleEl.textContent = 'Open a YouTube video to begin.';
      titleEl.className = 'video-title error';
      document.getElementById('analyzeBtn').disabled = true;
      document.getElementById('analyzeBtn').style.opacity = '0.3';
      document.getElementById('analyzeBtn').style.cursor = 'not-allowed';
      return;
    }

    // Try to get the title from the tab
    if (currentTab.title) {
      let title = currentTab.title.replace(' - YouTube', '').trim();
      titleEl.textContent = title;
      titleEl.className = 'video-title';
    } else {
      titleEl.textContent = 'Unable to fetch title.';
      titleEl.className = 'video-title error';
    }

    console.log('Active YouTube URL:', url);
  });

  document.getElementById('analyzeBtn').addEventListener('click', () => {
    // Placeholder — analysis logic goes here
    console.log('Analyze clicked');
  });
});