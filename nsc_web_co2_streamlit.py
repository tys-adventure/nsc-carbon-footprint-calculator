#!/usr/bin/env python3

import streamlit as st
from contextlib import contextmanager
from playwright.sync_api import sync_playwright

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
    Return a letter grade (A–F) based on CO₂ per page view in grams.
    You can tweak these thresholds to match your philosophy.
    """
    if co2_g <= 0.5:
        return "A"
    elif co2_g <= 1.0:
        return "B"
    elif co2_g <= 1.5:
        return "C"
    elif co2_g <= 2.0:
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


@contextmanager
def launch_browser(headless: bool = True):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        try:
            yield browser
        finally:
            browser.close()


def measure_visit(context, url: str, wait_until: str = "networkidle", timeout: int = 60000):
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


def run_measurements(url: str, headless: bool = True):
    """
    Run two visits to `url` in the same browser context:
    - First visit (cold cache)
    - Second visit (warm cache)

    Returns a dict with bytes & CO2 estimates for each.
    """
    with launch_browser(headless=headless) as browser:
        context = browser.new_context()

        first_bytes = measure_visit(context, url)
        second_bytes = measure_visit(context, url)

        context.close()

    first_energy_kwh, first_co2_g = co2_for_bytes(first_bytes)
    second_energy_kwh, second_co2_g = co2_for_bytes(second_bytes)

    results = {
        "url": url,
        "model": {
            "kwh_per_gb": KWH_PER_GB,
            "grid_intensity_g_per_kwh": GRID_INTENSITY,
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


# ---------- Streamlit UI ----------

st.set_page_config(
    page_title="Web CO₂ – First vs Return Visit",
    page_icon="🌱",
    layout="centered",
)

st.title("🌱 Nani Summit Creative Website CO₂ Estimator")
st.caption("Compare first-visit vs. return-visit data transfer, CO₂, and a simple letter grade.")

default_url = "https://example.com"
url = st.text_input("Page URL to measure", value=default_url, placeholder="https://your-site.com")

col_left, col_right = st.columns([1, 1])
with col_left:
    headless = st.checkbox("Run browser headless (recommended)", value=True)
with col_right:
    st.write("")  # spacing

run_button = st.button("Run measurement")

if run_button:
    if not url.strip():
        st.error("Please enter a URL first.")
    else:
        with st.spinner("Launching headless browser and measuring requests… this may take a bit."):
            try:
                results = run_measurements(url, headless=headless)
            except Exception as e:
                st.error(f"Something went wrong while measuring: {e}")
                st.stop()

        st.success("Measurement complete ✅")

        fv = results["first_visit"]
        rv = results["return_visit"]

        # Formatting helpers
        def fmt_mb(x): return f"{x:.2f}"
        def fmt_gb(x): return f"{x:.4f}"
        def fmt_kwh(x): return f"{x:.6f}"
        def fmt_g(x): return f"{x:.1f}"

        # Letter grades
        fv_grade = grade_from_co2(fv["co2_g"])
        rv_grade = grade_from_co2(rv["co2_g"])

        st.subheader("Overview")

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**First visit (cold cache)**")
            st.metric("Letter grade", fv_grade)
            st.metric("Data (MB)", fmt_mb(fv["mb"]))
            st.metric("Data (GB)", fmt_gb(fv["gb"]))
            st.metric("Energy (kWh)", fmt_kwh(fv["energy_kwh"]))
            st.metric("CO₂ (g)", fmt_g(fv["co2_g"]))
        with col2:
            st.markdown("**Return visit (warm cache)**")
            st.metric("Letter grade", rv_grade)
            st.metric("Data (MB)", fmt_mb(rv["mb"]))
            st.metric("Data (GB)", fmt_gb(rv["gb"]))
            st.metric("Energy (kWh)", fmt_kwh(rv["energy_kwh"]))
            st.metric("CO₂ (g)", fmt_g(rv["co2_g"]))

        st.divider()

        st.subheader("What the grades mean")

        st.markdown(
            f"**First visit grade: {fv_grade}** – {grade_description(fv_grade)}  \n"
            f"**Return visit grade: {rv_grade}** – {grade_description(rv_grade)}"
        )

        st.info(
            "These grades are based on per-page-view CO₂ in grams using a simple, opinionated scale. "
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
                "CO₂ (g)": float(fmt_g(fv["co2_g"])),
            },
            {
                "Visit type": "Return visit",
                "Grade": rv_grade,
                "Bytes": rv["bytes"],
                "MB": float(fmt_mb(rv["mb"])),
                "GB": float(fmt_gb(rv["gb"])),
                "Energy (kWh)": float(fmt_kwh(rv["energy_kwh"])),
                "CO₂ (g)": float(fmt_g(rv["co2_g"])),
            },
        ]

        st.table(table_data)

        st.divider()
        st.subheader("JSON output (for your logs / reports)")
        st.json(results)

        st.caption(
            "Note: Return-visit bytes should usually be lower if browser caching and/or service workers are working well."
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
greener — this tool is one of the nerdy ways we like to start that conversation. Learn more at <a href"https://nanisummitcreative.com>Nani Summit Creative</a>
"""
)
