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
    plan: float | None = None
    fact: float | None = None


@dataclass
class FormState:
    project: str = ""
    project_id: str = ""
    period_month: int = -1  # -1 = не выбран
    period_year: int = 0
    mode: str = "last"
    task_name: str = ""
    task_id: str = ""
    vor: float = 0.0
    unit: str = ""
    prev_cumulative: float = 0.0
    month_plan: float | None = None
    month_fact: float | None = None
    weeks: list[WeekRow] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.weeks:
            self.weeks = [WeekRow() for _ in range(WEEKS_COUNT)]
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
                plan=_opt_float(w.get("plan"), none_ok=True),
                fact=_opt_float(w.get("fact"), none_ok=True),
            )
            for w in weeks_raw
        ]
        return cls(
            project=str(raw.get("project") or ""),
            project_id=str(raw.get("project_id") or ""),
            period_month=int(raw.get("period_month") if raw.get("period_month") is not None else -1),
            period_year=int(raw.get("period_year") or 0),
            mode=str(raw.get("mode") or "last"),
            task_name=str(raw.get("task_name") or ""),
            task_id=str(raw.get("task_id") or ""),
            vor=float(raw.get("vor") or 0),
            unit=str(raw.get("unit") or ""),
            prev_cumulative=float(raw.get("prev_cumulative") or 0),
            month_plan=_opt_float(raw.get("month_plan"), none_ok=True),
            month_fact=_opt_float(raw.get("month_fact"), none_ok=True),
            weeks=weeks,
        )


def empty_form() -> FormState:
    """Пустая форма «как на проде» — без демо-префилла."""
    return FormState()


def sample_form_for_tests() -> FormState:
    """Демо-значения только для автотестов Mode1."""
    return FormState(
        project="ЖК Ленинский",
        project_id="0feb8a44-a0f4-11ef-af7f-0050560219d5",
        period_month=6,
        period_year=2026,
        mode="last",
        task_name="Фундаменты сборные",
        task_id="6",
        vor=350.0,
        unit="шт",
        prev_cumulative=0.0,
        month_plan=100.0,
        month_fact=55.0,
        weeks=[
            WeekRow(20, 10),
            WeekRow(20, 30),
            WeekRow(20, 0),
            WeekRow(20, 15),
            WeekRow(20, None),
        ],
    )


@dataclass
class WeekAgg:
    dev: float | None
    cum: float | None


@dataclass
class FormAggregates:
    plan_total: float
    fact_total: float
    month_deviation: float | None
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
    week_plan = 0.0
    week_fact = 0.0
    cum: float | None = None
    last_cum = 0.0
    rows: list[WeekAgg] = []

    for w in state.weeks[:WEEKS_COUNT]:
        plan_v = float(w.plan or 0)
        week_plan += plan_v
        if w.fact is None:
            rows.append(WeekAgg(dev=None, cum=None))
            continue
        f = float(w.fact)
        week_fact += f
        dev = f - plan_v
        row_cum = (0.0 if cum is None else cum) + dev
        cum = row_cum
        last_cum = row_cum
        rows.append(WeekAgg(dev=dev, cum=row_cum))

    month_plan = float(state.month_plan) if state.month_plan is not None else week_plan
    month_fact = float(state.month_fact) if state.month_fact is not None else week_fact
    month_deviation = None
    if state.month_plan is not None and state.month_fact is not None:
        month_deviation = float(state.month_plan) - float(state.month_fact)

    period_fact = float(state.month_fact) if state.month_fact is not None else week_fact
    vor = float(state.vor or 0)
    done = float(state.prev_cumulative or 0) + period_fact
    remaining = vor - done
    pct = (done / vor * 100.0) if vor else 0.0
    return FormAggregates(
        plan_total=month_plan,
        fact_total=month_fact,
        month_deviation=month_deviation,
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
    """Гейт: период, ВОР > 0 и факт за месяц или неделя > 0."""
    if int(state.period_month) < 0 or int(state.period_month) > 11:
        return False
    if int(state.period_year) < 2000:
        return False
    if float(state.vor or 0) <= 0:
        return False
    if state.month_fact is not None and float(state.month_fact) > 0:
        return True
    for w in state.weeks:
        if w.fact is not None and float(w.fact) > 0:
            return True
    return False


def to_mode1_inputs(state: FormState) -> dict[str, Any]:
    agg = compute_aggregates(state)
    facts = weeks_fact_list(state)
    if state.month_fact is not None and float(state.month_fact) > 0:
        if not any(f is not None and float(f) > 0 for f in facts):
            # Нет недельного факта — для Mode1 кладём факт месяца в 1-ю неделю
            facts = [float(state.month_fact), None, None, None, None]
    return {
        "rest": agg.remaining,
        "weeks_fact": facts,
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
