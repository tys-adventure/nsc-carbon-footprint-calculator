#!/usr/bin/env python3

import streamlit as st
from contextlib import contextmanager
from playwright.sync_api import sync_playwright
import subprocess
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

# --- Ensure Playwright browsers are available (for environments that support it) ---

@st.cache_resource
def ensure_playwright_browsers_installed():
    """
    Install the Chromium browser for Playwright if it isn't already present.
    Cached so it only runs once per container.
    """
    try:
        subprocess.run(
            ["playwright", "install", "chromium"],
            check=False,
            capture_output=True,
            text=True,
        )
    except Exception:
        # If this fails, we'll see the error when trying to launch the browser anyway
        pass

    return True


# --- Constants (Sustainable Web Design-ish model) ---
KWH_PER_GB = 0.81          # kWh of energy per GB of data transferred
GRID_INTENSITY = 442       # gCO2e per kWh (global average grid)


# ---------- Core measurement utilities ----------

def bytes_to_mb_gb(num_bytes: int):
    mb = num_bytes / (1024 ** 2)
    gb = num_bytes / (1024 ** 3)
    return mb, gb


def co2_for_bytes(num_bytes: int, kwh_per_gb: float = KWH_PER_GB,
                  grid_intensity: float = GRID_INTENSITY):
    _, gb = bytes_to_mb_gb(num_bytes)
    energy_kwh = gb * kwh_per_gb
    co2_grams = energy_kwh * grid_intensity
    return energy_kwh, co2_grams


def grade_from_co2(co2_g: float) -> str:
    """
    Strict grading scale (rounded CO₂ in grams per page view):
    A: <= 0.20 g
    B: 0.20–0.70 g
    C: 0.70–1.10 g
    D: 1.10–1.60 g
    F: > 1.60 g
    """
    if co2_g <= 0.20:
        return "A"
    elif co2_g <= 0.70:
        return "B"
    elif co2_g <= 1.10:
        return "C"
    elif co2_g <= 1.60:
        return "D"
    else:
        return "F"


def grade_description(letter: str) -> str:
    descriptions = {
        "A": "Excellent – ultra-light page, great for performance and the planet.",
        "B": "Good – efficient overall, with room for a bit more optimization.",
        "C": "Okay – around average; optimizations would make a real impact.",
        "D": "Heavy – likely room to trim assets, images, and scripts.",
        "F": "Very heavy – urgently needs performance and sustainability work.",
    }
    return descriptions.get(letter, "")


# ---------- Playwright-based measurement (best when available) ----------

@contextmanager
def launch_browser(headless: bool = True):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        try:
            yield browser
        finally:
            browser.close()


def measure_visit_playwright(context, url: str, wait_until: str = "networkidle", timeout: int = 60000):
    """
    Load `url` inside a given Playwright browser context and sum all
    response sizes for that visit.

    Returns total bytes transferred for that page load.
    """
    page = context.new_page()
    total_bytes = 0

    def handle_response(response):
        nonlocal total_bytes
        try:
            req = response.request
            res_url = req.url
            if res_url.startswith("data:") or res_url.startswith("about:"):
                return

            length = 0

            # Try Content-Length header first
            cl = response.headers.get("content-length")
            if cl:
                try:
                    length = int(cl)
                except ValueError:
                    length = 0

            # If no Content-Length header, fall back to actual body length
            if length == 0:
                try:
                    body = response.body()
                    length = len(body)
                except Exception:
                    length = 0

            total_bytes += length
        except Exception:
            # Don't let a single bad response crash the measurement
            pass

    page.on("response", handle_response)

    page.goto(url, wait_until=wait_until, timeout=timeout)

    # Optional: small extra wait to let late resources finish
    page.wait_for_timeout(2000)
    page.close()
    return total_bytes


