"""Модель формы ввода объёмов (макет construction_volumes_form) → вход Mode1."""

from __future__ import annotations

import calendar
from dataclasses import asdict, dataclass, field
from datetime import date
from typing import Any

from .mode1 import compute_mode1_schedule
from .parse_pptx import WeeklyReport

WEEKS_COUNT = 5
MONTHS_RU = [
    "Январь",
    "Февраль",
    "Март",
    "Апрель",
    "Май",
    "Июнь",
    "Июль",
    "Август",
    "Сентябрь",
    "Октябрь",
    "Ноябрь",
    "Декабрь",
]


@dataclass
class WeekRow:
    plan: float | None = 0.0
    fact: float | None = None


@dataclass
class FormState:
    project: str = "ЖК Ленинский"
    project_id: str = "0feb8a44-a0f4-11ef-af7f-0050560219d5"
    period_month: int = 6  # 0-based like mockup (июнь)
    period_year: int = 2026
    mode: str = "last"
    task_name: str = "Фундаменты сборные"
    task_id: str = "6"
    vor: float = 350.0
    unit: str = "шт"
    prev_cumulative: float = 150.0
    weeks: list[WeekRow] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.weeks:
            self.weeks = [
                WeekRow(plan=20, fact=10),
                WeekRow(plan=20, fact=30),
                WeekRow(plan=20, fact=0),
                WeekRow(plan=20, fact=15),
                WeekRow(plan=20, fact=None),
            ]
        while len(self.weeks) < WEEKS_COUNT:
            self.weeks.append(WeekRow())
        self.weeks = self.weeks[:WEEKS_COUNT]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "FormState":
        weeks_raw = raw.get("weeks") or []
        weeks = [
            WeekRow(
                plan=_opt_float(w.get("plan"), 0.0),
                fact=_opt_float(w.get("fact"), none_ok=True),
            )
            for w in weeks_raw
        ]
        return cls(
            project=str(raw.get("project") or "ЖК Ленинский"),
            project_id=str(raw.get("project_id") or ""),
            period_month=int(raw.get("period_month", 6)),
            period_year=int(raw.get("period_year", 2026)),
            mode=str(raw.get("mode") or "last"),
            task_name=str(raw.get("task_name") or ""),
            task_id=str(raw.get("task_id") or ""),
            vor=float(raw.get("vor") or 0),
            unit=str(raw.get("unit") or ""),
            prev_cumulative=float(raw.get("prev_cumulative") or 0),
            weeks=weeks,
        )


@dataclass
class WeekAgg:
    dev: float | None
    cum: float | None


@dataclass
class FormAggregates:
    plan_total: float
    fact_total: float
    month_cum: float
    done: float
    remaining: float
    pct_done: float
    rows: list[WeekAgg]
    vor: float


def _opt_float(v: Any, default: float | None = None, *, none_ok: bool = False) -> float | None:
    if v is None or v == "":
        return None if none_ok else default
    try:
        return float(v)
    except (TypeError, ValueError):
        return None if none_ok else default


def period_month_1based(state: FormState) -> int:
    """period_month в FormState — 0-based (как select в макете)."""
    return int(state.period_month) + 1


def today_from_period(state: FormState) -> date:
    """Сегодня для Mode1 = последний календарный день месяца отчёта."""
    y = int(state.period_year)
    m = period_month_1based(state)
    last = calendar.monthrange(y, m)[1]
    return date(y, m, last)


def period_label(state: FormState) -> str:
    idx = max(0, min(11, int(state.period_month)))
    return f"{MONTHS_RU[idx]} {state.period_year}"


def compute_aggregates(state: FormState) -> FormAggregates:
    plan_total = 0.0
    fact_total = 0.0
    cum: float | None = None
    last_cum = 0.0
    rows: list[WeekAgg] = []

    for w in state.weeks[:WEEKS_COUNT]:
        plan_v = float(w.plan or 0)
        plan_total += plan_v
        if w.fact is None:
            rows.append(WeekAgg(dev=None, cum=None))
            continue
        f = float(w.fact)
        fact_total += f
        dev = f - plan_v
        row_cum = (0.0 if cum is None else cum) + dev
        cum = row_cum
        last_cum = row_cum
        rows.append(WeekAgg(dev=dev, cum=row_cum))

    vor = float(state.vor or 0)
    done = float(state.prev_cumulative or 0) + fact_total
    remaining = vor - done
    pct = (done / vor * 100.0) if vor else 0.0
    return FormAggregates(
        plan_total=plan_total,
        fact_total=fact_total,
        month_cum=last_cum,
        done=done,
        remaining=remaining,
        pct_done=pct,
        rows=rows,
        vor=vor,
    )


def weeks_fact_list(state: FormState) -> list[float | None]:
    return [w.fact for w in state.weeks[:WEEKS_COUNT]]


def weeks_plan_list(state: FormState) -> list[float | None]:
    return [w.plan for w in state.weeks[:WEEKS_COUNT]]


def form_ready_for_recalc(state: FormState) -> bool:
    """Лёгкий гейт: ВОР > 0 и хотя бы один факт > 0."""
    if float(state.vor or 0) <= 0:
        return False
    for w in state.weeks:
        if w.fact is not None and float(w.fact) > 0:
            return True
    return False


def to_mode1_inputs(state: FormState) -> dict[str, Any]:
    agg = compute_aggregates(state)
    return {
        "rest": agg.remaining,
        "weeks_fact": weeks_fact_list(state),
        "today": today_from_period(state),
        "total": agg.vor,
        "done": agg.done,
        "period_year": int(state.period_year),
        "period_month": period_month_1based(state),
    }


def build_synthetic_report(state: FormState) -> WeeklyReport:
    agg = compute_aggregates(state)
    return WeeklyReport(
        slide_index=0,
        title=state.task_name,
        title_ole=state.task_name,
        period=period_label(state),
        weeks_plan=weeks_plan_list(state),
        weeks_fact=weeks_fact_list(state),
        total=agg.vor,
        done=agg.done,
        rest=agg.remaining,
        unit=state.unit,
        pct=agg.pct_done,
        history_months={},
        project_id=state.project_id,
        notes=["Источник: веб-форма ввода объёмов"],
    )


def run_mode1_for_form(state: FormState) -> dict[str, Any]:
    """Полный schedule-блок Mode1 + агрегаты формы."""
    agg = compute_aggregates(state)
    inputs = to_mode1_inputs(state)
    schedule = compute_mode1_schedule(
        rest=float(inputs["rest"]),
        weeks_fact=list(inputs["weeks_fact"]),
        today=inputs["today"],
        total=float(inputs["total"]),
        done=float(inputs["done"]),
        period_year=int(inputs["period_year"]),
        period_month=int(inputs["period_month"]),
    )
    return {
        "aggregates": agg,
        "schedule": schedule,
        "today": inputs["today"],
        "report": build_synthetic_report(state),
    }


def status_for_aggregates(agg: FormAggregates) -> str:
    if agg.vor > 0 and agg.done > agg.vor:
        return "over"
    if agg.vor > 0 and agg.done >= agg.vor:
        return "done"
    return "progress"
