"""
Streamlit demo: загрузка PPT + CSV/XML → расчёт → просмотр графика в браузере → скачивание CSV/XML (+MPP).

  streamlit run demo_app.py --server.port 8503
"""

from __future__ import annotations

import io
import sys
import zipfile
from datetime import date
from pathlib import Path

import pandas as pd
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
from demo.field_map import mapping_table_markdown  # noqa: E402
from demo.mpp_writer import (  # noqa: E402
    apply_updates_to_mpp,
    project_available,
    verify_mpp_links,
)
from demo.parse_pptx import parse_stroyka_pptx  # noqa: E402
from demo.schedule_view import (  # noqa: E402
    apply_updates_to_schedule_df,
    csv_rows_to_schedule_df,
    parse_mspdi_xml_to_df,
    render_compare_gantt,
    render_schedule_gantt,
    render_schedule_table,
)
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


def _render_xml_browser_viewer(xml_bytes: bytes, label: str = "XML") -> None:
    try:
        df = parse_mspdi_xml_to_df(xml_bytes)
    except ValueError as e:
        st.error(str(e))
        return
    c1, c2, c3 = st.columns(3)
    c1.metric(f"Задач в {label}", len(df))
    with_dates = int(df["_start"].notna().sum()) if "_start" in df.columns else 0
    c2.metric("С датами", with_dates)
    c3.metric("Со связями", int((df["Предшественники"].astype(str).str.len() > 0).sum()) if "Предшественники" in df.columns else 0)

    q = st.text_input("Фильтр по названию / Id", key=f"xml_filter_{label}", placeholder="например: фундамент или 6")
    view = df
    if q.strip():
        qq = q.strip().lower()
        view = df[
            df["Ид"].astype(str).str.contains(qq, case=False, na=False)
            | df["Название"].astype(str).str.lower().str.contains(qq, na=False)
        ]
    max_bars = st.slider("Макс. полос на Ганте", 10, 80, 40, key=f"xml_bars_{label}")
    render_schedule_gantt(view, title=f"Гант из {label} (упрощённо в браузере)", max_bars=max_bars)
    render_schedule_table(view, title=f"Таблица из {label}")