def run_measurements_playwright(url: str, headless: bool = True):
    """
    Full-browser measurement using Playwright.
    """
    # Ensure browsers installed (for supported environments)
    ensure_playwright_browsers_installed()

    with launch_browser(headless=headless) as browser:
        context = browser.new_context()

        first_bytes = measure_visit_playwright(context, url)
        second_bytes = measure_visit_playwright(context, url)

        context.close()

    first_energy_kwh, first_co2_g = co2_for_bytes(first_bytes)
    second_energy_kwh, second_co2_g = co2_for_bytes(second_bytes)

    results = {
        "url": url,
        "model": {
            "kwh_per_gb": KWH_PER_GB,
            "grid_intensity_g_per_kwh": GRID_INTENSITY,
            "mode": "playwright",
            "notes": (
                "Estimates use Sustainable Web Design model constants. "
                "Data transfer measured via headless Chromium + Playwright."
            ),
        },
        "first_visit": {
            "bytes": first_bytes,
            "mb": bytes_to_mb_gb(first_bytes)[0],
            "gb": bytes_to_mb_gb(first_bytes)[1],
            "energy_kwh": first_energy_kwh,
            "co2_g": first_co2_g,
        },
        "return_visit": {
            "bytes": second_bytes,
            "mb": bytes_to_mb_gb(second_bytes)[0],
            "gb": bytes_to_mb_gb(second_bytes)[1],
            "energy_kwh": second_energy_kwh,
            "co2_g": second_co2_g,
        },
    }

    return results


# ---------- HTTP-only fallback measurement (no real browser) ----------

def collect_resource_urls(base_url: str, html: str):
    """
    Very simple static asset discovery: HTML + common assets.
    """
    soup = BeautifulSoup(html, "html.parser")
    urls = set()

    # Always include the main document itself
    urls.add(base_url)

    tag_attr_pairs = [
        ("img", "src"),
        ("script", "src"),
        ("link", "href"),
        ("video", "src"),
        ("source", "src"),
    ]

    for tag, attr in tag_attr_pairs:
        for el in soup.find_all(tag):
            src = el.get(attr)
            if not src:
                continue
            full = urljoin(base_url, src)
            urls.add(full)

    return urls


def fetch_resource_metadata(url: str, timeout: int = 20):
    """
    Best-effort fetch of a resource's size and caching headers.
    Returns (bytes, headers_dict).
    """
    headers = {}
    length = 0

    try:
        # Try HEAD first
        head_resp = requests.head(url, timeout=timeout, allow_redirects=True)
        headers = {k.lower(): v for k, v in head_resp.headers.items()}
        cl = headers.get("content-length")
        if cl:
            try:
                length = int(cl)
            except ValueError:
                length = 0

        # If no length, fall back to GET
        if length == 0:
            get_resp = requests.get(url, timeout=timeout, stream=True)
            headers = {k.lower(): v for k, v in get_resp.headers.items()}
            cl = headers.get("content-length")
            if cl:
                try:
                    length = int(cl)
                except ValueError:
                    length = 0
            else:
                # As a last resort, read content to determine length
                content = get_resp.content
                length = len(content)

    except Exception:
        # On error, just treat as zero-length resource
        length = 0

    return length, headers


def _parse_max_age(cache_control: str):
    """
    Extract max-age seconds from a Cache-Control header, or None if missing/unparseable.
    """
    for part in cache_control.split(","):
        part = part.strip()
        if part.startswith("max-age"):
            pieces = part.split("=", 1)
            if len(pieces) == 2:
                try:
                    return int(pieces[1])
                except ValueError:
                    return None
    return None


def should_refetch_on_return(headers: dict) -> bool:
    """
    Heuristic: decide if a resource is likely to be refetched on a return visit.

    We are intentionally conservative:
    - If we DON'T see a strong, long-lived cache (max-age >= 1 day), we assume
      the resource WILL be refetched.
    - Only assets with clear, long max-age are treated as cached.
    """
    cc = headers.get("cache-control", "").lower()
    pragma = headers.get("pragma", "").lower()

    # Explicit "don't cache" directives → refetch
    if any(token in cc for token in ["no-cache", "no-store", "must-revalidate"]) or "max-age=0" in cc:
        return True
    if "no-cache" in pragma:
        return True

    # If Cache-Control exists, check max-age
    if cc:
        max_age = _parse_max_age(cc)
        if max_age is not None:
            # Treat as cached only if max-age is at least 1 day
            if max_age >= 86400:
                return False
            else:
                return True
        # Cache-Control present but no usable max-age → assume refetch
        return True

    # No Cache-Control header at all → assume refetch
    return True


