"""Unit-тесты формы и Mode1 (без COM)."""

from __future__ import annotations

from datetime import date

from demo.form_input import (
    FormState,
    WeekRow,
    compute_aggregates,
    form_ready_for_recalc,
    run_mode1_for_form,
    sample_form_for_tests,
    today_from_period,
)


def test_aggregates_mockup_default() -> None:
    state = sample_form_for_tests()
    agg = compute_aggregates(state)
    # недели: план 20×5=100, факт 10+30+0+15=55; prev 0 → done 55; vor 350 → rest 295
    assert agg.fact_total == 55
    assert agg.done == 55
    assert agg.remaining == 295
    assert agg.plan_total == 100
    assert agg.month_deviation == 45  # 100 - 55
    assert form_ready_for_recalc(state) is True


def test_month_volumes_from_weeks_ignore_manual_month_fields() -> None:
    state = sample_form_for_tests()
    state.month_plan = 999
    state.month_fact = 1
    agg = compute_aggregates(state)
    assert agg.plan_total == 100
    assert agg.fact_total == 55
    assert agg.month_deviation == 45


def test_empty_form_not_ready() -> None:
    assert form_ready_for_recalc(FormState()) is False


def test_today_end_of_month() -> None:
    state = sample_form_for_tests()
    state.period_month = 6
    state.period_year = 2026
    assert today_from_period(state) == date(2026, 7, 31)


def test_mode1_produces_finish() -> None:
    state = sample_form_for_tests()
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
        period_month=6,
        period_year=2026,
        weeks=[WeekRow(10, None), WeekRow(10, None), WeekRow(10, None), WeekRow(10, None), WeekRow(10, None)],
    )
    assert form_ready_for_recalc(state) is False
