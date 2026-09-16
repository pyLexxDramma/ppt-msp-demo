"""Нативная Streamlit-форма (Mode1 → .mpp). Fallback для Streamlit Cloud."""

from __future__ import annotations

from demo.catalog import load_form_options
from demo.form_input import (
    MONTHS_RU,
    WEEKS_COUNT,
    FormState,
    WeekRow,
    compute_aggregates,
    form_ready_for_recalc,
    period_label,
)
from demo.form_pipeline import SAMPLE_MPP, run_form_pipeline, silent_prefill_from_csv

import streamlit as st

PAGE_TITLE = "Данные по объему стройплощадок"


def _fmt(n: float | None, digits: int = 0) -> str:
    if n is None:
        return "—"
    return f"{n:,.{digits}f}".replace(",", " ").replace(".", ",")


def _signed(n: float | None) -> str:
    if n is None:
        return "—"
    prefix = "+" if n > 0 else ""
    return f"{prefix}{_fmt(n)}"


def _status_badge(status: str) -> str:
    if status == "over":
        return '<span class="badge badge-over">Превышение ВОР</span>'
    if status == "done":
        return '<span class="badge badge-done">Завершено</span>'
    return '<span class="badge badge-progress">В работе</span>'


def _parse_fact(raw: str) -> float | None:
    s = (raw or "").strip().replace(",", ".")
    if not s or s in {"—", "-"}:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _init_state(opts: dict) -> None:
    if "form_inited" in st.session_state:
        return
    pref = silent_prefill_from_csv(FormState())
    st.session_state["form_inited"] = True
    st.session_state["f_project_id"] = pref.project_id
    st.session_state["f_project"] = pref.project
    st.session_state["f_month"] = pref.period_month
    st.session_state["f_year"] = pref.period_year
    st.session_state["f_task_id"] = pref.task_id
    st.session_state["f_task_name"] = pref.task_name
    st.session_state["f_vor"] = float(pref.vor)
    st.session_state["f_unit"] = pref.unit
    st.session_state["f_prev_cum"] = float(pref.prev_cumulative)
    for i, w in enumerate(pref.weeks):
        st.session_state[f"plan_{i}"] = float(w.plan) if w.plan is not None else 0.0
        st.session_state[f"fact_{i}"] = "" if w.fact is None else str(w.fact).replace(".", ",")
    if not st.session_state["f_project_id"] and opts.get("projects"):
        st.session_state["f_project_id"] = opts["projects"][0]["id"]
        st.session_state["f_project"] = opts["projects"][0]["name"]


def _apply_task(task: dict, projects: list[dict]) -> None:
    st.session_state["f_task_id"] = task["id"]
    st.session_state["f_task_name"] = task["name"]
    st.session_state["f_unit"] = task.get("unit") or st.session_state.get("f_unit") or "шт"
    if float(task.get("vor") or 0) > 0:
        st.session_state["f_vor"] = float(task["vor"])
    pid = task.get("project_id") or ""
    if pid:
        st.session_state["f_project_id"] = pid
        for p in projects:
            if p["id"] == pid:
                st.session_state["f_project"] = p["name"]
                break


def _read_form() -> FormState:
    weeks: list[WeekRow] = []
    for i in range(WEEKS_COUNT):
        plan = float(st.session_state.get(f"plan_{i}", 0) or 0)
        fact = _parse_fact(str(st.session_state.get(f"fact_{i}", "")))
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


