Here you go, Peak — a full-blown README you can drop straight into your repo as README.md. I’ll assume:
	•	Repo name: nsc-carbon-footprint-calculator
	•	App file: nsc_web_co2_streamlit.py

You can tweak naming if needed.

⸻


# 🌱 Nani Summit Creative – Website CO₂ Estimator

A lightweight web tool for estimating the **per-page-view CO₂ emissions** of a website, comparing:

- **First visit** (cold cache)
- **Return visit** (warm cache / cached assets, approximated)

The app:

- Estimates data transfer (bytes → MB → GB)
- Converts that into **energy (kWh)** and **CO₂ (g)** using the Sustainable Web Design model
- Assigns a **strict letter grade (A–F)** for each visit
- Runs as a **Streamlit app**, either:
  - Publicly on **Streamlit Community Cloud**, or  
  - Locally on your machine with full Playwright/browser support.

Built and used by **Nani Summit Creative** to help outdoor brands and purpose-driven organizations understand and reduce the footprint of their websites.

---

## 🚀 Features

- **Per-URL CO₂ estimation**
  - Paste a URL, click a button, get first vs. return visit stats.
- **First vs return visit comparison**
  - Shows data transfer, energy, and CO₂ for both visits.
  - Return visit is based on caching behavior (full browser locally, header-based approximation on Streamlit Cloud).
- **Strict letter grading (A–F)**
  - Grades based on rounded CO₂ per page view (grams).
  - A is intentionally hard to get; most modern sites will be B/C/D.
- **Two measurement modes**
  - **Playwright mode (local / full browser)** – most accurate, with JS execution.
  - **HTTP-only mode (fallback)** – uses `requests` + `BeautifulSoup` + cache headers; used automatically on platforms where running a browser is not possible (e.g., Streamlit Cloud without system deps).
- **JSON output**
  - Raw results shown as JSON, useful for logging or reporting.
- **Nani Summit Creative branding**
  - Small “About” footer describing the philosophy of lower-carbon, high-performing websites.

---

## 🧮 How the CO₂ model works

The estimator uses a simplified and widely referenced approach inspired by the **Sustainable Web Design** model:

1. **Sum all transferred bytes for a page view**
2. Convert bytes → GB:
   \[
   \text{GB} = \frac{\text{bytes}}{1024^3}
   \]
3. Estimate energy:
   \[
   \text{kWh} = \text{GB} \times 0.81
   \]
4. Estimate CO₂:
   \[
   \text{CO₂ (g)} = \text{kWh} \times 442
   \]

With constants:

- `KWH_PER_GB = 0.81`
- `GRID_INTENSITY = 442 gCO₂e/kWh`

These are **global averages** and should be understood as **directional** rather than lab-grade precise.

---

## 🎓 Letter grading scale (strict)

Grading is based on **rounded CO₂ per page view** (to 2 decimal places), in **grams**:

- **A**: ≤ 0.20 g  
- **B**: 0.20–0.70 g  
- **C**: 0.70–1.10 g  
- **D**: 1.10–1.60 g  
- **F**: > 1.60 g  

This is intentionally strict:

- A: Very rare, ultra-light pages.
- B: Good, efficient sites (e.g., a well-optimized marketing page).
- C: Around average modern site.
- D/F: Heavy sites that would benefit from serious optimization.

---

## 🏗 Repository structure

Example minimal structure:

```text
nsc-carbon-footprint-calculator/
├─ nsc_web_co2_streamlit.py   # Main Streamlit app
├─ requirements.txt           # Python dependencies
└─ README.md                  # This file


⸻
```
🔧 Requirements
	•	Python: 3.9+ (recommended)
	•	For local full-browser mode:
	•	Playwright Python package
	•	Chromium browser installed by Playwright
	•	Some OS system libraries (on Linux)

⸻

📦 Installation

Clone the repo:

git clone https://github.com/your-username/nsc-carbon-footprint-calculator.git
cd nsc-carbon-footprint-calculator

Create and activate a virtual environment (recommended):

python -m venv venv
# macOS/Linux:
source venv/bin/activate
# Windows:
# venv\Scripts\activate

Install dependencies:

pip install --upgrade pip
pip install -r requirements.txt

requirements.txt example

streamlit
playwright
requests
beautifulsoup4

Install Playwright browser (for local full mode):

