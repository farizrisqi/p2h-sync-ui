import json
import os
import subprocess
import sys
from pathlib import Path

import streamlit as st
from dotenv import dotenv_values, set_key

SCRIPT_DIR = Path(__file__).resolve().parent
ENV_FILE = SCRIPT_DIR / ".env"
FAILURE_SCREENSHOT = SCRIPT_DIR / "downloads" / "failure.png"


def load_creds() -> dict:
    # Env vars dari Streamlit Cloud secrets lebih prioritas dari .env lokal
    vals = dotenv_values(ENV_FILE)
    return {
        "nrp": os.environ.get("PPA_NRP") or vals.get("PPA_NRP", ""),
        "password": os.environ.get("PPA_PASSWORD") or vals.get("PPA_PASSWORD", ""),
        "creds_json": os.environ.get("GOOGLE_CREDS_JSON") or vals.get("GOOGLE_CREDS_JSON", ""),
    }


def creds_from_env() -> bool:
    return all([
        os.environ.get("PPA_NRP"),
        os.environ.get("PPA_PASSWORD"),
        os.environ.get("GOOGLE_CREDS_JSON"),
    ])


def save_creds(nrp: str, password: str, creds_json: str) -> None:
    ENV_FILE.touch(exist_ok=True)
    set_key(str(ENV_FILE), "PPA_NRP", nrp)
    set_key(str(ENV_FILE), "PPA_PASSWORD", password)
    try:
        minified = json.dumps(json.loads(creds_json))
    except Exception:
        minified = creds_json
    set_key(str(ENV_FILE), "GOOGLE_CREDS_JSON", minified)


def is_configured(creds: dict) -> bool:
    return all([creds["nrp"], creds["password"], creds["creds_json"]])


def run_etl_subprocess() -> subprocess.Popen:
    # Gabung os.environ (sudah ada Streamlit Cloud secrets) + .env lokal sebagai fallback
    env = {**os.environ}
    for k, v in dotenv_values(ENV_FILE).items():
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


# ─── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Sync P2H",
    page_icon="🔄",
    layout="centered",
)

st.title("🔄 Sync Data P2H ke Google Sheets")
st.caption("Ambil data **NEED APPROVE P2H** dari ppa-dmp.net lalu perbarui Google Sheets secara manual.")

# ─── Sidebar: Pengaturan ───────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Pengaturan Akun")

    if creds_from_env():
        st.success("✅ Credentials dikonfigurasi via Streamlit Cloud Secrets")
        st.caption("Untuk mengubah, buka **Settings → Secrets** di dashboard Streamlit Cloud.")
    else:
        creds = load_creds()

        nrp_val = st.text_input("NRP (login ppa-dmp.net)", value=creds["nrp"], placeholder="Contoh: 123456")
        pw_val = st.text_input("Password ppa-dmp.net", value=creds["password"], type="password")

        try:
            json_display = json.dumps(json.loads(creds["creds_json"]), indent=2) if creds["creds_json"] else ""
        except Exception:
            json_display = creds["creds_json"]

        json_val = st.text_area(
            "Google Service Account JSON",
            value=json_display,
            height=200,
            placeholder="Paste isi file credentials.json di sini...",
            help="File JSON dari Google Cloud Console → IAM & Admin → Service Accounts → Keys.",
        )

        if st.button("💾 Simpan Pengaturan", use_container_width=True):
            if not all([nrp_val, pw_val, json_val]):
                st.error("Semua field wajib diisi.")
            else:
                try:
                    json.loads(json_val)
                    save_creds(nrp_val, pw_val, json_val)
                    st.success("✅ Pengaturan berhasil disimpan.")
                    st.rerun()
                except json.JSONDecodeError:
                    st.error("Format JSON tidak valid. Pastikan paste seluruh isi file credentials.json.")

        st.divider()
        if is_configured(load_creds()):
            st.success("✅ Akun sudah dikonfigurasi")
        else:
            st.warning("⚠️ Belum dikonfigurasi — isi form di atas")

# ─── Main: Jalankan ETL ────────────────────────────────────────────────────────
creds = load_creds()

if not is_configured(creds):
    st.info("👈 Isi pengaturan akun di **sidebar kiri** terlebih dahulu, lalu klik **Simpan Pengaturan**.")
    st.stop()

st.subheader("Jalankan Sync Manual")
st.write(
    "Klik tombol di bawah untuk mengambil data terbaru dari ppa-dmp.net "
    "dan memperbaruinya di Google Sheets."
)

if "etl_running" not in st.session_state:
    st.session_state["etl_running"] = False

run_btn = st.button(
    "🚀  Jalankan Sekarang",
    type="primary",
    use_container_width=True,
    disabled=st.session_state["etl_running"],
)

if run_btn:
    st.session_state["etl_running"] = True
    log_box = st.empty()
    result_box = st.empty()

    with st.spinner("Sedang berjalan... harap tunggu."):
        proc = run_etl_subprocess()
        logs: list = []

        for raw_line in proc.stdout:
            line = raw_line.rstrip()
            if line:
                logs.append(line)
                log_box.code("\n".join(logs), language="text")

        proc.wait()

    st.session_state["etl_running"] = False

    if proc.returncode == 0:
        result_box.success("✅ Sync berhasil! Data sudah diperbarui di Google Sheets.")
    else:
        result_box.error("❌ Terjadi kesalahan. Lihat log di bawah.")
        if FAILURE_SCREENSHOT.exists():
            st.image(str(FAILURE_SCREENSHOT), caption="Screenshot browser saat error", use_container_width=True)

    with st.expander("📋 Log Detail", expanded=(proc.returncode != 0)):
        st.code("\n".join(logs) if logs else "(tidak ada output)", language="text")
