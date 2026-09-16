"""
Streamlit demo: форма ввода объёмов → Mode1 → обновление sample .mpp (COM на Windows).

  streamlit run demo_app.py --server.port 8503
"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from demo.form_input import (  # noqa: E402
    MONTHS_RU,
    WEEKS_COUNT,
    FormState,
    WeekRow,
    compute_aggregates,
    form_ready_for_recalc,
    period_label,
)
from demo.form_pipeline import (  # noqa: E402
    SAMPLE_MPP,
    silent_prefill_from_csv,
    run_form_pipeline,
)
from demo.mpp_writer import project_available  # noqa: E402

PAGE_TITLE = "Данные по объему стройплощадок"

st.set_page_config(page_title=PAGE_TITLE, page_icon="Λ", layout="wide")

st.markdown(
    """
<style>
  :root {
    --navy: #0A1A2F;
    --blue: #00529B;
    --blue-deep: #003D75;
    --blue-soft-bg: #E3EDF7;
    --green: #10B981;
    --red: #EF5350;
    --ink: #101828;
    --ink-soft: #5B6473;
    --ink-faint: #8A93A3;
    --surface: #FFFFFF;
    --surface-soft: #F9FBFD;
    --page-bg: #EEF2F5;
    --line: #E4E7EB;
    --zone-blue-bg: #EAF1F8;
    --zone-blue-border: #B9D6F1;
    --zone-amber-bg: #FFF4E5;
    --zone-amber-border: #F3D9AC;
    --zone-green-bg: #EAF7F0;
    --zone-green-border: #B7E1C7;
  }
  .block-container { padding-top: 1rem; max-width: 1080px; }
  .brand-row { display:flex; align-items:center; justify-content:space-between; gap:12px; margin-bottom:8px; }
  .brand-mark {
    width:34px; height:34px; border-radius:9px; background:var(--blue); color:#fff;
    display:inline-flex; align-items:center; justify-content:center; font-weight:800; margin-right:8px;
  }
  .brand-word { font-weight:800; font-size:16px; color:var(--navy); }
  .pill {
    display:inline-flex; background:var(--blue-soft-bg); color:var(--blue);
    font-weight:600; font-size:11.5px; padding:7px 14px; border-radius:999px;
  }
  .hero-title { font-size:26px; font-weight:800; color:var(--navy); margin:0 0 4px; }
  .hero-sub { font-size:12.5px; color:var(--ink-faint); margin:0 0 8px; }
  .hero-underline { width:40px; height:3px; background:var(--blue); border-radius:2px; margin-bottom:16px; }
  .card {
    background:var(--surface); border:1px solid var(--line); border-radius:14px;
    padding:16px 18px; margin-bottom:14px;
  }
  .card-title { font-size:14.5px; font-weight:700; color:var(--navy); margin:0 0 2px; }
  .card-sub { font-size:11.5px; color:var(--ink-faint); margin:0 0 12px; }
  .zone {
    border-radius:9px; padding:12px 14px; margin-bottom:10px; border:1px solid;
  }
  .zone-blue { background:var(--zone-blue-bg); border-color:var(--zone-blue-border); }
  .zone-green { background:var(--zone-green-bg); border-color:var(--zone-green-border); }
  .zone-amber { background:var(--zone-amber-bg); border-color:var(--zone-amber-border); }
  .zone-head { font-size:13px; font-weight:700; color:var(--navy); margin-bottom:8px; }
  .zone-note { font-size:11px; color:var(--ink-faint); margin-top:6px; }
  .result-card {
    background:var(--surface); border:1px solid var(--line); border-radius:14px;
    padding:14px 18px; margin-top:12px;
  }
  .result-head { font-size:14px; font-weight:700; color:var(--navy); margin-bottom:10px; }
  .result-line { display:flex; justify-content:space-between; gap:12px; font-size:13px; margin:6px 0; }
  .result-k { color:var(--ink-soft); }
  .result-v { font-weight:700; color:var(--navy); font-family:ui-monospace,monospace; }
  .badge { display:inline-block; font-size:11px; font-weight:700; padding:3px 9px; border-radius:999px; }
  .badge-progress { background:var(--zone-amber-bg); color:#9A6B0C; }
  .badge-done { background:var(--zone-green-bg); color:#1D8A5E; }
  .badge-over { background:#FDECEC; color:var(--red); }
  .footnote { font-size:11px; color:var(--ink-faint); margin-top:14px; }
  div[data-testid="stMetricValue"] { font-size:1.2rem; }
</style>
""",
    unsafe_allow_html=True,
)


def _init_state() -> None:
    if "form_inited" in st.session_state:
        return
    pref = silent_prefill_from_csv(FormState())
    st.session_state["form_inited"] = True
    st.session_state["f_project"] = pref.project
    st.session_state["f_project_id"] = pref.project_id
    st.session_state["f_month"] = pref.period_month
    st.session_state["f_year"] = pref.period_year
    st.session_state["f_task_name"] = pref.task_name
    st.session_state["f_task_id"] = pref.task_id
    st.session_state["f_vor"] = float(pref.vor)
    st.session_state["f_unit"] = pref.unit
    st.session_state["f_prev_cum"] = float(pref.prev_cumulative)
    for i, w in enumerate(pref.weeks):
        st.session_state[f"plan_{i}"] = float(w.plan) if w.plan is not None else 0.0
        # Streamlit number_input не любит None — пустой факт = 0 с флагом «не задан» через checkbox сложно;
        # используем sentinel: храним факт как float, отдельный флаг «есть факт»
        has = w.fact is not None
        st.session_state[f"fact_has_{i}"] = has
        st.session_state[f"fact_{i}"] = float(w.fact) if has else 0.0


def _read_form() -> FormState:
    weeks: list[WeekRow] = []
    for i in range(WEEKS_COUNT):
        plan = float(st.session_state.get(f"plan_{i}", 0) or 0)
        has = bool(st.session_state.get(f"fact_has_{i}", False))
        fact = float(st.session_state.get(f"fact_{i}", 0) or 0) if has else None
        weeks.append(WeekRow(plan=plan, fact=fact))
    return FormState(
        project=str(st.session_state.get("f_project") or ""),
        project_id=str(st.session_state.get("f_project_id") or ""),
        period_month=int(st.session_state.get("f_month", 6)),
        period_year=int(st.session_state.get("f_year", 2026)),
        mode="last",
        task_name=str(st.session_state.get("f_task_name") or ""),
        task_id=str(st.session_state.get("f_task_id") or ""),
        vor=float(st.session_state.get("f_vor") or 0),
        unit=str(st.session_state.get("f_unit") or ""),
        prev_cumulative=float(st.session_state.get("f_prev_cum") or 0),
        weeks=weeks,
    )


def _fmt(n: float | None, digits: int = 0) -> str:
    if n is None:
        return "—"
    return f"{n:,.{digits}f}".replace(",", " ").replace(".", ",")


def _status_badge(status: str) -> str:
    if status == "over":
        return '<span class="badge badge-over">Превышение ВОР</span>'
    if status == "done":
        return '<span class="badge badge-done">Завершено</span>'
    return '<span class="badge badge-progress">В работе</span>'


def main() -> None:
    _init_state()

    st.markdown(
        '<div class="brand-row">'
        '<div><span class="brand-mark">Λ</span><span class="brand-word">CONALL</span></div>'
        '<span class="pill">AI.CONALL.RU · ВВОД ДАННЫХ</span>'
        "</div>",
        unsafe_allow_html=True,
    )
    st.markdown(f'<p class="hero-title">{PAGE_TITLE}</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="hero-sub">Роль: Инженер · ввод плана/факта по неделям для актуализации MS Project</p>'
        '<div class="hero-underline"></div>',
        unsafe_allow_html=True,
    )

    # ---- settings ----
    st.markdown(
        '<div class="card"><p class="card-title">Параметры отчёта</p>'
        '<p class="card-sub">Данные по выбранному периоду вносятся вручную</p></div>',
        unsafe_allow_html=True,
    )
    c1, c2, c3, c4 = st.columns([2, 2, 1.2, 1])
    with c1:
        st.text_input("Объект / ЖК", key="f_project")
    with c2:
        st.text_input("ID проекта", key="f_project_id")
    with c3:
        st.selectbox("Месяц отчёта", options=list(range(12)), format_func=lambda i: MONTHS_RU[i], key="f_month")
    with c4:
        st.number_input("Год", min_value=2020, max_value=2100, step=1, key="f_year")
    st.selectbox(
        "Режим расчёта прогноза",
        options=["last"],
        format_func=lambda _: "По факту последней недели",
        disabled=True,
        key="f_mode_display",
    )

    # ---- task ----
    st.markdown(
        '<div class="card"><p class="card-title">Задача</p>'
        '<p class="card-sub">В боевой версии придёт из MSP; в демо редактируется</p></div>',
        unsafe_allow_html=True,
    )
    t1, t2, t3, t4 = st.columns(4)
    with t1:
        st.text_input("Наименование работ", key="f_task_name")
    with t2:
        st.text_input("Ид задачи (MSP)", key="f_task_id")
    with t3:
        st.number_input("ВОР", min_value=0.0, step=1.0, key="f_vor")
    with t4:
        st.text_input("Ед. измерения", key="f_unit")

    form = _read_form()
    agg = compute_aggregates(form)

    # ---- weeks ----
    st.markdown(
        f'<div class="card"><p class="card-title">Ввод по неделям</p>'
        f'<p class="card-sub">Период: {period_label(form)} · отклонение и накопительно считаются автоматически</p></div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        f'<div class="zone zone-blue"><div class="zone-head">План · итог {_fmt(agg.plan_total)}</div></div>',
        unsafe_allow_html=True,
    )
    plan_cols = st.columns(WEEKS_COUNT)
    for i, col in enumerate(plan_cols):
        with col:
            st.number_input(f"{i + 1} нед.", min_value=0.0, step=1.0, key=f"plan_{i}")

    st.markdown(
        f'<div class="zone zone-green"><div class="zone-head">Факт · итог {_fmt(agg.fact_total)}</div></div>',
        unsafe_allow_html=True,
    )
    fact_cols = st.columns(WEEKS_COUNT)
    for i, col in enumerate(fact_cols):
        with col:
            st.checkbox(f"Есть факт {i + 1}", key=f"fact_has_{i}")
            st.number_input(
                f"Факт {i + 1}",
                min_value=0.0,
                step=1.0,
                key=f"fact_{i}",
                disabled=not st.session_state.get(f"fact_has_{i}", False),
            )

    # re-read after widgets (values already in session_state for next compute below)
    form = _read_form()
    agg = compute_aggregates(form)

    st.markdown(
        f'<div class="zone zone-amber"><div class="zone-head">'
        f"Отклонение и накопительно · {_fmt(agg.month_cum)}</div></div>",
        unsafe_allow_html=True,
    )
    st.caption("Отклонение = факт − план. Недели без факта в накопительный расчёт не попадают.")
    dcols = st.columns(WEEKS_COUNT)
    for i, col in enumerate(dcols):
        row = agg.rows[i] if i < len(agg.rows) else None
        with col:
            st.metric(f"Откл. {i + 1}", _fmt(row.dev if row else None))
    ccols = st.columns(WEEKS_COUNT)
    for i, col in enumerate(ccols):
        row = agg.rows[i] if i < len(agg.rows) else None
        with col:
            st.metric(f"Накоп. {i + 1}", _fmt(row.cum if row else None))

    # ---- cumulative ----
    st.markdown(
        '<div class="card"><p class="card-title">Факт накопленный с начала</p>'
        '<p class="card-sub">п. 4.1.1 ТЗ</p></div>',
        unsafe_allow_html=True,
    )
    s1, s2, s3 = st.columns(3)
    with s1:
        st.number_input("Накоплено до периода", min_value=0.0, step=1.0, key="f_prev_cum")
    form = _read_form()
    agg = compute_aggregates(form)
    with s2:
        st.metric("Факт накопленный с начала", f"{_fmt(agg.done)} {form.unit}")
    with s3:
        st.metric("Остаток до ВОР", f"{_fmt(agg.remaining)} {form.unit}")

    ready = form_ready_for_recalc(form)
    com_ok = project_available()
    st.caption(
        "Windows + MS Project + pywin32 — для скачивания .mpp. "
        f"COM сейчас: {'доступен' if com_ok else 'недоступен (на Mac ожидаемо)'}."
    )

    if st.button("Сохранить и пересчитать", type="primary", use_container_width=True, disabled=not ready):
        with st.spinner("Режим №1 и обновление графика…"):
            pipe = run_form_pipeline(form)
        st.session_state["pipe_result"] = pipe

    if not ready:
        st.info("Заполните ВОР > 0 и хотя бы одну неделю с фактом > 0 — кнопка станет активной.")

    pipe = st.session_state.get("pipe_result")
    if pipe is not None:
        m1 = pipe.schedule.get("mode1") or {}
        start = pipe.schedule.get("start") or "—"
        finish = pipe.schedule.get("finish") or "—"
        fw = m1.get("forecast_weeks")
        rem = pipe.schedule.get("remaining_days_ceil")
        st.markdown('<div class="result-card"><div class="result-head">Результат пересчёта (Mode1)</div>', unsafe_allow_html=True)
        st.markdown(
            f'<div class="result-line"><span class="result-k">Статус</span>'
            f'<span class="result-v">{_status_badge(pipe.status)}</span></div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<div class="result-line"><span class="result-k">Факт накопленный / ВОР</span>'
            f'<span class="result-v">{_fmt(pipe.aggregates.done)} / {_fmt(pipe.aggregates.vor)} {form.unit}</span></div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<div class="result-line"><span class="result-k">Остаток</span>'
            f'<span class="result-v">{_fmt(pipe.aggregates.remaining)} {form.unit}</span></div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<div class="result-line"><span class="result-k">Неделя / факт периода</span>'
            f'<span class="result-v">нед. {m1.get("last_week") or "—"} · {_fmt(m1.get("fact_period"), 1)}</span></div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<div class="result-line"><span class="result-k">Прогноз</span>'
            f'<span class="result-v">'
            f'{("≈ " + _fmt(fw, 1) + " нед.") if fw is not None else "не определён"} · '
            f'дней ceil={rem if rem is not None else "—"}</span></div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<div class="result-line"><span class="result-k">Начало / Окончание</span>'
            f'<span class="result-v">{start} → {finish}</span></div>',
            unsafe_allow_html=True,
        )
        st.caption(f"today={pipe.today} · {pipe.schedule.get('start_rule') or ''} · {pipe.schedule.get('finish_rule') or ''}")
        st.markdown("</div>", unsafe_allow_html=True)

        if pipe.mpp_error:
            st.warning(pipe.mpp_error)
        if pipe.mpp_bytes:
            st.download_button(
                "Скачать обновлённый .mpp",
                data=pipe.mpp_bytes,
                file_name="msp_updated.mpp",
                mime="application/vnd.ms-project",
                type="primary",
                use_container_width=True,
                help="Откройте файл в MS Project",
            )
            st.success("Скачайте обновлённый .mpp и откройте в MS Project.")
        d1, d2 = st.columns(2)
        with d1:
            if pipe.csv_bytes:
                st.download_button(
                    "Скачать msp_updated.csv",
                    data=pipe.csv_bytes,
                    file_name="msp_updated.csv",
                    mime="text/csv",
                    use_container_width=True,
                )
        with d2:
            if pipe.xml_bytes:
                st.download_button(
                    "Скачать msp_updated.xml",
                    data=pipe.xml_bytes,
                    file_name="msp_updated.xml",
                    mime="application/xml",
                    use_container_width=True,
                    help="На Mac: перенесите XML на Windows → Файл → Открыть в Project",
                )

        with st.expander("Отладка schedule (JSON)", expanded=False):
            st.json(pipe.schedule)

    st.markdown(
        f'<p class="footnote">Демо: sample график '
        f'<code>{SAMPLE_MPP.name}</code> (локально в sample_data/). '
        f"Запись .mpp — через COM на Windows. CSV подставляется скрыто только для префилла и доп. выгрузки.</p>",
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
