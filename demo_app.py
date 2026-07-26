"""
Streamlit demo: загрузка PPT + CSV/XML → расчёт → скачивание обновлённых CSV/XML (+MPP).

  streamlit run demo_app.py --server.port 8503
"""

from __future__ import annotations

import io
import sys
import zipfile
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from demo.build_update import (  # noqa: E402
    apply_updates_to_csv,
    load_msp_csv,
    match_and_build_updates,
    updates_to_diff_table,
)
from demo.mpp_writer import apply_updates_to_mpp, project_available  # noqa: E402
from demo.parse_pptx import parse_stroyka_pptx  # noqa: E402
from demo.xml_export import patch_mspdi_xml, rows_to_mspdi_xml  # noqa: E402

SAMPLE = ROOT / "sample_data"
PAGE_TITLE = "PPT → MSP — демо для XCA"

st.set_page_config(page_title=PAGE_TITLE, page_icon="📊", layout="wide")

st.markdown(
    """
<style>
  .block-container { padding-top: 1.2rem; max-width: 1200px; }
  div[data-testid="stMetricValue"] { font-size: 1.35rem; }
  .yellow-note {
    background: #fff8db; border-left: 4px solid #e6b800;
    padding: 0.75rem 1rem; border-radius: 4px; margin-bottom: 1rem;
  }
  .flow-note {
    background: #e8f0fe; border-left: 4px solid #1a73e8;
    padding: 0.75rem 1rem; border-radius: 4px; margin-bottom: 1rem;
  }
</style>
""",
    unsafe_allow_html=True,
)


def _load_sample_pptx() -> tuple[bytes, str]:
    p = SAMPLE / "stroyka_demo.pptx"
    return p.read_bytes(), p.name


def _load_sample_csv() -> tuple[bytes, str]:
    p = SAMPLE / "msp_demo.csv"
    return p.read_bytes(), p.name


def _load_sample_mpp() -> tuple[bytes, str] | tuple[None, None]:
    p = SAMPLE / "msp_demo.mpp"
    if p.exists():
        return p.read_bytes(), p.name
    return None, None


def _zip_outputs(csv_bytes: bytes, xml_bytes: bytes, mpp_bytes: bytes | None = None) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("msp_updated.csv", csv_bytes)
        zf.writestr("msp_updated.xml", xml_bytes)
        if mpp_bytes:
            zf.writestr("msp_updated.mpp", mpp_bytes)
    return buf.getvalue()


def render_gantt(
    updates,
    title: str = "Обновлённые задачи (демо-Гант)",
    show_before: bool = True,
    show_after: bool = True,
):
    if not show_before and not show_after:
        st.warning("Включите хотя бы один слой: «до» или «после PPT».")
        return

    rows = []
    for u in updates:
        if not u.task_id:
            continue
        label = f"{u.task_id}. {u.name[:50]}"
        if show_after:
            try:
                start = datetime.strptime(u.after["Начало"], "%d.%m.%y")
                finish = datetime.strptime(u.after["Окончание"], "%d.%m.%y")
                rows.append(
                    {
                        "Задача": label,
                        "Начало": start,
                        "Окончание": finish,
                        "Источник": "после PPT",
                    }
                )
            except Exception:
                pass
        if show_before:
            try:
                bs = datetime.strptime(u.before["Начало"], "%d.%m.%y")
                bf = datetime.strptime(u.before["Окончание"], "%d.%m.%y")
                rows.append(
                    {
                        "Задача": label,
                        "Начало": bs,
                        "Окончание": bf,
                        "Источник": "до",
                    }
                )
            except Exception:
                pass
    if not rows:
        st.info("Нет дат для Ганта")
        return
    df = pd.DataFrame(rows)
    fig = px.timeline(
        df,
        x_start="Начало",
        x_end="Окончание",
        y="Задача",
        color="Источник",
        title=title,
        color_discrete_map={"до": "#9aa0a6", "после PPT": "#1a73e8"},
        category_orders={"Источник": ["до", "после PPT"]},
    )
    fig.update_yaxes(autorange="reversed")
    fig.update_layout(
        height=max(280, 90 * max(1, len({u.task_id for u in updates if u.task_id}))),
        margin=dict(l=20, r=20, t=50, b=20),
        legend=dict(title="Слой", orientation="h", yanchor="bottom", y=1.02, x=0),
        # Legend click still works, but primary control is checkboxes above
    )
    st.plotly_chart(fig, use_container_width=True)


