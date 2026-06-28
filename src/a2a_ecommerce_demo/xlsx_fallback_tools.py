from __future__ import annotations

import re
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

OOXML_NS = {
    "main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "rel": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "pkgrel": "http://schemas.openxmlformats.org/package/2006/relationships",
}


def _cell_to_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if re.fullmatch(r"-?\d+\.0", text):
        return text[:-2]
    return text


def _column_index(cell_ref: str) -> int:
    letters = re.sub(r"[^A-Z]", "", cell_ref.upper())
    index = 0
    for letter in letters:
        index = index * 26 + ord(letter) - ord("A") + 1
    return max(index - 1, 0)


def _xml_text(element: ET.Element | None) -> str:
    if element is None:
        return ""
    return "".join(element.itertext()).strip()


def _read_shared_strings(archive: zipfile.ZipFile) -> list[str]:
    try:
        xml = archive.read("xl/sharedStrings.xml")
    except KeyError:
        return []
    root = ET.fromstring(xml)
    return [_xml_text(item) for item in root.findall("main:si", OOXML_NS)]


def _sheet_targets(archive: zipfile.ZipFile) -> list[tuple[str, str]]:
    workbook = ET.fromstring(archive.read("xl/workbook.xml"))
    rels = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    target_by_id = {
        rel.attrib.get("Id", ""): rel.attrib.get("Target", "")
        for rel in rels.findall("pkgrel:Relationship", OOXML_NS)
    }
    sheets = []
    for sheet in workbook.findall("main:sheets/main:sheet", OOXML_NS):
        name = sheet.attrib.get("name", "Sheet")
        rel_id = sheet.attrib.get(f"{{{OOXML_NS['rel']}}}id", "")
        target = target_by_id.get(rel_id, "")
        if not target:
            continue
        target = target.lstrip("/")
        if not target.startswith("xl/"):
            target = f"xl/{target}"
        sheets.append((name, target))
    return sheets


def _cell_value(cell: ET.Element, shared_strings: list[str]) -> str:
    cell_type = cell.attrib.get("t", "")
    if cell_type == "inlineStr":
        return _xml_text(cell.find("main:is", OOXML_NS))
    value = _xml_text(cell.find("main:v", OOXML_NS))
    if cell_type == "s":
        try:
            return shared_strings[int(value)]
        except (ValueError, IndexError):
            return value
    if cell_type == "str":
        return value
    return _cell_to_text(value)


def read_xlsx_sheets(path: Path, max_rows: int = 5000, max_cols: int = 120, max_sheets: int = 20) -> list[dict[str, Any]]:
    """Read worksheet values directly from OOXML, ignoring styles and drawings."""
    sheets = []
    with zipfile.ZipFile(path) as archive:
        shared_strings = _read_shared_strings(archive)
        for sheet_name, target in _sheet_targets(archive)[:max_sheets]:
            root = ET.fromstring(archive.read(target))
            rows = []
            max_seen_col = 0
            for row_element in root.findall("main:sheetData/main:row", OOXML_NS):
                if len(rows) >= max_rows:
                    break
                values = [""] * max_cols
                has_value = False
                for cell in row_element.findall("main:c", OOXML_NS):
                    cell_ref = cell.attrib.get("r", "")
                    column_index = _column_index(cell_ref)
                    if column_index >= max_cols:
                        continue
                    value = _cell_value(cell, shared_strings)
                    values[column_index] = value
                    if value:
                        has_value = True
                        max_seen_col = max(max_seen_col, column_index + 1)
                if has_value:
                    rows.append(values)
            trimmed = [row[:max_seen_col] for row in rows] if max_seen_col else []
            dimension = root.find("main:dimension", OOXML_NS)
            sheets.append(
                {
                    "sheet": sheet_name,
                    "target": target,
                    "dimension": dimension.attrib.get("ref", "") if dimension is not None else "",
                    "rows": trimmed,
                    "max_column": max_seen_col,
                }
            )
    return sheets