def run_measurements_http(url: str):
    """
    Fallback measurement using plain HTTP requests only.
    No JavaScript execution, approximate caching behavior.
    """
    try:
        resp = requests.get(url, timeout=20)
    except Exception:
        # If we can't even fetch the main HTML, bail similarly to Playwright.
        raise

    html = resp.text
    resource_urls = collect_resource_urls(url, html)

    resources = []
    for res_url in resource_urls:
        length, headers = fetch_resource_metadata(res_url)
        resources.append(
            {
                "url": res_url,
                "bytes": length,
                "headers": headers,
            }
        )

    first_bytes = sum(r["bytes"] for r in resources)
    # Approximate "return visit" by summing only resources that are likely to be re-fetched
    second_bytes = sum(
        r["bytes"] for r in resources if should_refetch_on_return(r["headers"])
    )

    # Safety floor so we don't return unrealistically tiny second visits
    if first_bytes > 0 and second_bytes < first_bytes * 0.1:
        second_bytes = int(first_bytes * 0.1)

    first_energy_kwh, first_co2_g = co2_for_bytes(first_bytes)
    second_energy_kwh, second_co2_g = co2_for_bytes(second_bytes)

    results = {
        "url": url,
        "model": {
            "kwh_per_gb": KWH_PER_GB,
            "grid_intensity_g_per_kwh": GRID_INTENSITY,
            "mode": "http-only",
            "notes": (
                "Estimates use Sustainable Web Design model constants. "
                "Data transfer approximated via HTTP requests only (no JS execution)."
            ),
        },
        "first_visit": {
            "bytes": first_bytes,
            "mb": bytes_to_mb_gb(first_bytes)[0],
            "gb": bytes_to_mb_gb(first_bytes)[1],
            "energy_kwh": first_energy_kwh,
            "co2_g": first_co2_g,
        },
        "return_visit": {
            "bytes": second_bytes,
            "mb": bytes_to_mb_gb(second_bytes)[0],
            "gb": bytes_to_mb_gb(second_bytes)[1],
            "energy_kwh": second_energy_kwh,
            "co2_g": second_co2_g,
        },
    }

    return results


# ---------- Wrapper: try Playwright, fall back to HTTP-only ----------

def run_measurements(url: str, headless: bool = True):
    """
    Try full Playwright measurement first. If the environment doesn't support
    running browsers (like some managed hosts), fall back to HTTP-only mode.
    """
    try:
        return run_measurements_playwright(url, headless=headless)
    except Exception:
        # Fallback: HTTP-only approximation
        return run_measurements_http(url)


# ---------- Streamlit UI ----------

st.set_page_config(
    page_title="Web CO₂ – First vs Return Visit",
    page_icon="🌱",
    layout="centered",
)

st.title("🌱 Nani Summit Creative Website CO₂ Estimator")
st.caption("Compare first-visit vs. return-visit data transfer, CO₂, and a strict letter grade.")

default_url = "https://example.com"
url = st.text_input("Page URL to measure", value=default_url, placeholder="https://your-site.com")

col_left, col_right = st.columns([1, 1])
with col_left:
    headless = st.checkbox("Run browser headless (recommended when supported)", value=True)
with col_right:
    st.write("")  # spacing

run_button = st.button("Run measurement")

