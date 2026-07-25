"""Build MS Project XML (MSPDI-like) from CSV rows + yellow-column updates."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from datetime import date, datetime, time
from pathlib import Path
from typing import TYPE_CHECKING
from xml.dom import minidom

if TYPE_CHECKING:
    from .build_update import TaskUpdate

NS = "http://schemas.microsoft.com/project"
ET.register_namespace("", NS)


def _parse_date(s: str) -> date | None:
    s = (s or "").strip()
    if not s or s.upper() in {"НД", "NA", "Н/Д"}:
        return None
    raw = s[:19] if "T" in s else s
    for fmt in ("%d.%m.%y", "%d.%m.%Y", "%Y-%m-%d", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(s.replace("Z", "")).date()
    except ValueError:
        return None


def _xml_dt(d: date | None, end: bool = False) -> str | None:
    if not d:
        return None
    t = time(18, 0, 0) if end else time(9, 0, 0)
    return datetime.combine(d, t).strftime("%Y-%m-%dT%H:%M:%S")


def _parse_pct(s: str) -> int:
    m = re.search(r"(\d+)", str(s or "0"))
    return int(m.group(1)) if m else 0


def _parse_pred(cell: str) -> list[tuple[int, int, int]]:
    """Parse '6ОН+13 д;10НН' → [(pred_id, type, lag_days)].
    Type: 0=FF, 1=FS(ОН), 2=SF, 3=SS(НН) — MSPDI codes.
    """
    type_map = {"ОО": 0, "ОН": 1, "НО": 2, "НН": 3, "FF": 0, "FS": 1, "SF": 2, "SS": 3}
    out: list[tuple[int, int, int]] = []
    if not cell:
        return out
    for part in str(cell).replace(",", ";").split(";"):
        part = part.strip()
        if not part:
            continue
        m = re.match(
            r"(\d+)\s*([ОНFSon]{2})?\s*([+-]\s*\d+)?",
            part.replace("д", "").replace(" ", ""),
            re.I,
        )
        if not m:
            continue
        pid = int(m.group(1))
        tcode = (m.group(2) or "ОН").upper().replace("FS", "ОН").replace("SS", "НН")
        # normalize latin
        tcode = tcode.replace("FS", "ОН")
        if tcode in ("FS",):
            tcode = "ОН"
        typ = type_map.get(tcode, 1)
        lag = 0
        if m.group(3):
            lag = int(m.group(3).replace(" ", ""))
        out.append((pid, typ, lag))
    return out


def rows_to_mspdi_xml(
    rows: list[dict[str, str]],
    updates: list["TaskUpdate"] | None = None,
    project_name: str = "msp_updated",
) -> bytes:
    """Generate Project XML that MS Project can File→Open."""
    by_id = {u.task_id: u for u in (updates or []) if u.task_id}
    # Apply updates onto working copy of rows
    work = []
    for row in rows:
        r = dict(row)
        tid = str(r.get("Ид") or "")
        if tid in by_id:
            for k, v in by_id[tid].after.items():
                if k in r:
                    r[k] = v
        work.append(r)

    root = ET.Element(f"{{{NS}}}Project")
    ET.SubElement(root, f"{{{NS}}}Name").text = project_name
    ET.SubElement(root, f"{{{NS}}}Title").text = project_name
    ET.SubElement(root, f"{{{NS}}}ScheduleFromStart").text = "1"
    ET.SubElement(root, f"{{{NS}}}MinutesPerDay").text = "480"
    ET.SubElement(root, f"{{{NS}}}MinutesPerWeek").text = "2400"
    ET.SubElement(root, f"{{{NS}}}DaysPerMonth").text = "20"
    ET.SubElement(root, f"{{{NS}}}CurrencySymbol").text = "₽"

    tasks_el = ET.SubElement(root, f"{{{NS}}}Tasks")
    # Project summary task UID=0
    t0 = ET.SubElement(tasks_el, f"{{{NS}}}Task")
    ET.SubElement(t0, f"{{{NS}}}UID").text = "0"
    ET.SubElement(t0, f"{{{NS}}}ID").text = "0"
    ET.SubElement(t0, f"{{{NS}}}Name").text = project_name
    ET.SubElement(t0, f"{{{NS}}}Type").text = "1"
    ET.SubElement(t0, f"{{{NS}}}IsNull").text = "0"
    ET.SubElement(t0, f"{{{NS}}}OutlineLevel").text = "0"
    ET.SubElement(t0, f"{{{NS}}}Summary").text = "1"

    uid_by_id: dict[str, int] = {}
    for row in work:
        tid = str(row.get("Ид") or "").strip()
        if not tid:
            continue
        try:
            uid = int(tid)
        except ValueError:
            continue
        uid_by_id[tid] = uid

    for row in work:
        tid = str(row.get("Ид") or "").strip()
        name = (row.get("Название") or "").strip()
        if not tid or not name:
            continue
        try:
            uid = int(tid)
        except ValueError:
            continue

        start = _parse_date(row.get("Начало") or "")
        finish = _parse_date(row.get("Окончание") or "")
        b_start = _parse_date(row.get("Базовое_начало") or "")
        b_finish = _parse_date(row.get("Базовое_окончание") or "")
        outline = int(str(row.get("Уровень_структуры") or row.get("Уровень") or "1") or "1")
        is_summary = (row.get("БЛОК") or "") == "Суммарная задача" or not (row.get("ВОР") or "").strip()

        t = ET.SubElement(tasks_el, f"{{{NS}}}Task")
        ET.SubElement(t, f"{{{NS}}}UID").text = str(uid)
        ET.SubElement(t, f"{{{NS}}}ID").text = str(uid)
        ET.SubElement(t, f"{{{NS}}}Name").text = name
        ET.SubElement(t, f"{{{NS}}}Type").text = "0"
        ET.SubElement(t, f"{{{NS}}}IsNull").text = "0"
        ET.SubElement(t, f"{{{NS}}}OutlineLevel").text = str(max(1, outline))
        ET.SubElement(t, f"{{{NS}}}Summary").text = "1" if is_summary else "0"
        ET.SubElement(t, f"{{{NS}}}PercentComplete").text = str(_parse_pct(row.get("Процент_завершения") or "0"))
        if start:
            ET.SubElement(t, f"{{{NS}}}Start").text = _xml_dt(start, end=False)
        if finish:
            ET.SubElement(t, f"{{{NS}}}Finish").text = _xml_dt(finish, end=True)
        if start and finish and finish >= start:
            dur_days = (finish - start).days + 1
            # PTxh0m0s in ISO duration — Project uses PT[minutes]M sometimes; use days format
            ET.SubElement(t, f"{{{NS}}}Duration").text = f"PT{dur_days * 8}H0M0S"
            ET.SubElement(t, f"{{{NS}}}Manual").text = "0"

        notes = (row.get("Заметки") or "").strip()
        if notes:
            ET.SubElement(t, f"{{{NS}}}Notes").text = notes

        # Baseline
        if b_start:
            ET.SubElement(t, f"{{{NS}}}BaselineStart").text = _xml_dt(b_start, False)
        if b_finish:
            ET.SubElement(t, f"{{{NS}}}BaselineFinish").text = _xml_dt(b_finish, True)

        # Extended: volume as Number1/Text — keep simple Number1 = VOR if numeric
        vor = (row.get("ВОР") or "").replace(" ", "").replace(",", ".")
        try:
            vor_f = float(vor) if vor else None
        except ValueError:
            vor_f = None
        if vor_f is not None:
            ET.SubElement(t, f"{{{NS}}}Number1").text = str(vor_f)
        unit = (row.get("Ед_изм") or "").strip()
        if unit:
            ET.SubElement(t, f"{{{NS}}}Text1").text = unit

        for pred_id, typ, lag in _parse_pred(row.get("Предшественники") or ""):
            if str(pred_id) not in uid_by_id and pred_id not in uid_by_id.values():
                # still emit — Project resolves by UID
                pass
            pl = ET.SubElement(t, f"{{{NS}}}PredecessorLink")
            ET.SubElement(pl, f"{{{NS}}}PredecessorUID").text = str(pred_id)
            ET.SubElement(pl, f"{{{NS}}}Type").text = str(typ)
            # lag in tenths of minutes: 1 day = 4800
            ET.SubElement(pl, f"{{{NS}}}LinkLag").text = str(int(lag) * 4800)
            ET.SubElement(pl, f"{{{NS}}}LagFormat").text = "7"  # days

    rough = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    # pretty
    try:
        parsed = minidom.parseString(rough)
        return parsed.toprettyxml(indent="  ", encoding="utf-8")
    except Exception:
        return rough


def patch_mspdi_xml(
    xml_bytes: bytes,
    updates: list["TaskUpdate"],
) -> bytes:
    """Patch Start/Finish/Name notes in an existing Project XML by Task ID/UID."""
    by_id = {u.task_id: u for u in updates if u.task_id}
    if not by_id:
        return xml_bytes

    # Strip default ns for easier find, or use {*} 
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return xml_bytes

    def local(tag: str) -> str:
        return tag.split("}")[-1] if "}" in tag else tag

    for task in root.iter():
        if local(task.tag) != "Task":
            continue
        tid_el = None
        uid_el = None
        for child in list(task):
            ln = local(child.tag)
            if ln == "ID":
                tid_el = child
            elif ln == "UID":
                uid_el = child
        key = (tid_el.text if tid_el is not None else None) or (
            uid_el.text if uid_el is not None else None
        )
        if not key or key not in by_id:
            continue
        u = by_id[key]
        start = _parse_date(u.after.get("Начало", ""))
        finish = _parse_date(u.after.get("Окончание", ""))

        def set_child(name: str, value: str):
            for child in list(task):
                if local(child.tag) == name:
                    child.text = value
                    return
            # append with same ns as task
            ns = task.tag.split("}")[0].strip("{") if "}" in task.tag else NS
            el = ET.SubElement(task, f"{{{ns}}}{name}" if ns else name)
            el.text = value

        if start:
            set_child("Start", _xml_dt(start, False) or "")
        if finish:
            set_child("Finish", _xml_dt(finish, True) or "")
        note = u.after.get("Заметки") or ""
        if note:
            set_child("Notes", note)

    rough = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    try:
        return minidom.parseString(rough).toprettyxml(indent="  ", encoding="utf-8")
    except Exception:
        return rough


def load_xml_bytes(path_or_bytes: str | Path | bytes) -> bytes:
    if isinstance(path_or_bytes, (str, Path)):
        return Path(path_or_bytes).read_bytes()
    return path_or_bytes