def _inject_css() -> None:
    st.markdown(
        """
<style>
  :root {
    --navy: #0A1A2F; --blue: #00529B; --red: #EF5350;
    --ink-soft: #5B6473; --ink-faint: #8A93A3;
    --surface: #FFFFFF; --surface-soft: #F9FBFD; --line: #E4E7EB;
    --zone-blue-bg: #EAF1F8; --zone-blue-border: #B9D6F1;
    --zone-amber-bg: #FFF4E5; --zone-amber-border: #F3D9AC;
    --zone-green-bg: #EAF7F0; --zone-green-border: #B7E1C7;
  }
  .block-container { padding-top: 1rem; max-width: 1080px; }
  .brand-row { display:flex; align-items:center; justify-content:space-between; gap:12px; margin-bottom:8px; }
  .brand-mark {
    width:34px; height:34px; border-radius:9px; background:var(--blue); color:#fff;
    display:inline-flex; align-items:center; justify-content:center; font-weight:800; margin-right:8px;
  }
  .brand-word { font-weight:800; font-size:16px; color:var(--navy); }
  .pill {
    display:inline-flex; background:#E3EDF7; color:var(--blue);
    font-weight:600; font-size:11.5px; padding:7px 14px; border-radius:999px;
  }
  .hero-title { font-size:26px; font-weight:800; color:var(--navy); margin:0 0 4px; }
  .hero-sub { font-size:12.5px; color:var(--ink-faint); margin:0 0 8px; }
  .hero-underline { width:40px; height:3px; background:var(--blue); border-radius:2px; margin-bottom:14px; }
  .section-title { font-size:14.5px; font-weight:700; color:var(--navy); margin:0 0 2px; }
  .section-sub { font-size:11.5px; color:var(--ink-faint); margin:0 0 10px; }
  .field-caption { font-size:11px; color:var(--ink-faint); margin:2px 0 8px; }
  .zone { border-radius:9px; padding:10px 12px 12px; margin-bottom:10px; border:1px solid; }
  .zone-blue { background:var(--zone-blue-bg); border-color:var(--zone-blue-border); }
  .zone-green { background:var(--zone-green-bg); border-color:var(--zone-green-border); }
  .zone-amber { background:var(--zone-amber-bg); border-color:var(--zone-amber-border); }
  .zone-head { display:flex; justify-content:space-between; align-items:center;
    font-size:13px; font-weight:700; color:var(--navy); margin-bottom:8px; }
  .zone-badge {
    background:var(--surface); border:1px solid var(--line); color:var(--blue);
    font-family:ui-monospace,monospace; font-weight:700; font-size:12px;
    padding:2px 8px; border-radius:999px;
  }
  .zone-note { font-size:11px; color:var(--ink-faint); margin-top:6px; }
  .result-head { display:flex; justify-content:space-between; gap:12px; align-items:flex-start; margin-bottom:10px; }
  .result-head-title { font-size:13px; font-weight:700; color:var(--navy); }
  .result-head-sub { font-size:12px; color:var(--ink-faint); margin-top:2px; }
  .result-hl { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:10px; margin:10px 0 12px; }
  .result-hl-label { font-size:10.5px; font-weight:700; letter-spacing:.03em; text-transform:uppercase; color:var(--ink-faint); }
  .result-hl-value { font-family:ui-monospace,monospace; font-size:15px; font-weight:700; color:var(--navy); }
  .result-line { display:flex; justify-content:space-between; gap:12px; font-size:13px;
    padding:7px 0; border-bottom:1px solid var(--line); }
  .result-k { color:var(--ink-soft); }
  .result-v { font-weight:700; color:var(--navy); font-family:ui-monospace,monospace; }
  .result-change {
    margin:10px 0; padding:8px 10px; border-radius:8px; border:1px dashed var(--line);
    background:var(--surface-soft); font-size:12px; color:var(--ink-soft);
  }
  .result-mpp-note { color:var(--red); font-size:12.5px; }
  .badge { display:inline-block; font-size:11px; font-weight:700; padding:3px 9px; border-radius:999px; }
  .badge-progress { background:var(--zone-amber-bg); color:#9A6B0C; }
  .badge-done { background:var(--zone-green-bg); color:#1D8A5E; }
  .badge-over { background:#FDECEC; color:var(--red); }
  .period-pill {
    display:inline-block; background:var(--surface-soft); border:1px solid var(--line);
    color:var(--ink-soft); font-size:11.5px; font-weight:600; padding:6px 12px; border-radius:999px;
  }
</style>
""",
        unsafe_allow_html=True,
    )


