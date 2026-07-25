"""Match PPT works to MSP CSV rows and build yellow-column updates."""

from __future__ import annotations

import csv
import io
import re
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from .mode1 import compute_mode1_schedule
from .parse_pptx import WeeklyReport


def _norm_name(s: str) -> str:
    s = (s or "").lower().replace("ё", "е")
    s = re.sub(r"[^\w\s]+", " ", s, flags=re.UNICODE)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _similarity(a: str, b: str) -> float:
    na, nb = _norm_name(a), _norm_name(b)
    if not na or not nb:
        return 0.0
    if na in nb or nb in na:
        return 0.95
    return SequenceMatcher(None, na, nb).ratio()


def _fmt_date(d: date | None) -> str:
    if not d:
        return ""
    # MSP CSV style: dd.mm.yy
    return d.strftime("%d.%m.%y")


def _parse_period_month(period: str) -> tuple[int | None, int | None]:
    months = {
        "январ": 1,
        "феврал": 2,
        "март": 3,
        "апрел": 4,
        "ма": 5,
        "июн": 6,
        "июл": 7,
        "август": 8,
        "сентябр": 9,
        "октябр": 10,
        "ноябр": 11,
        "декабр": 12,
    }
    p = (period or "").lower()
    year_m = re.search(r"(20\d{2})", p)
    year = int(year_m.group(1)) if year_m else None
    for key, m in months.items():
        if key in p:
            # avoid "ма" matching "март" wrongly — "ма" is short; check май separately
            if key == "ма" and "май" not in p and "мая" not in p:
                continue
            return year, m
    if "май" in p or "мая" in p:
        return year, 5
    return year, None


@dataclass
class TaskUpdate:
    task_id: str
    name: str
    match_score: float
    ppt_title: str
    before: dict[str, str]
    after: dict[str, str]
    schedule: dict[str, Any] = field(default_factory=dict)
    ppt: dict[str, Any] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_msp_csv(path_or_bytes: str | Path | bytes, encoding: str = "cp1251") -> tuple[list[str], list[dict[str, str]]]:
    if isinstance(path_or_bytes, (str, Path)):
        raw = Path(path_or_bytes).read_bytes()
    else:
        raw = path_or_bytes
    text = raw.decode(encoding, errors="replace")
    reader = csv.DictReader(io.StringIO(text), delimiter=";")
    fieldnames = list(reader.fieldnames or [])
    rows = [dict(r) for r in reader]
    return fieldnames, rows


