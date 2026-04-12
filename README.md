# YTCA - NLP-Powered YouTube Comment Analyzer

**CMPT 310 - D200 Introduction to Artificial Intelligence, Spring 2026**  
Nick Ze Kun Lei, Hayder AL-Musawi, Maxim Maletsky, Kelvin Li

---

## Overview

YTCA is a Chrome extension that analyzes YouTube comment sections in real-time. It fetches up to 100 comments and runs them through a NLP pipeline to produce sentiment breakdowns, thematic clustering, and keyword extraction. All results are displayed in a popup UI with PDF export.

---

## Setup

### 1. Python Environment

Run the following in your terminal from the project root:

```bash
python -m venv .venv
```

**Activate the virtual environment — run this every time you work on the project:**

```bash
.venv\Scripts\activate      # Windows
source .venv/bin/activate   # Mac/Linux
```

### 2. Install Dependencies

```bash
pip install -r backend/requirement.txt
python -m spacy download en_core_web_sm
```

### 3. YouTube API Key

Create a file called `.env` inside the `backend/` folder and add the following:

`YOUTUBE_API_KEY=your_api_key_here`

Replace `your_api_key_here` with your YouTube Data API v3 key. You can obtain one for free from the [Google Cloud Console](https://console.cloud.google.com/) — create a project, enable the YouTube Data API v3, and generate an API key under Credentials.

### 4. Download Frontend Libraries

Chrome extensions cannot load scripts from external CDNs. Download the following files and place them inside the `extension/` folder:

- **Chart.js** → https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js  
  Save as `chart.umd.min.js`

- **jsPDF** → https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js  
  Save as `jspdf.umd.min.js`

---

## Running the Project

### Start the Backend

Open a terminal in the project root, activate your virtual environment, then run:

```bash
cd backend
uvicorn main:app --reload
```

### Load the Chrome Extension

1. Open Chrome and go to `chrome://extensions/`
2. Toggle **Developer Mode** ON (top right)
3. Click **Load unpacked**
4. Select the `extension/` folder

The YT Comment Analyzer icon will appear in your Chrome toolbar.

---

## Usage

1. Navigate to any YouTube video or Short
2. Click the extension icon
3. Click **Analyze Comments**
4. View results across three tabs:
   - **Analyze** — sentiment overview (positive / neutral / negative %)
   - **Comments** — per-comment sentiment badges with category filters and keyword tags
   - **Model** — PCA cluster scatter plot
5. Click **Export** to download a PDF report

You can also manually enter any YouTube URL in the Analyze tab to analyze a video you are not currently watching.

---

## Troubleshooting

**API key not working**  
Make sure your `.env` file is inside the `backend/` folder and has no trailing spaces around the key.

**Models are slow on first request**  
This is expected — models load into memory on first startup. After warming up the response time is much faster.

**Extension not updating after code changes**  
Go to `chrome://extensions/` and click the refresh icon on the CommentIQ card.

**Comments not loading**  
The video may have comments disabled or be private. The backend handles these cases and will return an appropriate error message in the popup.
