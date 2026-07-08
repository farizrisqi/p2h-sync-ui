import subprocess
import sys
from pathlib import Path

import streamlit as st

SCRIPT_DIR = Path(__file__).resolve().parent
FAILURE_SCREENSHOT = SCRIPT_DIR / "downloads" / "failure.png"


# ── Pastikan Playwright Chromium terinstall (sekali per server start) ──────────
@st.cache_resource(show_spinner=False)
def ensure_browser() -> bool:
    result = subprocess.run(
        [sys.executable, "-m", "playwright", "install", "chromium"],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


# ── Baca last sync dari Google Sheets (cache 60 detik) ────────────────────────
@st.cache_data(ttl=60, show_spinner=False)
def get_last_sync() -> str | None:
    try:
        from sheets_sync import read_last_sync
        return read_last_sync()
    except Exception:
        return None


def invalidate_last_sync():
    get_last_sync.clear()


def run_etl_subprocess() -> subprocess.Popen:
    import os
    from dotenv import dotenv_values

    env = {**os.environ}
    for k, v in dotenv_values(SCRIPT_DIR / ".env").items():
        if k not in env:
            env[k] = v
    env["PLAYWRIGHT_HEADLESS"] = "true"
    env["PYTHONUNBUFFERED"] = "1"

    return subprocess.Popen(
        [sys.executable, str(SCRIPT_DIR / "pipeline.py")],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=env,
        cwd=str(SCRIPT_DIR),
    )


# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(page_title="Sync P2H", page_icon="🔄", layout="centered")

# ── Install browser (background, tidak blokir UI) ─────────────────────────────
with st.spinner("Menyiapkan browser..."):
    browser_ok = ensure_browser()

if not browser_ok:
    st.error("Gagal menyiapkan browser Playwright. Cek log deploy Streamlit Cloud.")
    st.stop()

# ── Header ─────────────────────────────────────────────────────────────────────
st.title("🔄 Sync Data P2H")
st.caption("Ambil data **NEED APPROVE P2H** dari ppa-dmp.net dan perbarui Google Sheets.")

last_sync = get_last_sync()
if last_sync:
    st.info(f"🕐 Terakhir sync: **{last_sync}** UTC")
else:
    st.warning("⚠️ Belum pernah disinkron atau tidak dapat membaca status.")

st.divider()

# ── Tombol Jalankan ────────────────────────────────────────────────────────────
if "etl_running" not in st.session_state:
    st.session_state["etl_running"] = False

st.subheader("Jalankan Sync Manual")
st.write("Klik tombol di bawah untuk mengambil data terbaru dan memperbaruinya di Google Sheets.")

run_btn = st.button(
    "🚀  Jalankan Sekarang",
    type="primary",
    use_container_width=True,
    disabled=st.session_state["etl_running"],
)

if run_btn:
    st.session_state["etl_running"] = True
    log_placeholder = st.empty()
    result_placeholder = st.empty()

    with st.spinner("Sedang berjalan... harap tunggu."):
        proc = run_etl_subprocess()
        logs: list[str] = []

        for raw_line in proc.stdout:
            line = raw_line.rstrip()
            if line:
                logs.append(line)
                log_placeholder.code("\n".join(logs), language="text")

        proc.wait()

    st.session_state["etl_running"] = False
    invalidate_last_sync()

    if proc.returncode == 0:
        result_placeholder.success("✅ Sync berhasil! Data sudah diperbarui di Google Sheets.")
        st.rerun()
    else:
        result_placeholder.error("❌ Terjadi kesalahan. Lihat log di bawah.")
        if FAILURE_SCREENSHOT.exists():
            st.image(
                str(FAILURE_SCREENSHOT),
                caption="Screenshot browser saat error",
                use_container_width=True,
            )

    with st.expander("📋 Log Detail", expanded=(proc.returncode != 0)):
        st.code("\n".join(logs) if logs else "(tidak ada output)", language="text")