if run_button:
    if not url.strip():
        st.error("Please enter a URL first.")
    else:
        with st.spinner("Measuring requests and estimating CO₂… this may take a bit."):
            try:
                results = run_measurements(url, headless=headless)
            except Exception as e:
                st.error(f"Something went wrong while measuring: {e}")
                st.stop()

        st.success("Measurement complete ✅")

        fv = results["first_visit"]
        rv = results["return_visit"]
        mode = results["model"].get("mode", "playwright")

        # Exact CO₂ values
        fv_co2_exact = fv["co2_g"]
        rv_co2_exact = rv["co2_g"]

        # Round to 2 decimal places for both display and grading
        fv_co2_rounded = round(fv_co2_exact, 2)
        rv_co2_rounded = round(rv_co2_exact, 2)

        # Formatting helpers
        def fmt_mb(x): return f"{x:.2f}"
        def fmt_gb(x): return f"{x:.4f}"
        def fmt_kwh(x): return f"{x:.6f}"

        # Letter grades based on rounded values
        fv_grade = grade_from_co2(fv_co2_rounded)
        rv_grade = grade_from_co2(rv_co2_rounded)

        if mode == "http-only":
            st.warning(
                "Running in HTTP-only mode (no full browser available on this host). "
                "JavaScript-heavy pages and caching behavior are approximated from headers."
            )

        st.subheader("Overview")

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**First visit (cold cache)**")
            st.metric("Letter grade", fv_grade)
            st.metric("Data (MB)", fmt_mb(fv["mb"]))
            st.metric("Data (GB)", fmt_gb(fv["gb"]))
            st.metric("Energy (kWh)", fmt_kwh(fv["energy_kwh"]))
            st.metric("CO₂ (g)", f"{fv_co2_rounded:.2f}")
        with col2:
            st.markdown("**Return visit (warm cache, approx.)**")
            st.metric("Letter grade", rv_grade)
            st.metric("Data (MB)", fmt_mb(rv["mb"]))
            st.metric("Data (GB)", fmt_gb(rv["gb"]))
            st.metric("Energy (kWh)", fmt_kwh(rv["energy_kwh"]))
            st.metric("CO₂ (g)", f"{rv_co2_rounded:.2f}")

        st.divider()

        st.subheader("What the grades mean")

        st.markdown(
            f"**First visit grade: {fv_grade}** – {grade_description(fv_grade)}  \n"
            f"**Return visit grade: {rv_grade}** – {grade_description(rv_grade)}"
        )

        st.info(
            "These grades are based on per-page-view CO₂ in grams using a stricter scale. "
            "You can tweak the thresholds in the code to match your own standards."
        )

        st.divider()

        st.subheader("Raw numbers")

        st.write("All units are approximate and based on average grid intensity and energy-per-GB factors.")

        table_data = [
            {
                "Visit type": "First visit",
                "Grade": fv_grade,
                "Bytes": fv["bytes"],
                "MB": float(fmt_mb(fv["mb"])),
                "GB": float(fmt_gb(fv["gb"])),
                "Energy (kWh)": float(fmt_kwh(fv["energy_kwh"])),
                "CO₂ (g)": float(f"{fv_co2_rounded:.2f}"),
            },
            {
                "Visit type": "Return visit",
                "Grade": rv_grade,
                "Bytes": rv["bytes"],
                "MB": float(fmt_mb(rv["mb"])),
                "GB": float(fmt_gb(rv["gb"])),
                "Energy (kWh)": float(fmt_kwh(rv["energy_kwh"])),
                "CO₂ (g)": float(f"{rv_co2_rounded:.2f}"),
            },
        ]

        st.table(table_data)

        st.divider()
        st.subheader("JSON output (for your logs / reports)")
        st.json(results)

        st.caption(
            "Note: Return-visit bytes should usually be lower if browser caching and/or service workers are working well. "
            "In HTTP-only mode, this is approximated from cache headers."
        )
else:
    st.info("Enter a URL and click **Run measurement** to get started.")


# ---------- Nani Summit Creative footer ----------

st.markdown("---")
st.markdown(
    """
**About Nani Summit Creative**

We build lower-carbon, high-performing websites for outdoor brands and purpose-driven
organizations. The goal is simple: faster sites that tread lighter on the planet,
without sacrificing good design or real-world results.

If you’re curious how your site stacks up — or want to make your next build a little
greener — this tool is one of the nerdy ways we like to start that conversation. Learn more at: <a href "https:nanisummitcreative.com"> Nani Summit Creative</a>.
"""
)