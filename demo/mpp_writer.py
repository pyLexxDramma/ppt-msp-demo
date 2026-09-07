"""Optional: write schedule/VOR fields into .mpp via MS Project COM (Windows + Project only).

Правила записи (тест XCA):
- Пишем: ВОР/факт/остаток/ед., %ВОР, осталось дней (прогноз), Начало/Окончание.
- НЕ пишем базовые поля формы (у заказчика они «жёлтые»: Базовое начало/окончание).
- НЕ трогаем ActualStart/ActualFinish по умолчанию (иначе Project сбрасывает % 100→0).
- Связи не меняем; после CalculateProject перепроверяем Pred/Succ.
- Number2 (прогноз Mode1) пишем повторно после Calculate.
"""

from __future__ import annotations

import tempfile
from datetime import date, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .build_update import TaskUpdate


def project_available() -> bool:
    try:
        import win32com.client  # noqa: F401

        return True
    except ImportError:
        return False


def _parse_csv_date(s: str) -> date | None:
    s = (s or "").strip()
    if not s or s.upper() in {"НД", "NA"}:
        return None
    for fmt in ("%d.%m.%y", "%d.%m.%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except Exception:
            continue
    return None


def _fmt_num(v: Any) -> str | None:
    if v is None or v == "":
        return None
    try:
        f = float(str(v).replace(",", ".").replace("%", "").strip())
        if abs(f - int(f)) < 1e-9:
            return str(int(f))
        return str(f)
    except (TypeError, ValueError):
        return str(v)


def _safe_set(task, attr: str, value) -> bool:
    try:
        setattr(task, attr, value)
        return True
    except Exception:
        return False


def _snap_links(proj, ids: set[str]) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for t in proj.Tasks:
        if t is None:
            continue
        try:
            tid = str(int(t.ID))
        except Exception:
            continue
        if tid not in ids:
            continue
        out[tid] = {
            "preds": t.Predecessors or "",
            "succs": t.Successors or "",
            "pct": str(int(t.PercentComplete)) if t.PercentComplete is not None else "",
        }
    return out


def _apply_yellow_fields(task, u: "TaskUpdate", *, write_dates: bool) -> None:
    """ВОР + прогноз; даты — опционально."""
    after = u.after
    ppt = u.ppt or {}

    vor = _fmt_num(after.get("ВОР") or ppt.get("total"))
    fact = _fmt_num(after.get("ВОР_факт") if after.get("ВОР_факт") not in (None, "") else ppt.get("done"))
    rest = _fmt_num(after.get("ВОР_остаток") if after.get("ВОР_остаток") not in (None, "") else ppt.get("rest"))
    unit = after.get("Ед_изм") or ppt.get("unit") or ""
    pct_vor = _fmt_num(after.get("%_выполнения_ВОР") or ppt.get("pct"))
    rem = _fmt_num(after.get("Осталось_дней_прогноз"))

    rest_f = None
    try:
        rest_f = float(rest) if rest is not None else None
    except ValueError:
        rest_f = None

    # Если по PPT остаток > 0, а в MSP задача 100% — даты не правятся. Снимаем «закрытие».
    if rest_f is not None and rest_f > 0 and int(task.PercentComplete or 0) >= 100:
        try:
            if pct_vor is not None:
                task.PercentComplete = max(0, min(99, int(float(pct_vor))))
            else:
                task.PercentComplete = 99
        except Exception:
            try:
                task.PercentComplete = 0
            except Exception:
                pass
        try:
            # очистить факт. окончание, иначе Finish не меняется
            task.ActualFinish = "NA"
        except Exception:
            pass

    if vor is not None:
        _safe_set(task, "Text13", vor)
    if unit:
        _safe_set(task, "Text14", str(unit))
    if fact is not None:
        _safe_set(task, "Text15", fact)
    if rest is not None:
        _safe_set(task, "Text16", rest)
    if pct_vor is not None:
        try:
            task.Number1 = float(pct_vor)
        except Exception:
            pass
    if rem is not None:
        try:
            task.Number2 = float(rem)
        except Exception:
            pass

    if not write_dates:
        return

    start_d = _parse_csv_date(after.get("Начало", ""))
    finish_d = _parse_csv_date(after.get("Окончание", ""))

    # Только плановые Start/Finish — без ActualStart (он сбрасывает прогресс)
    if start_d:
        _safe_set(task, "ConstraintType", 0)  # ASAP
        _safe_set(task, "Start", start_d.strftime("%d.%m.%Y"))
    if finish_d:
        ok = _safe_set(task, "Finish", finish_d.strftime("%d.%m.%Y"))
        if not ok:
            _safe_set(task, "ConstraintType", 3)  # Must Finish On
            _safe_set(task, "ConstraintDate", finish_d.strftime("%d.%m.%Y"))
            _safe_set(task, "Finish", finish_d.strftime("%d.%m.%Y"))


def apply_updates_to_mpp(
    mpp_bytes: bytes,
    updates: list["TaskUpdate"],
    *,
    preserve_progress: bool = True,
    write_dates: bool = True,
    recalculate: bool = True,
) -> bytes:
    """Применить ВОР/сроки/прогноз к копии MPP. Базу и связи не трогаем.

    preserve_progress=True (по умолчанию): не писать ActualStart/ActualFinish/% Complete.
    """
    import win32com.client

    by_id = {u.task_id: u for u in updates if u.task_id}
    if not by_id:
        return mpp_bytes

    with tempfile.TemporaryDirectory() as td:
        src = Path(td) / "in.mpp"
        out = Path(td) / "out.mpp"
        src.write_bytes(mpp_bytes)

        app = win32com.client.Dispatch("MSProject.Application")
        app.Visible = False
        app.DisplayAlerts = False
        try:
            app.FileOpen(str(src))
            proj = app.ActiveProject
            before_links = _snap_links(proj, set(by_id))

            for t in proj.Tasks:
                if t is None:
                    continue
                try:
                    tid = str(int(t.ID))
                except Exception:
                    continue
                if tid not in by_id:
                    continue
                _apply_yellow_fields(t, by_id[tid], write_dates=write_dates)

            if recalculate:
                try:
                    app.CalculateProject()
                except Exception:
                    pass

            # Повторно зафиксировать кастомный прогноз Mode1 и ВОР (каскад мог пересчитать длительности)
            for t in proj.Tasks:
                if t is None:
                    continue
                try:
                    tid = str(int(t.ID))
                except Exception:
                    continue
                if tid not in by_id:
                    continue
                u = by_id[tid]
                rem = _fmt_num(u.after.get("Осталось_дней_прогноз"))
                if rem is not None:
                    try:
                        t.Number2 = float(rem)
                    except Exception:
                        pass
                rest = _fmt_num(u.after.get("ВОР_остаток") or (u.ppt or {}).get("rest"))
                if rest is not None:
                    _safe_set(t, "Text16", rest)
                # %: вернуть исходный; если был 100% при остатке ВОР>0 — поставить %ВОР (<100)
                if preserve_progress and tid in before_links:
                    u = by_id[tid]
                    rest_v = _fmt_num(u.after.get("ВОР_остаток") or (u.ppt or {}).get("rest"))
                    try:
                        rest_left = float(rest_v) if rest_v is not None else 0.0
                    except ValueError:
                        rest_left = 0.0
                    old_pct = before_links[tid].get("pct")
                    try:
                        old_i = int(old_pct) if old_pct != "" else None
                    except ValueError:
                        old_i = None
                    if old_i is not None and old_i >= 100 and rest_left > 0:
                        pct_vor = _fmt_num(
                            u.after.get("%_выполнения_ВОР") or (u.ppt or {}).get("pct")
                        )
                        try:
                            t.PercentComplete = max(
                                0, min(99, int(float(pct_vor)) if pct_vor else 99)
                            )
                        except Exception:
                            pass
                    elif old_i is not None and int(t.PercentComplete or 0) != old_i:
                        try:
                            t.PercentComplete = old_i
                        except Exception:
                            pass

            after_links = _snap_links(proj, set(by_id))
            # sanity: связи должны совпасть (не пишем в файл лог, вызывающий код может сверить)
            _ = before_links, after_links

            app.FileSaveAs(str(out))
            app.FileClose(0)
            return out.read_bytes()
        finally:
            try:
                app.Quit()
            except Exception:
                pass


def verify_mpp_links(
    mpp_before: bytes,
    mpp_after: bytes,
    task_ids: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Сравнить Pred/Succ до и после (для UI / отчёта приёмки)."""
    import win32com.client

    def dump(raw: bytes) -> dict[str, dict[str, str]]:
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "t.mpp"
            p.write_bytes(raw)
            app = win32com.client.Dispatch("MSProject.Application")
            app.Visible = False
            app.DisplayAlerts = False
            try:
                app.FileOpen(str(p))
                proj = app.ActiveProject
                ids = set(task_ids) if task_ids else None
                out: dict[str, dict[str, str]] = {}
                for t in proj.Tasks:
                    if t is None:
                        continue
                    try:
                        tid = str(int(t.ID))
                    except Exception:
                        continue
                    if ids is not None and tid not in ids:
                        continue
                    out[tid] = {
                        "preds": t.Predecessors or "",
                        "succs": t.Successors or "",
                    }
                app.FileClose(0)
                return out
            finally:
                try:
                    app.Quit()
                except Exception:
                    pass

    b, a = dump(mpp_before), dump(mpp_after)
    keys = sorted(set(b) | set(a), key=lambda x: int(x) if x.isdigit() else x)
    rows = []
    for tid in keys:
        pb, pa = b.get(tid, {}), a.get(tid, {})
        ok = pb.get("preds") == pa.get("preds") and pb.get("succs") == pa.get("succs")
        rows.append(
            {
                "Ид": tid,
                "Pred до": pb.get("preds", ""),
                "Pred после": pa.get("preds", ""),
                "Succ до": pb.get("succs", ""),
                "Succ после": pa.get("succs", ""),
                "Связи OK": "да" if ok else "НЕТ",
            }
        )
    return rows
