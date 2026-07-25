"""Optional: write dates into .mpp via MS Project COM (Windows + Project only)."""

from __future__ import annotations

import tempfile
from datetime import date, datetime
from pathlib import Path
from typing import TYPE_CHECKING

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
        except ValueError:
            continue
    return None


def apply_updates_to_mpp(
    mpp_bytes: bytes,
    updates: list["TaskUpdate"],
) -> bytes:
    """Apply Start/Finish (and Text13/15 when possible) to a copy of MPP. Requires MS Project."""
    import win32com.client

    by_id = {u.task_id: u for u in updates if u.task_id}
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
            for t in proj.Tasks:
                if t is None:
                    continue
                tid = str(int(t.ID))
                if tid not in by_id:
                    continue
                u = by_id[tid]
                start_d = _parse_csv_date(u.after.get("Начало", ""))
                finish_d = _parse_csv_date(u.after.get("Окончание", ""))
                try:
                    t.ConstraintType = 0  # ASAP first
                except Exception:
                    pass
                if u.after.get("ВОР"):
                    try:
                        t.Text13 = str(u.after["ВОР"])
                    except Exception:
                        pass
                if u.ppt.get("done") is not None:
                    try:
                        done = u.ppt["done"]
                        t.Text15 = str(int(done) if float(done).is_integer() else done)
                    except Exception:
                        pass
                if u.after.get("Ед_изм"):
                    try:
                        t.Text14 = u.after["Ед_изм"]
                    except Exception:
                        pass
                if start_d:
                    try:
                        t.ActualStart = start_d.strftime("%d.%m.%Y")
                    except Exception:
                        pass
                    try:
                        t.Start = start_d.strftime("%d.%m.%Y")
                    except Exception:
                        pass
                if finish_d:
                    try:
                        t.ConstraintType = 3  # Must Finish On
                        t.ConstraintDate = finish_d.strftime("%d.%m.%Y")
                        t.Finish = finish_d.strftime("%d.%m.%Y")
                    except Exception:
                        pass
            try:
                app.CalculateProject()
            except Exception:
                pass
            app.FileSaveAs(str(out))
            app.FileClose(0)
            return out.read_bytes()
        finally:
            try:
                app.Quit()
            except Exception:
                pass
