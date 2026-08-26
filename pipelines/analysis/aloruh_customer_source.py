from __future__ import annotations

from io import BytesIO
from pathlib import Path
import re
from xml.etree import ElementTree as ET
from zipfile import ZipFile

NS = {
    "main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "rel": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "pkg": "http://schemas.openxmlformats.org/package/2006/relationships",
}
REQUIRED_COLUMNS = {"商品ID", "SKC", "图片", "真实上架时间", "店铺名称"}


def cell_value(cell: ET.Element, shared: list[str]) -> str:
    if cell.attrib.get("t") == "inlineStr":
        return "".join(node.text or "" for node in cell.findall(".//main:t", NS))
    value = cell.find("main:v", NS)
    if value is None or value.text is None:
        return ""
    return shared[int(value.text)] if cell.attrib.get("t") == "s" else value.text


def column_index(reference: str) -> int:
    match = re.match(r"([A-Z]+)", reference.upper())
    if not match:
        raise ValueError(f"invalid cell reference: {reference}")
    result = 0
    for char in match.group(1):
        result = result * 26 + ord(char) - ord("A") + 1
    return result - 1


def first_sheet_path(book: ZipFile) -> str:
    root = ET.fromstring(book.read("xl/workbook.xml"))
    sheet = root.find("main:sheets/main:sheet", NS)
    if sheet is None:
        raise ValueError("customer workbook has no worksheet")
    relationship_id = sheet.attrib[f"{{{NS['rel']}}}id"]
    relationships = ET.fromstring(book.read("xl/_rels/workbook.xml.rels"))
    for item in relationships.findall("pkg:Relationship", NS):
        if item.attrib.get("Id") == relationship_id:
            target = item.attrib["Target"].lstrip("/")
            return target if target.startswith("xl/") else f"xl/{target}"
    raise ValueError("cannot resolve customer worksheet")


def read_workbook(content: bytes) -> list[dict[str, str]]:
    with ZipFile(BytesIO(content)) as book:
        shared = []
        if "xl/sharedStrings.xml" in book.namelist():
            root = ET.fromstring(book.read("xl/sharedStrings.xml"))
            shared = ["".join(n.text or "" for n in item.findall(".//main:t", NS))
                      for item in root.findall("main:si", NS)]
        root = ET.fromstring(book.read(first_sheet_path(book)))
    matrix = []
    for row in root.findall(".//main:sheetData/main:row", NS):
        values: list[str] = []
        for cell in row.findall("main:c", NS):
            index = column_index(cell.attrib.get("r", ""))
            values.extend([""] * (index - len(values)))
            values.append(cell_value(cell, shared))
        matrix.append(values)
    headers = matrix[0]
    missing = REQUIRED_COLUMNS - set(headers)
    if missing:
        raise ValueError(f"customer workbook missing columns: {sorted(missing)}")
    return [dict(zip(headers, row + [""] * (len(headers) - len(row))))
            for row in matrix[1:] if any(row)]


def read_source(source_zip: Path) -> tuple[list[dict[str, str]], set[str]]:
    with ZipFile(source_zip) as archive:
        workbooks = [item for item in archive.infolist()
                     if item.filename.lower().endswith(".xlsx")]
        if len(workbooks) != 1:
            raise ValueError(f"expected one workbook, found {len(workbooks)}")
        rows = read_workbook(archive.read(workbooks[0]))
        local_skcs = {
            Path(item.filename).stem for item in archive.infolist()
            if "/图包/" in item.filename and item.filename.lower().endswith(".jpg")
        }
    skcs = [row["SKC"].strip() for row in rows]
    if not all(skcs) or len(skcs) != len(set(skcs)):
        raise ValueError("customer SKCs must be non-empty and unique")
    if any(row["店铺名称"].strip().casefold() != "aloruh" for row in rows):
        raise ValueError("customer workbook contains a non-Aloruh row")
    return rows, local_skcs
