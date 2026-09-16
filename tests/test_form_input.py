"""Unit-тесты формы и Mode1 (без COM)."""

from __future__ import annotations

from datetime import date

from demo.form_input import (
    FormState,
    WeekRow,
    compute_aggregates,
    form_ready_for_recalc,
    run_mode1_for_form,
    today_from_period,
)


def test_aggregates_mockup_default() -> None:
    state = FormState()
    agg = compute_aggregates(state)
    # 10+30+0+15 = 55 факт; prev 150 → done 205; vor 350 → rest 145
    assert agg.fact_total == 55
    assert agg.done == 205
    assert agg.remaining == 145
    assert agg.plan_total == 100
    assert form_ready_for_recalc(state) is True


def test_today_end_of_month() -> None:
    state = FormState(period_month=6, period_year=2026)  # июль (0-based 6)
    assert today_from_period(state) == date(2026, 7, 31)


def test_mode1_produces_finish() -> None:
    state = FormState(
        period_month=6,
        period_year=2026,
        vor=350,
        prev_cumulative=150,
        weeks=[
            WeekRow(20, 10),
            WeekRow(20, 30),
            WeekRow(20, 0),
            WeekRow(20, 15),
            WeekRow(20, None),
        ],
    )
    out = run_mode1_for_form(state)
    sched = out["schedule"]
    m1 = sched["mode1"]
    assert m1["last_week"] == 4
    assert m1["fact_period"] == 15
    assert sched["finish"] is not None
    assert m1["remaining_days_ceil"] is not None
    assert m1["remaining_days_ceil"] > 0


def test_not_ready_without_fact() -> None:
    state = FormState(
        vor=100,
        weeks=[WeekRow(10, None), WeekRow(10, None), WeekRow(10, None), WeekRow(10, None), WeekRow(10, None)],
    )
    assert form_ready_for_recalc(state) is False
