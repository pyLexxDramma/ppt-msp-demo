"""Match PPT works to MSP CSV rows and build yellow-column updates."""

from __future__ import annotations

import csv
import io
import re
from dataclasses import asdict, dataclass, field
from datetime import date
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from .field_map import CANONICAL_FIELDS, canonicalize_header, normalize_row
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
            if key == "ма" and "май" not in p and "мая" not in p:
                continue
            return year, m
    if "май" in p or "мая" in p:
        return year, 5
    return year, None


def _num_str(v: float | int | None) -> str:
    """Целое число в выгрузке (как в оригинальном CSV/MPP)."""
    if v is None:
        return ""
    try:
        return str(int(round(float(v))))
    except (TypeError, ValueError):
        return str(v)


def _pct_int(v: float | int | None) -> str:
    if v is None:
        return ""
    try:
        return str(int(round(float(v))))
    except (TypeError, ValueError):
        return ""


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
    """Load CSV and normalize headers to canonical 1:1 names."""
    if isinstance(path_or_bytes, (str, Path)):
        raw = Path(path_or_bytes).read_bytes()
    else:
        raw = path_or_bytes
    text = raw.decode(encoding, errors="replace")
    reader = csv.DictReader(io.StringIO(text), delimiter=";")
    raw_fields = list(reader.fieldnames or [])
    rows = [normalize_row(dict(r)) for r in reader]
    # Preserve order: canonical first for known, then extras
    seen: list[str] = []
    for f in raw_fields:
        cf = canonicalize_header(f)
        if cf and cf not in seen:
            seen.append(cf)
    for f in CANONICAL_FIELDS:
        if f not in seen:
            seen.append(f)
    return seen, rows


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
            "ВОР_факт": best.get("ВОР_факт") or "",
            "ВОР_остаток": best.get("ВОР_остаток") or "",
            "Ед_изм": best.get("Ед_изм") or "",
            "%_выполнения_ВОР": best.get("%_выполнения_ВОР") or "",
            "Осталось_дней_прогноз": best.get("Осталось_дней_прогноз") or "",
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
            after["ВОР"] = _num_str(rep.total)
        if rep.done is not None:
            after["ВОР_факт"] = _num_str(rep.done)
        if rep.rest is not None:
            after["ВОР_остаток"] = _num_str(rep.rest)
        if rep.unit:
            after["Ед_изм"] = rep.unit
        if rep.pct is not None:
            after["%_выполнения_ВОР"] = _pct_int(rep.pct)
        if sched.get("remaining_days_ceil") is not None:
            after["Осталось_дней_прогноз"] = str(int(sched["remaining_days_ceil"]))
        if start_d:
            after["Начало"] = _fmt_date(start_d)
        if finish_d:
            after["Окончание"] = _fmt_date(finish_d)
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
    """Write CSV with canonical headers (1:1 with MPP display names)."""
    by_id = {u.task_id: u for u in updates if u.task_id}

    out_fields: list[str] = []
    for f in CANONICAL_FIELDS:
        if f not in out_fields:
            out_fields.append(f)
    for f in fieldnames:
        cf = canonicalize_header(f)
        if cf and cf not in out_fields:
            out_fields.append(cf)

    out_rows: list[dict[str, str]] = []
    for row in rows:
        base = {f: row.get(f, "") for f in out_fields}
        tid = str(row.get("Ид") or "")
        if tid in by_id:
            for k, v in by_id[tid].after.items():
                ck = canonicalize_header(k)
                if ck in base:
                    base[ck] = v
                elif ck not in out_fields:
                    out_fields.append(ck)
                    base[ck] = v
        out_rows.append(base)

    # ensure all rows have all keys
    for r in out_rows:
        for f in out_fields:
            r.setdefault(f, "")

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=out_fields, delimiter=";", lineterminator="\n", extrasaction="ignore")
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
                "ВОР_факт": u.after.get("ВОР_факт", ""),
                "ВОР_остаток": u.after.get("ВОР_остаток", ""),
                "Осталось дн": str(u.schedule.get("remaining_days_ceil") or ""),
                "%ВОР": u.after.get("%_выполнения_ВОР", ""),
            }
        )
    return rows
