import os
import subprocess
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

# === НАСТРОЙКИ ===
RULES_OPTIONS = {
    "Sales": "rules.json",
    "HR": "hr_rules.json",
    "Inventory": "inventory_rules.json"
}
UPLOADS_DIR = Path("uploads")

st.set_page_config(
    page_title="Data Quality Profiler",
    page_icon="📊",
    layout="wide"
)

st.title("📊 Data Quality Profiler")
st.markdown("---")

selected_domain = st.selectbox(
    "Выберите домен для проверки",
    options=list(RULES_OPTIONS.keys())
)
RULES_PATH = RULES_OPTIONS[selected_domain]

if "data_path" not in st.session_state:
    st.session_state.data_path = ""
if "report_path" not in st.session_state:
    st.session_state.report_path = ""
if "report_status" not in st.session_state:
    st.session_state.report_status = {
        "ready": False,
        "returncode": None,
        "stdout": "",
        "stderr": ""
    }
if "run_requested" not in st.session_state:
    st.session_state.run_requested = False

with st.form("upload_and_run"):
    data_file = st.file_uploader(
        "Загрузите CSV-файл с данными",
        type=["csv"],
        help="Файл должен содержать данные для проверки качества"
    )
    submit = st.form_submit_button("🚀 Запустить проверку")

    if data_file:
        st.success(f"✅ Файл загружен: {data_file.name} ({data_file.size} байт)")

    if submit:
        if not data_file:
            st.warning("Сначала загрузите CSV-файл.")
        else:
            UPLOADS_DIR.mkdir(exist_ok=True)
            data_path = UPLOADS_DIR / data_file.name
            with open(data_path, "wb") as f:
                f.write(data_file.getbuffer())

            report_path = Path.cwd() / f"{data_path.stem}_report.md"
            st.session_state.data_path = str(data_path)
            st.session_state.report_path = str(report_path)
            st.session_state.report_status = {
                "ready": False,
                "returncode": None,
                "stdout": "",
                "stderr": ""
            }
            st.session_state.run_requested = True

if st.session_state.data_path and st.session_state.run_requested:
    data_path = Path(st.session_state.data_path)
    with st.spinner("Запускаем профайлер..."):
        result = subprocess.run(
            [
                sys.executable,
                "profile_investor.py",
                st.session_state.data_path,
                RULES_PATH,
                "--output",
                st.session_state.report_path,
            ],
            capture_output=True,
            text=True,
        )

    st.session_state.report_status = {
        "ready": result.returncode == 0 and Path(st.session_state.report_path).exists(),
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }
    st.session_state.run_requested = False

if st.session_state.data_path:
    data_path = Path(st.session_state.data_path)
    st.markdown("### Загруженный файл")
    st.write(data_path.name)

    if st.session_state.report_status["returncode"] is None:
        st.info("Нажмите кнопку запуска, чтобы сформировать отчёт профайлера.")
    elif st.session_state.report_status["returncode"] != 0:
        st.error("❌ Ошибка выполнения профайлера:")
        st.text(st.session_state.report_status["stderr"])
        st.text(st.session_state.report_status["stdout"])
    elif st.session_state.report_status["ready"]:
        report_path = Path(st.session_state.report_path)
        report_text = report_path.read_text(encoding="utf-8")

        st.markdown("## Отчёт профайлера")
        st.markdown(report_text)

        st.download_button(
            label="📥 Скачать отчёт",
            data=report_text,
            file_name=report_path.name,
            mime="text/markdown",
        )

        if data_path.exists():
            st.markdown("---")
            st.subheader("📊 Исходные данные")
            csv_bytes = data_path.read_bytes()
            st.download_button(
                label="📥 Скачать CSV",
                data=csv_bytes,
                file_name=data_path.name,
                mime="text/csv",
            )

        st.markdown("---")
        st.subheader("📧 Отправить отчёт на почту")
        st.caption("Функция отправки на почту пока в разработке.")
        email_to = st.text_input("Введите email получателя", key="email_to")
        if st.button("📧 Отправить", key="send_email"):
            if email_to:
                st.info(f"📌 Функция отправки на почту в разработке. Отчёт для {email_to} будет отправлен позже.")
            else:
                st.warning("Введите email")
    else:
        st.warning("Отчёт не создан. Проверьте вывод ниже.")
        st.text(st.session_state.report_status["stdout"])
else:
    st.info("👆 Загрузите CSV-файл и нажмите кнопку запуска, чтобы начать проверку.")