def main():
    st.title("Автоматизация графика СМР: PPT → MS Project")
    st.caption(
        "Расчёт сроков по PPT + просмотр графика в браузере (CSV/XML). "
        "Полный MS Project здесь не эмулируется — для него скачайте XML."
    )

    st.markdown(
        '<div class="flow-note">'
        "<b>Поток:</b> 1) PPT + CSV (XML опционально) → 2) «Рассчитать» → "
        "3) смотрите таблицу/Гант/дифф в браузере → "
        "4) скачайте <code>msp_updated.xml</code> → File → Open в MS Project."
        "</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="yellow-note">'
        "<b>Жёлтые колонки</b> (обновляем): "
        "ВОР, ВОР_факт, ВОР_остаток, Ед_изм, Начало, Окончание, "
        "%_выполнения_ВОР, Осталось_дней_прогноз, Заметки. "
        "<b>Не трогаем:</b> база, предшественники/последователи, % завершения MSP. "
        "<b>На Cloud нет .mpp</b> — только CSV/XML."
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
            "**В браузере:** таблица + Гант по CSV/XML.\n\n"
            "**В Project:** скачайте XML → Файл → Открыть.\n\n"
            "**MPP** — только Windows + Project + `pywin32` (не Cloud)."
        )
        mpp_ok = project_available()
        st.write("MS Project COM:", "✅ доступен" if mpp_ok else "❌ нет")

    use_sample = source.startswith("Демо")

    tab_calc, tab_view = st.tabs(
        ["1. PPT → расчёт → скачать", "2. Просмотр CSV / XML в браузере"]
    )

    with tab_calc:
        st.subheader("Загрузка входных файлов")
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
                    "Экспорт Project XML (.xml) — патч дат по ID + превью",
                    type=["xml"],
                    key="up_xml",
                )
                if up_xml:
                    xml_bytes_in, xml_name = up_xml.getvalue(), up_xml.name

        if mpp_ok:
            with st.expander("Дополнительно: исходный .mpp (вариант A, только локально)"):
                if use_sample:
                    mpp_bytes, mpp_name = _load_sample_mpp()
                    if mpp_bytes:
                        st.caption(f"sample: `{mpp_name}`")
                else:
                    up_mpp = st.file_uploader("Файл .mpp", type=["mpp"], key="up_mpp")
                    if up_mpp:
                        mpp_bytes, mpp_name = up_mpp.getvalue(), up_mpp.name

        ready = bool(pptx_bytes) and bool(csv_bytes)
        if not ready:
            st.warning("Нужны как минимум **PPTX** и **CSV** графика. XML — опционально.")
        else:
            if st.button("Рассчитать и подготовить файлы", type="primary", use_container_width=True):
                with st.spinner("Парсинг PPT → сопоставление с графиком → CSV/XML…"):
                    reports = parse_stroyka_pptx(pptx_bytes, filename=pptx_name or "upload.pptx")
                    fieldnames, rows = load_msp_csv(csv_bytes)
                    updates = match_and_build_updates(reports, rows, today=today)
                    csv_out = apply_updates_to_csv(fieldnames, rows, updates)
                    xml_out = rows_to_mspdi_xml(rows, updates, project_name="msp_updated")
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
                    st.session_state["fieldnames"] = fieldnames
                    st.session_state["mpp_bytes"] = mpp_bytes
                    st.session_state["mpp_out"] = None
                    st.session_state["pptx_name"] = pptx_name
                    st.session_state["csv_name"] = csv_name

        if xml_bytes_in and "updates" not in st.session_state:
            with st.expander("Превью загруженного XML (до расчёта)", expanded=False):
                _render_xml_browser_viewer(xml_bytes_in, label="входной XML")

        if "updates" not in st.session_state:
            st.info("Загрузите PPTX+CSV и нажмите «Рассчитать», либо откройте вкладку просмотра CSV/XML.")
        else:
            reports = st.session_state["reports"]
            updates = st.session_state["updates"]
            csv_out = st.session_state["csv_out"]
            xml_out = st.session_state["xml_out"]
            xml_patched = st.session_state.get("xml_patched")
            rows = st.session_state.get("rows") or []

            st.markdown("---")
            st.subheader("Результат расчёта")

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

            st.markdown("**Дифф обновляемых полей**")
            st.dataframe(
                pd.DataFrame(updates_to_diff_table(updates)),
                use_container_width=True,
                hide_index=True,
            )

            with st.expander("Детали Mode1"):
                for u in updates:
                    if not u.task_id:
                        st.warning(f"Не сопоставлено: {u.ppt_title}")
                        continue
                    st.markdown(f"**Id {u.task_id}** — {u.name}")
                    st.write(u.schedule)
                    st.caption(" · ".join(u.notes))

            st.subheader("Сравнение сроков (Гант до / после)")
            g1, g2 = st.columns(2)
            with g1:
                show_before = st.checkbox("Показать «до»", value=True, key="gantt_before")
            with g2:
                show_after = st.checkbox("Показать «после PPT»", value=True, key="gantt_after")
            render_compare_gantt(updates, show_before=show_before, show_after=show_after)

            st.subheader("График целиком в браузере (после обновления)")
            base_df = csv_rows_to_schedule_df(rows)
            after_df = apply_updates_to_schedule_df(base_df, updates)
            changed_ids = {str(u.task_id) for u in matched}
            only_chg = st.checkbox("Только изменённые задачи", value=False, key="only_changed")
            show_df = after_df
            if only_chg and changed_ids:
                show_df = after_df[after_df["Ид"].astype(str).isin(changed_ids)]
            max_bars = st.slider("Макс. полос на Ганте графика", 10, 80, 35, key="full_gantt_bars")
            render_schedule_gantt(
                show_df,
                title="Обновлённый график (CSV → веб)",
                max_bars=max_bars,
                highlight_ids=changed_ids,
            )
            render_schedule_table(show_df, title="Таблица обновлённого графика")

            st.markdown("**Превью выходного XML** (то, что откроете в Project)")
            with st.expander("Гант / таблица из msp_updated.xml", expanded=False):
                _render_xml_browser_viewer(xml_out, label="msp_updated.xml")

            st.markdown("---")
            st.subheader("Скачать файлы для MS Project")
            st.success(
                "Рекомендуется: **msp_updated.xml** → в MS Project: Файл → Открыть → "
                "«Создать новый проект»."
            )
            with st.expander("Карта имён CSV ↔ MPP (1:1)"):
                st.markdown(
                    "В выгрузке CSV заголовки = канонические имена формы. "
                    "В Project переименуйте Текст13/14/15/16 и Число1/2 так же."
                )
                st.markdown(mapping_table_markdown())

            d1, d2, d3 = st.columns(3)
            with d1:
                st.download_button(
                    "⬇️ msp_updated.csv",
                    data=csv_out,
                    file_name="msp_updated.csv",
                    mime="text/csv",
                    use_container_width=True,
                    help="Windows-1251, `;` — запасной обмен",
                )
            with d2:
                st.download_button(
                    "⬇️ msp_updated.xml",
                    data=xml_out,
                    file_name="msp_updated.xml",
                    mime="application/xml",
                    use_container_width=True,
                    help="MSPDI XML → File → Open в Project",
                )
            with d3:
                if xml_patched:
                    st.download_button(
                        "⬇️ msp_patched.xml",
                        data=xml_patched,
                        file_name="msp_patched.xml",
                        mime="application/xml",
                        use_container_width=True,
                        help="Ваш XML с пропатченными Start/Finish",
                    )
                else:
                    st.caption("Загрузите исходный .xml — появится патч-файл")

            zip_bytes = _zip_outputs(csv_out, xml_out)
            st.download_button(
                "⬇️ Всё пакетом (CSV + XML).zip",
                data=zip_bytes,
                file_name="msp_updated_pack.zip",
                mime="application/zip",
                use_container_width=True,
            )

            st.markdown("---")
            st.subheader("Приёмка (XCA)")
            matched_ids = [u.task_id for u in updates if u.task_id]
            st.markdown(
                """
| Цель | Как проверить |
|------|----------------|
| Перенос в ячейки | Дифф и таблица выше: ВОР / даты / прогноз |
| Пересчёт хвоста СМР | В Project: сдвиг Id6 тянет последователей |
| Связи не слетели | Предшественники/Последователи до = после |
| База | Базовое начало/окончание не меняются |
"""
            )
            st.caption(
                "Веб-Гант — упрощённый просмотр. Полный каскад и календарь — только в MS Project по XML."
            )

            if mpp_ok and st.session_state.get("mpp_bytes"):
                st.markdown("**Вариант A — правка исходного .mpp (COM, локально)**")
                preserve = st.checkbox(
                    "Не трогать % завершения и факт. даты (рекомендуется)",
                    value=True,
                    key="mpp_preserve",
                )
                b1, b2 = st.columns(2)
                with b1:
                    if st.button("Сформировать .mpp через Project COM", use_container_width=True):
                        try:
                            with st.spinner("MS Project COM…"):
                                src = st.session_state["mpp_bytes"]
                                mpp_out = apply_updates_to_mpp(
                                    src,
                                    updates,
                                    preserve_progress=preserve,
                                    write_dates=True,
                                    recalculate=True,
                                )
                                st.session_state["mpp_out"] = mpp_out
                                st.session_state["mpp_link_check"] = verify_mpp_links(
                                    src, mpp_out, matched_ids
                                )
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
                if st.session_state.get("mpp_link_check"):
                    st.markdown("**Проверка связей после COM**")
                    st.dataframe(
                        pd.DataFrame(st.session_state["mpp_link_check"]),
                        use_container_width=True,
                        hide_index=True,
                    )

    with tab_view:
        st.subheader("Просмотр графика без MS Project")
        st.caption(
            "Загрузите экспорт CSV или XML из Project — увидите таблицу и упрощённый Гант в браузере. "
            "Это не замена Project (календарь/ресурсы/каскад считаются там)."
        )
        v1, v2 = st.columns(2)
        with v1:
            view_csv = st.file_uploader("CSV графика", type=["csv"], key="view_csv")
        with v2:
            view_xml = st.file_uploader("XML графика (MSPDI)", type=["xml"], key="view_xml")

        if use_sample and not view_csv and not view_xml:
            st.info("Демо: можно нажать кнопку ниже или загрузить свой файл.")
            if st.button("Показать демо-CSV Ленинский", key="btn_demo_view"):
                st.session_state["force_demo_csv_view"] = True

        if st.session_state.get("force_demo_csv_view") and not view_csv:
            view_csv_bytes = _load_sample_csv()[0]
            fieldnames, rows = load_msp_csv(view_csv_bytes)
            df = csv_rows_to_schedule_df(rows)
            st.success(f"Демо CSV: {len(df)} задач")
            q = st.text_input("Фильтр", key="demo_csv_filter")
            if q.strip():
                qq = q.strip().lower()
                df = df[
                    df["Ид"].astype(str).str.contains(qq, case=False, na=False)
                    | df["Название"].astype(str).str.lower().str.contains(qq, na=False)
                ]
            render_schedule_gantt(df, title="Демо-график из CSV", max_bars=40)
            render_schedule_table(df, title="Таблица демо-CSV")

        if view_csv is not None:
            try:
                fieldnames, rows = load_msp_csv(view_csv.getvalue())
                df = csv_rows_to_schedule_df(rows)
                st.success(f"CSV: {len(df)} задач (`{view_csv.name}`)")
                q = st.text_input("Фильтр CSV", key="user_csv_filter")
                if q.strip():
                    qq = q.strip().lower()
                    df = df[
                        df["Ид"].astype(str).str.contains(qq, case=False, na=False)
                        | df["Название"].astype(str).str.lower().str.contains(qq, na=False)
                    ]
                bars = st.slider("Макс. полос (CSV)", 10, 80, 40, key="view_csv_bars")
                render_schedule_gantt(df, title="Гант из CSV", max_bars=bars)
                render_schedule_table(df, title="Таблица из CSV")
            except Exception as e:
                st.error(f"Ошибка чтения CSV: {e}")

        if view_xml is not None:
            st.markdown("---")
            _render_xml_browser_viewer(view_xml.getvalue(), label=view_xml.name or "XML")

        if st.session_state.get("xml_out"):
            st.markdown("---")
            st.markdown("**Результат последнего расчёта** уже в сессии — можно скачать XML на вкладке расчёта.")
            st.download_button(
                "⬇️ msp_updated.xml (из сессии)",
                data=st.session_state["xml_out"],
                file_name="msp_updated.xml",
                mime="application/xml",
                key="dl_xml_from_view_tab",
            )


if __name__ == "__main__":
    main()