playwright install chromium

On Linux, you may also need system deps:

playwright install-deps



(You don’t need that on Streamlit Cloud; the app falls back to HTTP-only mode there.)

⸻

🖥 Running locally (full-featured mode)

Once dependencies are installed:

streamlit run nsc_web_co2_streamlit.py

Streamlit will:
	•	Start a local dev server (usually at http://localhost:8501)
	•	Open the app in your browser

Local app behavior

Locally, the app will:
	1.	Try Playwright mode:
	•	Launch a headless Chromium browser.
	•	Load the page twice in the same browser context:
	•	First visit (cold cache).
	•	Second visit (warm cache).
	•	For each network response, measure size via:
	•	Content-Length header when available.
	•	Otherwise, the actual response body length.
	2.	Compute:
	•	Total bytes
	•	MB, GB
	•	Energy (kWh)
	•	CO₂ (g)
	3.	Round CO₂ to 2 decimals and apply the strict letter grade.

If Playwright fails locally (e.g., missing browser), the app will automatically fall back to HTTP-only mode (see below).

⸻

🌐 Running on Streamlit Community Cloud
	1.	Push your repo to GitHub (public or private).
	2.	Ensure it includes:
	•	nsc_web_co2_streamlit.py
	•	requirements.txt
	•	README.md (optional but recommended)
	3.	Go to Streamlit Community Cloud￼.
	4.	Click “New app” and select:
	•	Repository: your-username/nsc-carbon-footprint-calculator
	•	Branch: main
	•	Main file: nsc_web_co2_streamlit.py
	5.	Click Deploy.

Streamlit Cloud will:
	•	Install dependencies from requirements.txt
	•	Run the app
	•	Give you a public URL, e.g.:

https://nsc-web-co2-yourname.streamlit.app

On Streamlit Cloud – measurement mode

Most managed hosts (including Streamlit Cloud) don’t allow installing all the system libraries needed for Playwright’s Chromium browser. When that happens:
	•	The app automatically detects Playwright failure.
	•	It falls back to HTTP-only mode.

You’ll see a small warning in the UI:

“Running in HTTP-only mode (no full browser available on this host). JavaScript-heavy pages and caching behavior are approximated from headers.”

This fallback is still useful and directionally correct, but less accurate than full browser mode.

⸻

🔍 How HTTP-only fallback works

When Playwright isn’t available, the app uses:
	•	requests to fetch:
	•	Main HTML
	•	Linked assets (images, scripts, stylesheets, video sources, etc.)
	•	BeautifulSoup to discover asset URLs in HTML:
	•	<img src="...">
	•	<script src="...">
	•	<link href="...">
	•	<video src="..."> and <source src="...">

First visit (HTTP-only mode)
	1.	Fetch the main URL with GET.
	2.	Parse HTML to find asset URLs.
	3.	For each resource URL:
	•	Try HEAD (for Content-Length).
	•	If no length, fall back to GET and count body length.
	4.	Sum all bytes across:
	•	Main HTML
	•	Images
	•	Scripts
	•	Stylesheets
	•	Video sources, etc.

Return visit (HTTP-only mode)

We approximate what would load on a return visit based on cache headers:
	•	If Cache-Control contains:
	•	no-cache, no-store, must-revalidate, or max-age=0 → treat as refetched
	•	If Cache-Control has max-age:
	•	If max-age >= 86400 seconds (1 day) → treat as cached (NOT refetched)
	•	Otherwise → treat as refetched
	•	If no usable cache headers → assume refetched

Then:
	•	Sum bytes for resources that we believe are refetched.
	•	Apply a safety floor:
	•	If the computed return-visit bytes are less than 10% of first-visit bytes, we bump them up to 10% to avoid unrealistically tiny return visits.

This is clearly labeled as approximate in the UI.

⸻

🧑‍💻 Code overview

Main file: nsc_web_co2_streamlit.py

Key parts:
	•	Measurement utilities
	•	bytes_to_mb_gb(num_bytes)
	•	co2_for_bytes(num_bytes, kwh_per_gb, grid_intensity)
	•	Grading
	•	grade_from_co2(co2_g)
Applies the strict A–F thresholds.
	•	grade_description(letter)
Human-readable explanation per grade.
	•	Playwright mode
	•	launch_browser(headless=True)
Context manager to launch a headless Chromium instance.
	•	measure_visit_playwright(context, url)
Loads the URL, listens to response events, and sums byte sizes.
	•	run_measurements_playwright(url, headless=True)
First + second visit in same browser context.
	•	HTTP-only mode
	•	collect_resource_urls(base_url, html)
Uses BeautifulSoup to discover resource URLs.
	•	fetch_resource_metadata(url)
Tries HEAD then GET, returns (length_in_bytes, headers).
	•	_parse_max_age(cache_control)
Extracts max-age from a header string.
	•	should_refetch_on_return(headers)
Determines if a resource is likely to be reloaded on return.
	•	run_measurements_http(url)
First + return visit estimation, plus safety floor.
	•	Wrapper
	•	run_measurements(url, headless=True)
Tries Playwright first; if it throws an exception, falls back to HTTP-only.
	•	Streamlit UI
	•	URL input, headless checkbox, “Run measurement” button.
	•	Overview metrics:
	•	Letter grade
	•	Data (MB/GB)
	•	Energy (kWh)
	•	CO₂ (g, rounded)
	•	“What the grades mean” section.
	•	Raw data table + JSON output.
	•	Nani Summit Creative footer.

⸻

🧱 Example usage

Local (dev / internal use)

streamlit run nsc_web_co2_streamlit.py

Then:
	1.	Go to the browser window that opens.
	2.	Enter a URL, e.g. https://nanisummitcreative.com.
	3.	Leave “Run browser headless” checked (recommended).
	4.	Click Run measurement.

You’ll see:
	•	First vs return visit data and grades.
	•	A stricter grading scale where A is rare.
	•	JSON you can export or copy into other tools.

Streamlit Cloud (public tool)
	1.	Deploy via Streamlit as described above.
	2.	Share the Streamlit URL publicly or link it from your site.
	3.	Visitors paste their own URLs and get a “first pass” sustainability/performance read.

⸻

⚠️ Limitations & caveats
	•	Estimates, not absolutes
	•	Based on global average energy and CO₂ factors.
	•	Real values will vary by user’s location, device, and network.
	•	HTTP-only mode is approximate
	•	No JavaScript execution (no SPA routing, no lazy-loaded assets discovered by runtime JS).
	•	Caching is estimated from headers, not a real browser cache.
	•	Dynamic / personalized content
	•	A/B tests, personalization, geolocation, and ads can change payloads between runs.
	•	Largest impact: assets & JS
	•	Big images, heavy JS bundles, and video are usually the main drivers of high CO₂ per view.

The tool is best used for:
	•	Comparisons over time (before vs after an optimization).
	•	Comparisons between pages on the same site.
	•	Storytelling with clients about performance & sustainability.

⸻

👣 About Nani Summit Creative

From the app footer:

We build lower-carbon, high-performing websites for outdoor brands and purpose-driven organizations. The goal is simple: faster sites that tread lighter on the planet, without sacrificing good design or real-world results.

If you’re curious how your site stacks up — or want to make your next build a little greener — this tool is one of the nerdy ways we like to start that conversation.

You can customize that copy to match your current positioning, site URL, or call to action (e.g. a “Work with us” link).

⸻

🛠 Troubleshooting

ModuleNotFoundError: No module named 'bs4'

You’re missing BeautifulSoup. Make sure beautifulsoup4 is in requirements.txt and installed:

pip install beautifulsoup4

ModuleNotFoundError: No module named 'playwright'

Install Playwright:

pip install playwright
playwright install chromium

Playwright “missing browser” / “install-deps” errors (Linux)

Run:

playwright install chromium
playwright install-deps

If you’re on a managed host (like Streamlit Cloud), you usually can’t run install-deps — the app will just fall back to HTTP-only mode automatically.

⸻

🧭 Roadmap ideas

Some natural next steps you might add later:
	•	Batch mode: upload a CSV of URLs and measure all of them.
	•	Simple export: “Download JSON” or “Download CSV”.
	•	Per-visit assumptions: let the user adjust:
	•	kWh/GB
	•	Grid intensity (gCO₂/kWh) for different regions.
	•	A small “how to improve” section based on page weight thresholds.

⸻

If you’re reading this in GitHub, feel free to open issues or PRs to improve the heuristics, add features, or tune the grading scale.

