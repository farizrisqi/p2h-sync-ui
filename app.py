import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import streamlit as st

SCRIPT_DIR = Path(__file__).resolve().parent
FAILURE_SCREENSHOT = SCRIPT_DIR / "downloads" / "failure.png"
WIB = timezone(timedelta(hours=7))

BULAN = ["", "Januari", "Februari", "Maret", "April", "Mei", "Juni",
         "Juli", "Agustus", "September", "Oktober", "November", "Desember"]


def format_last_sync(raw: str | None) -> tuple[str, str]:
    """Kembalikan (label_utama, label_relatif) dalam bahasa manusia."""
    if not raw:
        return "Belum pernah dijalankan", ""
    try:
        dt_utc = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        dt_wib = dt_utc.astimezone(WIB)
        now_wib = datetime.now(WIB)

        jam = dt_wib.strftime("%H:%M")
        tgl = dt_wib.day
        bln = BULAN[dt_wib.month]
        thn = dt_wib.year

        delta = now_wib - dt_wib
        total_menit = int(delta.total_seconds() // 60)

        if total_menit < 1:
            relatif = "baru saja"
        elif total_menit < 60:
            relatif = f"{total_menit} menit yang lalu"
        elif total_menit < 1440:
            jam_lalu = total_menit // 60
            relatif = f"{jam_lalu} jam yang lalu"
        else:
            hari_lalu = total_menit // 1440
            relatif = f"{hari_lalu} hari yang lalu"

        if dt_wib.date() == now_wib.date():
            label = f"Hari ini, {jam} WIB"
        else:
            label = f"{tgl} {bln} {thn}, {jam} WIB"

        return label, relatif
    except Exception:
        return raw, ""


# ── Install Playwright Chromium sekali per server start ───────────────────────
@st.cache_resource(show_spinner=False)
def ensure_browser() -> bool:
    result = subprocess.run(
        [sys.executable, "-m", "playwright", "install", "chromium"],
        capture_output=True, text=True,
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

st.markdown("""
<style>
  /* Gradient header */
  .hero {
    background: linear-gradient(120deg, #4f46e5, #6366f1 55%, #7c3aed);
    border-radius: 16px;
    padding: 32px 28px 28px;
    color: white;
    margin-bottom: 24px;
  }
  .hero h1 { margin: 0 0 6px; font-size: 24px; font-weight: 700; }
  .hero .sub { font-size: 14px; opacity: 0.85; margin: 0; }

  /* Status card */
  .sync-card {
    background: #f0fdf4;
    border: 1.5px solid #bbf7d0;
    border-radius: 12px;
    padding: 16px 20px;
    margin-bottom: 20px;
    display: flex;
    align-items: center;
    gap: 12px;
  }
  .sync-card.warn {
    background: #fffbeb;
    border-color: #fde68a;
  }
  .sync-card .icon { font-size: 24px; }
  .sync-card .main { font-size: 15px; font-weight: 600; color: #166534; }
  .sync-card.warn .main { color: #92400e; }
  .sync-card .rel { font-size: 13px; color: #6b7280; margin-top: 2px; }

  /* Run button override */
  div[data-testid="stButton"] > button[kind="primary"] {
    background: linear-gradient(90deg, #4f46e5, #7c3aed) !important;
    border: none !important;
    border-radius: 12px !important;
    font-size: 16px !important;
    font-weight: 700 !important;
    padding: 14px !important;
    letter-spacing: 0.3px !important;
    box-shadow: 0 4px 14px rgba(79,70,229,0.35) !important;
    transition: opacity 0.2s !important;
  }
  div[data-testid="stButton"] > button[kind="primary"]:hover {
    opacity: 0.88 !important;
  }
  div[data-testid="stButton"] > button[kind="primary"]:disabled {
    opacity: 0.5 !important;
  }
</style>
""", unsafe_allow_html=True)

# ── Install browser ────────────────────────────────────────────────────────────
with st.spinner("🔧 Menyiapkan browser..."):
    browser_ok = ensure_browser()

if not browser_ok:
    st.error("Gagal menyiapkan browser. Hubungi pengelola aplikasi.")
    st.stop()

# ── Hero header ────────────────────────────────────────────────────────────────
st.markdown("""
<div class="hero">
  <h1>🔄 Sync Data P2H</h1>
  <p class="sub">Ambil data <b>NEED APPROVE P2H</b> dari ppa-dmp.net dan perbarui Google Sheets secara manual.</p>
</div>
""", unsafe_allow_html=True)

# ── Status last sync ───────────────────────────────────────────────────────────
raw_sync = get_last_sync()
label, relatif = format_last_sync(raw_sync)

if raw_sync:
    rel_html = f'<div class="rel">⏱ {relatif}</div>' if relatif else ""
    st.markdown(f"""
    <div class="sync-card">
      <div class="icon">✅</div>
      <div>
        <div class="main">Terakhir diperbarui: {label}</div>
        {rel_html}
      </div>
    </div>
    """, unsafe_allow_html=True)
else:
    st.markdown("""
    <div class="sync-card warn">
      <div class="icon">⚠️</div>
      <div>
        <div class="main">Data belum pernah disinkronkan</div>
        <div class="rel">Klik tombol di bawah untuk mulai.</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

# ── Tombol jalankan ────────────────────────────────────────────────────────────
if "etl_running" not in st.session_state:
    st.session_state["etl_running"] = False

label_btn = "⏳  Sedang berjalan..." if st.session_state["etl_running"] else "🚀  Jalankan Sekarang"
run_btn = st.button(label_btn, type="primary", use_container_width=True,
                    disabled=st.session_state["etl_running"])

if run_btn:
    st.session_state["etl_running"] = True
    log_placeholder = st.empty()
    result_placeholder = st.empty()

    with st.spinner("Sedang mengambil data dan mengirim ke Google Sheets..."):
        proc = run_etl_subprocess()
        logs: list[str] = []

        for raw_line in proc.stdout:
            line = raw_line.rstrip()
            if line:
                logs.append(line)
                log_placeholder.code("\n".join(logs), language="text")

        proc.wait()

    st.session_state["etl_running"] = False
    get_last_sync.clear()

    if proc.returncode == 0:
        result_placeholder.success("✅ Berhasil! Data sudah diperbarui di Google Sheets.")
        st.rerun()
    else:
        result_placeholder.error("❌ Terjadi kesalahan saat mengambil data.")
        if FAILURE_SCREENSHOT.exists():
            st.image(str(FAILURE_SCREENSHOT), caption="Tampilan browser saat terjadi error",
                     use_container_width=True)

    with st.expander("📋 Lihat Log Lengkap", expanded=(proc.returncode != 0)):
        st.code("\n".join(logs) if logs else "(tidak ada output)", language="text")