def match_and_build_updates(
    reports: list[WeeklyReport],
    csv_rows: list[dict[str, str]],
    today: date | None = None,
    min_score: float = 0.55,
) -> list[TaskUpdate]:
    today = today or date.today()
    leaf_rows = [
        r
        for r in csv_rows
        if (r.get("Название") or "").strip()
        and (r.get("БЛОК") or "") != "Суммарная задача"
        and (r.get("ВОР") or "").strip()
    ]

    updates: list[TaskUpdate] = []
    used_ids: set[str] = set()

    for rep in reports:
        best, best_score = None, 0.0
        for row in leaf_rows:
            tid = str(row.get("Ид") or "")
            if tid in used_ids:
                continue
            score = _similarity(rep.title, row.get("Название") or "")
            # volume bonus
            try:
                vor = float(str(row.get("ВОР") or "0").replace(" ", "").replace(",", "."))
            except ValueError:
                vor = 0.0
            if rep.total and vor and abs(vor - rep.total) < 0.5:
                score = max(score, 0.9)
            if score > best_score:
                best, best_score = row, score

        if not best or best_score < min_score:
            updates.append(
                TaskUpdate(
                    task_id="",
                    name="",
                    match_score=best_score,
                    ppt_title=rep.title,
                    before={},
                    after={},
                    ppt=rep.to_dict(),
                    notes=[f"Не найдена задача MSP (score={best_score:.2f})"],
                )
            )
            continue

        used_ids.add(str(best.get("Ид")))
        py, pm = _parse_period_month(rep.period)
        sched = compute_mode1_schedule(
            rest=float(rep.rest or 0),
            weeks_fact=rep.weeks_fact,
            today=today,
            total=rep.total,
            done=rep.done,
            period_year=py,
            period_month=pm,
            history_months=rep.history_months,
        )

        start_d = date.fromisoformat(sched["start"]) if sched.get("start") else None
        finish_d = date.fromisoformat(sched["finish"]) if sched.get("finish") else None

        before = {
            "ВОР": best.get("ВОР") or "",
            "Ед_изм": best.get("Ед_изм") or "",
            "Начало": best.get("Начало") or "",
            "Окончание": best.get("Окончание") or "",
            "Процент_завершения": best.get("Процент_завершения") or "",
            "Заметки": best.get("Заметки") or "",
            "Предшественники": best.get("Предшественники") or "",
            "Последователи": best.get("Последователи") or "",
            "Базовое_начало": best.get("Базовое_начало") or "",
            "Базовое_окончание": best.get("Базовое_окончание") or "",
        }

        note_bits = [
            f"PPT: Всего={rep.total} Выполнено={rep.done} Остаток={rep.rest} {rep.unit}",
            f"%ВОР PPT={rep.pct:.2f}%" if rep.pct is not None else "",
            f"Mode1 осталось дн≈{sched.get('remaining_days_ceil')}",
            sched.get("finish_rule") or "",
        ]
        note = " | ".join(x for x in note_bits if x)

        after = dict(before)
        if rep.total is not None:
            after["ВОР"] = str(int(rep.total) if float(rep.total).is_integer() else rep.total)
        if rep.unit:
            after["Ед_изм"] = rep.unit
        if start_d:
            after["Начало"] = _fmt_date(start_d)
        if finish_d:
            after["Окончание"] = _fmt_date(finish_d)
        # % завершения не трогаем (формула/политика ТЗ) — пишем в Заметки
        after["Заметки"] = note

        notes = list(rep.notes)
        notes.append(sched.get("start_rule") or "")
        notes.append(f"match score={best_score:.2f}")

        updates.append(
            TaskUpdate(
                task_id=str(best.get("Ид")),
                name=best.get("Название") or "",
                match_score=best_score,
                ppt_title=rep.title,
                before=before,
                after=after,
                schedule=sched,
                ppt=rep.to_dict(),
                notes=[n for n in notes if n],
            )
        )

    return updates


def apply_updates_to_csv(
    fieldnames: list[str],
    rows: list[dict[str, str]],
    updates: list[TaskUpdate],
    encoding: str = "cp1251",
) -> bytes:
    by_id = {u.task_id: u for u in updates if u.task_id}
    out_rows: list[dict[str, str]] = []
    for row in rows:
        tid = str(row.get("Ид") or "")
        if tid in by_id:
            u = by_id[tid]
            new_row = dict(row)
            for k, v in u.after.items():
                if k in new_row:
                    new_row[k] = v
            out_rows.append(new_row)
        else:
            out_rows.append(row)

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames, delimiter=";", lineterminator="\n")
    writer.writeheader()
    writer.writerows(out_rows)
    return buf.getvalue().encode(encoding, errors="replace")


def updates_to_diff_table(updates: list[TaskUpdate]) -> list[dict[str, str]]:
    rows = []
    for u in updates:
        if not u.task_id:
            rows.append(
                {
                    "Ид": "—",
                    "Название": u.ppt_title,
                    "Статус": "не сопоставлено",
                    "Начало было": "",
                    "Начало стало": "",
                    "Окончание было": "",
                    "Окончание стало": "",
                    "ВОР": "",
                }
            )
            continue
        rows.append(
            {
                "Ид": u.task_id,
                "Название": u.name[:80],
                "Статус": "OK",
                "Начало было": u.before.get("Начало", ""),
                "Начало стало": u.after.get("Начало", ""),
                "Окончание было": u.before.get("Окончание", ""),
                "Окончание стало": u.after.get("Окончание", ""),
                "ВОР": f"{u.before.get('ВОР')} → {u.after.get('ВОР')}",
                "Осталось дн": str(u.schedule.get("remaining_days_ceil") or ""),
                "%ВОР PPT": f"{u.ppt.get('pct'):.1f}%" if u.ppt.get("pct") is not None else "",
            }
        )
    return rows