def render(*, cloud_note: str | None = None) -> None:
    """Рисует форму. page_config должен быть вызван снаружи."""
    _inject_css()
    opts = load_form_options()
    projects = opts.get("projects") or []
    tasks = opts.get("tasks") or []
    units = opts.get("units") or ["шт"]
    years = opts.get("years") or list(range(2024, 2030))
    _init_state(opts)

    if cloud_note:
        st.info(cloud_note)

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

    with st.expander("Что меняется в файле MS Project (.mpp) и как считаются показатели", expanded=False):
        st.markdown(
            "- После пересчёта обновляется **одна задача** (Ид из формы) в sample-графике.\n"
            "- Mode1: последняя неделя с фактом > 0 → `остаток / факт × 7` → ceil → окончание.\n"
            "- **today** = последний день месяца отчёта.\n"
            "- Отклонение: **факт − план**; недели без факта в накопитель не входят."
        )

    project_ids = [p["id"] for p in projects] or [st.session_state["f_project_id"]]
    project_labels = {p["id"]: p["name"] for p in projects}
    if st.session_state["f_project_id"] not in project_ids and project_ids:
        st.session_state["f_project_id"] = project_ids[0]
        st.session_state["f_project"] = project_labels.get(project_ids[0], "")

    c1, c2, c3, c4 = st.columns([2, 2, 1.2, 1])
    with c1:
        pid = st.selectbox(
            "Объект / ЖК",
            options=project_ids,
            format_func=lambda i: project_labels.get(i, i),
            key="f_project_id",
        )
        st.session_state["f_project"] = project_labels.get(pid, st.session_state.get("f_project", ""))
    with c2:
        st.text_input("ID проекта", value=st.session_state["f_project_id"], disabled=True)
    with c3:
        st.selectbox(
            "Месяц отчёта",
            options=list(range(12)),
            format_func=lambda i: MONTHS_RU[i],
            key="f_month",
        )
    with c4:
        year_opts = list(years)
        if st.session_state["f_year"] not in year_opts:
            year_opts = sorted({*year_opts, int(st.session_state["f_year"])})
        st.selectbox("Год", options=year_opts, key="f_year")

    st.selectbox(
        "Режим расчёта прогноза",
        options=["last"],
        format_func=lambda _: "По факту последней недели (Mode1)",
        disabled=True,
        key="f_mode_display",
    )
    st.markdown(
        '<p class="field-caption">остальные режимы — следующий этап</p>',
        unsafe_allow_html=True,
    )

    st.markdown(
        '<p class="section-title">Задача</p>'
        '<p class="section-sub">из графика MPP / БД — ID подставляются автоматически</p>',
        unsafe_allow_html=True,
    )
    task_ids = [t["id"] for t in tasks] or [st.session_state["f_task_id"]]
    task_by_id = {t["id"]: t for t in tasks}
    if st.session_state["f_task_id"] not in task_ids and task_ids:
        st.session_state["f_task_id"] = task_ids[0]
        _apply_task(task_by_id[task_ids[0]], projects)

    t1, t2, t3, t4 = st.columns(4)
    with t1:

        def _on_task_change() -> None:
            chosen = st.session_state.get("f_task_id")
            if chosen in task_by_id:
                _apply_task(task_by_id[chosen], projects)

        st.selectbox(
            "Наименование работ",
            options=task_ids,
            format_func=lambda i: task_by_id.get(i, {}).get("name", i),
            key="f_task_id",
            on_change=_on_task_change,
        )
    with t2:
        st.text_input("Ид задачи (MSP)", value=st.session_state["f_task_id"], disabled=True)
    with t3:
        st.number_input("ВОР", min_value=0.0, step=1.0, key="f_vor", disabled=True)
    with t4:
        unit_opts = list(units)
        if st.session_state["f_unit"] not in unit_opts:
            unit_opts = [*unit_opts, st.session_state["f_unit"]]
        st.selectbox("Ед. измерения", options=unit_opts, key="f_unit")

    form = _read_form()
    agg = compute_aggregates(form)

    head_l, head_r = st.columns([3, 1])
    with head_l:
        st.markdown(
            '<p class="section-title">Ввод по неделям</p>'
            '<p class="section-sub">План и факт — отклонение и накопительно считаются автоматически</p>',
            unsafe_allow_html=True,
        )
    with head_r:
        st.markdown(
            f'<div style="text-align:right;margin-top:8px"><span class="period-pill">{period_label(form)}</span></div>',
            unsafe_allow_html=True,
        )

    st.markdown(
        f'<div class="zone zone-blue"><div class="zone-head"><span>План</span>'
        f'<span class="zone-badge">{_fmt(agg.plan_total)}</span></div></div>',
        unsafe_allow_html=True,
    )
    for i, col in enumerate(st.columns(WEEKS_COUNT)):
        with col:
            st.number_input(f"{i + 1} нед.", min_value=0.0, step=1.0, key=f"plan_{i}")

    st.markdown(
        f'<div class="zone zone-green"><div class="zone-head"><span>Факт</span>'
        f'<span class="zone-badge">{_fmt(agg.fact_total)}</span></div></div>',
        unsafe_allow_html=True,
    )
    for i, col in enumerate(st.columns(WEEKS_COUNT)):
        with col:
            st.text_input(f"{i + 1} нед.", key=f"fact_{i}", placeholder="—")

    form = _read_form()
    agg = compute_aggregates(form)

    st.markdown(
        f'<div class="zone zone-amber"><div class="zone-head"><span>Отклонение и накопительно</span>'
        f'<span class="zone-badge">{_signed(agg.month_cum)}</span></div></div>',
        unsafe_allow_html=True,
    )
    st.caption("Отклонение (факт − план)")
    for i, col in enumerate(st.columns(WEEKS_COUNT)):
        row = agg.rows[i] if i < len(agg.rows) else None
        with col:
            st.metric(f"{i + 1} нед.", _signed(row.dev if row else None))
    st.caption("Накопительно")
    for i, col in enumerate(st.columns(WEEKS_COUNT)):
        row = agg.rows[i] if i < len(agg.rows) else None
        with col:
            st.metric(f"{i + 1} нед.", _signed(row.cum if row else None))

    st.markdown(
        '<p class="section-title">Факт накопленный с начала</p>'
        '<p class="section-sub">п. 4.1.1 ТЗ</p>',
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
    act1, act2 = st.columns([2, 1])
    with act1:
        run = st.button("Сохранить и пересчитать", type="primary", use_container_width=True)
    with act2:
        pipe_prev = st.session_state.get("pipe_result")
        if pipe_prev is not None and pipe_prev.mpp_bytes:
            st.download_button(
                "Скачать .mpp",
                data=pipe_prev.mpp_bytes,
                file_name="msp_updated.mpp",
                mime="application/vnd.ms-project",
                use_container_width=True,
            )

    if run:
        if not ready:
            st.toast("Исправьте поля: нужен ВОР > 0 и хотя бы один факт > 0", icon="⚠️")
        else:
            with st.spinner("Пересчёт…"):
                pipe = run_form_pipeline(form, write_csv_xml=False)
            st.session_state["pipe_result"] = pipe
            if pipe.mpp_bytes:
                st.toast("Пересчёт завершён. Можно скачать .mpp", icon="✅")
            else:
                st.toast(
                    pipe.mpp_error
                    or "Пересчёт завершён. Файл .mpp недоступен на этой машине расчёта.",
                    icon="⚠️",
                )

    pipe = st.session_state.get("pipe_result")
    if pipe is None:
        return

    m1 = pipe.schedule.get("mode1") or {}
    start = pipe.schedule.get("start") or "—"
    finish = pipe.schedule.get("finish") or "—"
    before = pipe.update.before or {}
    before_start = before.get("Начало") or "—"
    before_finish = before.get("Окончание") or "—"
    rem = pipe.schedule.get("remaining_days_ceil")
    fw = m1.get("forecast_weeks")

    st.markdown(
        f'<div class="result-head"><div>'
        f'<div class="result-head-title">Результат пересчёта (Mode1)</div>'
        f'<div class="result-head-sub">{form.task_name} · {period_label(form)}</div>'
        f"</div>{_status_badge(pipe.status)}</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div class="result-hl">'
        f'<div><div class="result-hl-label">Начало → Окончание</div>'
        f'<div class="result-hl-value">{start} → {finish}</div></div>'
        f'<div><div class="result-hl-label">Осталось дней</div>'
        f'<div class="result-hl-value">{rem if rem is not None else "—"}</div></div>'
        f'<div><div class="result-hl-label">Факт периода</div>'
        f'<div class="result-hl-value">нед. {m1.get("last_week") or "—"} · {_fmt(m1.get("fact_period"), 1)}</div></div>'
        f"</div>",
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
        f'<div class="result-line"><span class="result-k">Прогноз недель</span>'
        f'<span class="result-v">{("≈ " + _fmt(fw, 1)) if fw is not None else "—"}</span></div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div class="result-line"><span class="result-k">today (конец месяца отчёта)</span>'
        f'<span class="result-v">{pipe.today}</span></div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div class="result-change">Обновлена задача Id {pipe.update.task_id}'
        f" · Начало {before_start} → {start}"
        f" · Окончание {before_finish} → {finish}</div>",
        unsafe_allow_html=True,
    )
    if pipe.mpp_bytes:
        st.download_button(
            "Скачать .mpp",
            data=pipe.mpp_bytes,
            file_name="msp_updated.mpp",
            mime="application/vnd.ms-project",
        )
    else:
        st.markdown(
            '<p class="result-mpp-note">Расчёт готов. Файл .mpp недоступен на этой машине '
            "(нужны MS Project и pywin32).</p>",
            unsafe_allow_html=True,
        )
    _ = SAMPLE_MPP
