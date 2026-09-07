"""Веб-просмотр графика СМР из CSV-строк / MSPDI XML (упрощённо, без MS Project)."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import date, datetime
from typing import Any

import pandas as pd
import plotly.express as px
import streamlit as st

from .xml_export import _parse_date

YELLOW_COLS = [
    "ВОР",
    "ВОР_факт",
    "ВОР_остаток",
    "Ед_изм",
    "%_выполнения_ВОР",
    "Осталось_дней_прогноз",
    "Начало",
    "Окончание",
    "Заметки",
]


def _local(tag: str) -> str:
    return tag.split("}")[-1] if "}" in tag else tag


def _fmt_d(d: date | None) -> str:
    return d.strftime("%d.%m.%y") if d else ""


def _pred_links_to_str(task_el: ET.Element) -> str:
    type_map = {"0": "ОО", "1": "ОН", "2": "НО", "3": "НН"}
    parts: list[str] = []
    for child in list(task_el):
        if _local(child.tag) != "PredecessorLink":
            continue
        uid = typ = lag = None
        for c in list(child):
            ln = _local(c.tag)
            if ln == "PredecessorUID":
                uid = (c.text or "").strip()
            elif ln == "Type":
                typ = (c.text or "1").strip()
            elif ln == "LinkLag":
                try:
                    # tenths of minutes; 4800 = 1 day
                    lag = int(int(c.text or "0") / 4800)
                except ValueError:
                    lag = 0
        if not uid:
            continue
        tcode = type_map.get(typ or "1", "ОН")
        if lag:
            parts.append(f"{uid}{tcode}{lag:+d}")
        else:
            parts.append(f"{uid}{tcode}")
    return ";".join(parts)


def parse_mspdi_xml_to_df(xml_bytes: bytes) -> pd.DataFrame:
    """Упрощённая таблица задач из Project XML (MSPDI)."""
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as e:
        raise ValueError(f"Не удалось разобрать XML: {e}") from e

    rows: list[dict[str, Any]] = []
    for task in root.iter():
        if _local(task.tag) != "Task":
            continue
        fields: dict[str, str] = {}
        for child in list(task):
            ln = _local(child.tag)
            if ln in {
                "UID",
                "ID",
                "Name",
                "Start",
                "Finish",
                "OutlineLevel",
                "Summary",
                "PercentComplete",
                "Notes",
                "BaselineStart",
                "BaselineFinish",
                "Number1",
                "Number2",
                "Text1",
                "Text13",
                "Text14",
                "Text15",
                "Text16",
            }:
                fields[ln] = (child.text or "").strip()
        tid = fields.get("ID") or fields.get("UID") or ""
        if not tid or tid == "0":
            continue
        name = fields.get("Name") or ""
        if not name:
            continue
        start = _parse_date(fields.get("Start") or "")
        finish = _parse_date(fields.get("Finish") or "")
        rows.append(
            {
                "Ид": tid,
                "Название": name,
                "Уровень": fields.get("OutlineLevel") or "",
                "Суммарная": "да" if fields.get("Summary") == "1" else "",
                "Начало": _fmt_d(start),
                "Окончание": _fmt_d(finish),
                "Базовое_начало": _fmt_d(_parse_date(fields.get("BaselineStart") or "")),
                "Базовое_окончание": _fmt_d(_parse_date(fields.get("BaselineFinish") or "")),
                "%_завершения": fields.get("PercentComplete") or "",
                "Предшественники": _pred_links_to_str(task),
                "ВОР": fields.get("Text13") or fields.get("Number1") or "",
                "Ед_изм": fields.get("Text14") or fields.get("Text1") or "",
                "ВОР_факт": fields.get("Text15") or "",
                "ВОР_остаток": fields.get("Text16") or "",
                "Осталось_дней_прогноз": fields.get("Number2") or "",
                "Заметки": (fields.get("Notes") or "")[:120],
                "_start": start,
                "_finish": finish,
            }
        )
    return pd.DataFrame(rows)


def csv_rows_to_schedule_df(rows: list[dict[str, str]]) -> pd.DataFrame:
    out: list[dict[str, Any]] = []
    for r in rows:
        tid = str(r.get("Ид") or "").strip()
        name = str(r.get("Название") or "").strip()
        if not tid or not name:
            continue
        start = _parse_date(r.get("Начало") or "")
        finish = _parse_date(r.get("Окончание") or "")
        out.append(
            {
                "Ид": tid,
                "Название": name,
                "Уровень": r.get("Уровень_структуры") or r.get("Уровень") or "",
                "Начало": r.get("Начало") or _fmt_d(start),
                "Окончание": r.get("Окончание") or _fmt_d(finish),
                "Базовое_начало": r.get("Базовое_начало") or "",
                "Базовое_окончание": r.get("Базовое_окончание") or "",
                "%_завершения": r.get("Процент_завершения") or "",
                "Предшественники": r.get("Предшественники") or "",
                "Последователи": r.get("Последователи") or "",
                "ВОР": r.get("ВОР") or "",
                "ВОР_факт": r.get("ВОР_факт") or "",
                "ВОР_остаток": r.get("ВОР_остаток") or "",
                "Ед_изм": r.get("Ед_изм") or "",
                "%_выполнения_ВОР": r.get("%_выполнения_ВОР") or "",
                "Осталось_дней_прогноз": r.get("Осталось_дней_прогноз") or "",
                "Заметки": (r.get("Заметки") or "")[:120],
                "_start": start,
                "_finish": finish,
            }
        )
    return pd.DataFrame(out)


def apply_updates_to_schedule_df(df: pd.DataFrame, updates) -> pd.DataFrame:
    """Копия df с after-значениями для сопоставленных Id; колонка Изменено."""
    if df.empty:
        return df
    by_id = {str(u.task_id): u for u in updates if getattr(u, "task_id", None)}
    out = df.copy()
    out["Изменено"] = ""
    for i, row in out.iterrows():
        tid = str(row.get("Ид") or "")
        u = by_id.get(tid)
        if not u:
            continue
        changed: list[str] = []
        for col in YELLOW_COLS:
            if col not in out.columns:
                continue
            new_v = u.after.get(col)
            if new_v is None:
                continue
            old_v = str(row.get(col) or "").strip()
            if str(new_v).strip() != old_v:
                changed.append(col)
            out.at[i, col] = new_v
            if col == "Начало":
                out.at[i, "_start"] = _parse_date(str(new_v))
            if col == "Окончание":
                out.at[i, "_finish"] = _parse_date(str(new_v))
        out.at[i, "Изменено"] = ", ".join(changed) if changed else "да"
    return out


def render_schedule_gantt(
    df: pd.DataFrame,
    *,
    title: str = "График в браузере",
    color_col: str | None = None,
    max_bars: int = 40,
    highlight_ids: set[str] | None = None,
) -> None:
    if df is None or df.empty:
        st.info("Нет задач для Ганта.")
        return
    work = df.copy()
    if highlight_ids:
        # сначала изменённые, потом соседние по Id
        work["_prio"] = work["Ид"].astype(str).isin(highlight_ids).astype(int)
        work = work.sort_values(["_prio", "Ид"], ascending=[False, True])
    # только с датами
    work = work[work["_start"].notna() & work["_finish"].notna()]
    if work.empty:
        st.info("У задач нет распознанных дат Начало/Окончание.")
        return
    if len(work) > max_bars:
        st.caption(f"Показаны первые {max_bars} из {len(work)} задач с датами (фильтр ниже).")
        work = work.head(max_bars)

    plot_df = pd.DataFrame(
        {
            "Задача": work.apply(
                lambda r: f"{r['Ид']}. {str(r['Название'])[:48]}", axis=1
            ),
            "Начало": work["_start"],
            "Окончание": [
                f if f >= s else s for s, f in zip(work["_start"], work["_finish"])
            ],
        }
    )
    if color_col and color_col in work.columns:
        plot_df["Слой"] = work[color_col].fillna("").astype(str).values
        color = "Слой"
    elif highlight_ids:
        plot_df["Слой"] = [
            "изменено" if str(i) in highlight_ids else "прочее"
            for i in work["Ид"].astype(str)
        ]
        color = "Слой"
    else:
        plot_df["Слой"] = "график"
        color = "Слой"

    fig = px.timeline(
        plot_df,
        x_start="Начало",
        x_end="Окончание",
        y="Задача",
        color=color,
        title=title,
        color_discrete_map={
            "изменено": "#1a73e8",
            "прочее": "#9aa0a6",
            "после PPT": "#1a73e8",
            "до": "#9aa0a6",
            "график": "#1a73e8",
        },
    )
    fig.update_yaxes(autorange="reversed")
    fig.update_layout(
        height=max(320, 28 * len(plot_df) + 80),
        margin=dict(l=10, r=10, t=50, b=20),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
    )
    st.plotly_chart(fig, use_container_width=True)


def render_schedule_table(
    df: pd.DataFrame,
    *,
    title: str = "Таблица графика",
    show_cols: list[str] | None = None,
) -> None:
    if df is None or df.empty:
        st.info("Пустая таблица.")
        return
    st.markdown(f"**{title}**")
    cols = show_cols or [
        c
        for c in [
            "Ид",
            "Название",
            "Начало",
            "Окончание",
            "Предшественники",
            "Последователи",
            "ВОР",
            "ВОР_факт",
            "ВОР_остаток",
            "%_выполнения_ВОР",
            "Осталось_дней_прогноз",
            "Изменено",
            "Заметки",
        ]
        if c in df.columns
    ]
    view = df[cols].copy()
    st.dataframe(view, use_container_width=True, hide_index=True, height=min(480, 40 + 35 * min(len(view), 12)))


def render_compare_gantt(updates, show_before: bool = True, show_after: bool = True) -> None:
    """Гант только по обновлённым задачам: до / после."""
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
                    {"Задача": label, "Начало": start, "Окончание": finish, "Источник": "после PPT"}
                )
            except Exception:
                pass
        if show_before:
            try:
                bs = datetime.strptime(u.before["Начало"], "%d.%m.%y")
                bf = datetime.strptime(u.before["Окончание"], "%d.%m.%y")
                rows.append(
                    {"Задача": label, "Начало": bs, "Окончание": bf, "Источник": "до"}
                )
            except Exception:
                pass
    if not rows:
        st.info("Нет дат для Ганта сравнения.")
        return
    df = pd.DataFrame(rows)
    fig = px.timeline(
        df,
        x_start="Начало",
        x_end="Окончание",
        y="Задача",
        color="Источник",
        title="Сравнение сроков: до PPT → после",
        color_discrete_map={"до": "#9aa0a6", "после PPT": "#1a73e8"},
        category_orders={"Источник": ["до", "после PPT"]},
    )
    fig.update_yaxes(autorange="reversed")
    n = len({u.task_id for u in updates if u.task_id})
    fig.update_layout(
        height=max(280, 90 * max(1, n)),
        margin=dict(l=20, r=20, t=50, b=20),
        legend=dict(title="Слой", orientation="h", yanchor="bottom", y=1.02, x=0),
    )
    st.plotly_chart(fig, use_container_width=True)