def main():
    st.title("Автоматизация графика СМР: PPT → MS Project")
    st.caption(
        "Загрузка файлов → расчёт сроков (Режим №1) → скачивание обновлённых CSV / XML "
        "(и MPP при наличии Project)."
    )

    st.markdown(
        '<div class="flow-note">'
        "<b>Поток:</b> 1) загрузить PPT + график (CSV и/или XML) → "
        "2) «Рассчитать» → 3) скачать <code>msp_updated.csv</code> / <code>msp_updated.xml</code> "
        "→ открыть в MS Project (File → Open)."
        "</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="yellow-note">'
        "<b>Жёлтые колонки</b>: Начало, Окончание, ВОР, Ед.изм, Заметки. "
        "<b>Не трогаем:</b> база, предшественники/последователи, % завершения MSP."
        "</div>",
        unsafe_allow_html=True,
    )

    with st.sidebar:
        st.header("Параметры")
        today = st.date_input("Дата «сегодня» (Режим №1)", value=date(2026, 7, 25))
        source = st.radio(
            "Источник данных",
            ["Загрузить свои файлы", "Демо-файлы Ленинский"],
            index=0,
        )
        st.markdown("---")
        st.markdown(
            "**CSV / XML** — всегда доступны для скачивания.\n\n"
            "**MPP** — только Windows + установленный Microsoft Project + `pywin32`."
        )
        mpp_ok = project_available()
        st.write("MS Project COM:", "✅ доступен" if mpp_ok else "❌ нет")

    use_sample = source.startswith("Демо")

    st.subheader("1. Загрузка входных файлов")
    c1, c2, c3 = st.columns(3)

    pptx_bytes = pptx_name = None
    csv_bytes = csv_name = None
    xml_bytes_in = xml_name = None
    mpp_bytes = mpp_name = None

    with c1:
        st.markdown("**PPT-отчёт (обязательно)**")
        if use_sample:
            pptx_bytes, pptx_name = _load_sample_pptx()
            st.success(f"sample: `{pptx_name}`")
        else:
            up = st.file_uploader("Файл .pptx", type=["pptx"], key="up_pptx")
            if up:
                pptx_bytes, pptx_name = up.getvalue(), up.name

    with c2:
        st.markdown("**График CSV**")
        if use_sample:
            csv_bytes, csv_name = _load_sample_csv()
            st.success(f"sample: `{csv_name}`")
        else:
            up_csv = st.file_uploader(
                "Экспорт из Project (.csv, cp1251, `;`)",
                type=["csv"],
                key="up_csv",
            )
            if up_csv:
                csv_bytes, csv_name = up_csv.getvalue(), up_csv.name

    with c3:
        st.markdown("**График XML (опционально)**")
        if use_sample:
            st.caption("XML соберём из CSV после расчёта")
        else:
            up_xml = st.file_uploader(
                "Экспорт Project XML (.xml) — патч дат по ID",
                type=["xml"],
                key="up_xml",
            )
            if up_xml:
                xml_bytes_in, xml_name = up_xml.getvalue(), up_xml.name

    if mpp_ok:
        with st.expander("Дополнительно: исходный .mpp (вариант A)"):
            if use_sample:
                mpp_bytes, mpp_name = _load_sample_mpp()
                if mpp_bytes:
                    st.caption(f"sample: `{mpp_name}`")
            else:
                up_mpp = st.file_uploader("Файл .mpp", type=["mpp"], key="up_mpp")
                if up_mpp:
                    mpp_bytes, mpp_name = up_mpp.getvalue(), up_mpp.name

    # Need PPT + (CSV or XML). If only XML — we still need task list; require CSV for matching.
    ready = bool(pptx_bytes) and bool(csv_bytes)
    if not ready:
        st.warning("Нужны как минимум **PPTX** и **CSV** графика. XML — опционально для патча.")
        if not use_sample:
            st.stop()

    if st.button("Рассчитать и подготовить файлы", type="primary", use_container_width=True):
        with st.spinner("Парсинг PPT → сопоставление с графиком → CSV/XML…"):
            reports = parse_stroyka_pptx(pptx_bytes, filename=pptx_name or "upload.pptx")
            fieldnames, rows = load_msp_csv(csv_bytes)
            updates = match_and_build_updates(reports, rows, today=today)
            csv_out = apply_updates_to_csv(fieldnames, rows, updates)
            # Always build fresh MSPDI from updated rows
            xml_out = rows_to_mspdi_xml(rows, updates, project_name="msp_updated")
            # If user uploaded XML — also produce patched copy
            xml_patched = None
            if xml_bytes_in:
                xml_patched = patch_mspdi_xml(xml_bytes_in, updates)

            st.session_state["reports"] = reports
            st.session_state["updates"] = updates
            st.session_state["csv_out"] = csv_out
            st.session_state["xml_out"] = xml_out
            st.session_state["xml_patched"] = xml_patched
            st.session_state["xml_name_in"] = xml_name
            st.session_state["rows"] = rows
            st.session_state["mpp_bytes"] = mpp_bytes
            st.session_state["mpp_out"] = None
            st.session_state["pptx_name"] = pptx_name
            st.session_state["csv_name"] = csv_name

    if "updates" not in st.session_state:
        st.info("Загрузите файлы и нажмите «Рассчитать и подготовить файлы».")
        st.stop()

    reports = st.session_state["reports"]
    updates = st.session_state["updates"]
    csv_out = st.session_state["csv_out"]
    xml_out = st.session_state["xml_out"]
    xml_patched = st.session_state.get("xml_patched")

    st.markdown("---")
    st.subheader("2. Результат расчёта")

    ppt_rows = []
    for r in reports:
        ppt_rows.append(
            {
                "Слайд": r.slide_index,
                "Работа": r.title[:70],
                "Всего": r.total,
                "Выполнено": r.done,
                "Остаток": r.rest,
                "Ед.": r.unit,
                "%": f"{r.pct:.1f}%" if r.pct is not None else "",
                "Факт по неделям": r.weeks_fact,
            }
        )
    st.markdown("**Из PPT**")
    st.dataframe(pd.DataFrame(ppt_rows), use_container_width=True, hide_index=True)

    matched = [u for u in updates if u.task_id]
    m1, m2, m3 = st.columns(3)
    m1.metric("Работ в PPT", len(reports))
    m2.metric("Сопоставлено с MSP", len(matched))
    m3.metric(
        "Прогноз дн (Mode1)",
        sum(int(u.schedule.get("remaining_days_ceil") or 0) for u in matched),
    )

    st.markdown("**Дифф жёлтых колонок**")
    st.dataframe(pd.DataFrame(updates_to_diff_table(updates)), use_container_width=True, hide_index=True)

    with st.expander("Детали Mode1"):
        for u in updates:
            if not u.task_id:
                st.warning(f"Не сопоставлено: {u.ppt_title}")
                continue
            st.markdown(f"**Id {u.task_id}** — {u.name}")
            st.write(u.schedule)
            st.caption(" · ".join(u.notes))

    st.subheader("Отображение сроков (Гант)")
    g1, g2 = st.columns(2)
    with g1:
        show_before = st.checkbox("Показать «до» (исходный график)", value=True, key="gantt_before")
    with g2:
        show_after = st.checkbox("Показать «после PPT»", value=True, key="gantt_after")
    render_gantt(updates, show_before=show_before, show_after=show_after)

    st.markdown("---")
    st.subheader("3. Скачать изменённые файлы")

    d1, d2, d3 = st.columns(3)
    with d1:
        st.download_button(
            "⬇️ msp_updated.csv",
            data=csv_out,
            file_name="msp_updated.csv",
            mime="text/csv",
            use_container_width=True,
            help="Windows-1251, `;` → File → Open в Project",
        )
    with d2:
        st.download_button(
            "⬇️ msp_updated.xml",
            data=xml_out,
            file_name="msp_updated.xml",
            mime="application/xml",
            use_container_width=True,
            help="MSPDI XML из обновлённого графика → File → Open в Project",
        )
    with d3:
        if xml_patched:
            st.download_button(
                "⬇️ msp_patched.xml",
                data=xml_patched,
                file_name="msp_patched.xml",
                mime="application/xml",
                use_container_width=True,
                help="Ваш загруженный XML с пропатченными Start/Finish",
            )
        else:
            st.caption("Загрузите исходный .xml — появится патч-файл")

    # ZIP
    zip_bytes = _zip_outputs(csv_out, xml_out)
    st.download_button(
        "⬇️ Всё пакетом (CSV + XML).zip",
        data=zip_bytes,
        file_name="msp_updated_pack.zip",
        mime="application/zip",
        use_container_width=True,
    )

    if mpp_ok and st.session_state.get("mpp_bytes"):
        st.markdown("**Вариант A — бинарный MPP**")
        b1, b2 = st.columns(2)
        with b1:
            if st.button("Сформировать .mpp через Project COM", use_container_width=True):
                try:
                    with st.spinner("MS Project…"):
                        mpp_out = apply_updates_to_mpp(st.session_state["mpp_bytes"], updates)
                    st.session_state["mpp_out"] = mpp_out
                    st.success("MPP готов")
                except Exception as e:
                    st.error(f"Ошибка MPP: {e}")
        with b2:
            if st.session_state.get("mpp_out"):
                st.download_button(
                    "⬇️ msp_updated.mpp",
                    data=st.session_state["mpp_out"],
                    file_name="msp_updated.mpp",
                    mime="application/vnd.ms-project",
                    use_container_width=True,
                )
                st.download_button(
                    "⬇️ ZIP (CSV+XML+MPP)",
                    data=_zip_outputs(csv_out, xml_out, st.session_state["mpp_out"]),
                    file_name="msp_updated_full.zip",
                    mime="application/zip",
                    use_container_width=True,
                )


if __name__ == "__main__":
    main()
