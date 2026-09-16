"""Граничные случаи Mode1 и статусов формы (без COM)."""

from __future__ import annotations

from demo.form_input import (
    FormState,
    WeekRow,
    compute_aggregates,
    form_ready_for_recalc,
    run_mode1_for_form,
    status_for_aggregates,
)


def _weeks(*facts: float | None) -> list[WeekRow]:
    return [WeekRow(plan=20, fact=f) for f in facts]


def test_cumulative_skips_weeks_without_fact() -> None:
    state = FormState(
        vor=350,
        prev_cumulative=0,
        weeks=_weeks(10, None, 0, 15, None),
    )
    agg = compute_aggregates(state)
    assert agg.rows[0].dev == 10 - 20
    assert agg.rows[1].dev is None and agg.rows[1].cum is None
    assert agg.rows[2].dev == 0 - 20
    assert agg.rows[2].cum == (10 - 20) + (0 - 20)
    assert agg.fact_total == 25
    assert agg.month_cum == (10 - 20) + (0 - 20) + (15 - 20)


def test_mode1_no_positive_fact() -> None:
    state = FormState(vor=100, prev_cumulative=0, weeks=_weeks(None, 0, None, None, None))
    assert form_ready_for_recalc(state) is False
    out = run_mode1_for_form(state)
    m1 = out["schedule"]["mode1"]
    assert m1["last_week"] is None
    assert out["schedule"]["finish"] is None


def test_mode1_remaining_zero_completed() -> None:
    state = FormState(
        vor=100,
        prev_cumulative=80,
        weeks=_weeks(20, None, None, None, None),
    )
    agg = compute_aggregates(state)
    assert agg.remaining == 0
    assert status_for_aggregates(agg) == "done"
    out = run_mode1_for_form(state)
    m1 = out["schedule"]["mode1"]
    assert m1["forecast_weeks"] == 0
    assert m1["remaining_days_ceil"] == 0
    assert out["schedule"]["finish"] is not None


def test_status_over_when_done_exceeds_vor() -> None:
    state = FormState(
        vor=100,
        prev_cumulative=90,
        weeks=_weeks(20, None, None, None, None),
    )
    agg = compute_aggregates(state)
    assert agg.done == 110
    assert agg.remaining == -10
    assert status_for_aggregates(agg) == "over"
