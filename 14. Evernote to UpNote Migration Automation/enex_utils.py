#!/usr/bin/env python3
"""Shared helpers for reading Evernote .enex export files."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Optional

# ----- CONFIG -----
EVERNOTE_TIMESTAMP_FORMAT = "%Y%m%dT%H%M%SZ"
# ---------


@dataclass(frozen=True)
class EnexNote:
    title: str
    created_ms: Optional[int]
    updated_ms: Optional[int]


def parse_evernote_timestamp(value: str) -> Optional[int]:
    try:
        dt = datetime.strptime(value.strip(), EVERNOTE_TIMESTAMP_FORMAT).replace(tzinfo=timezone.utc)
    except ValueError:
        return None
    return int(dt.timestamp() * 1000)


def iter_notes(enex_path: Path) -> Iterator[EnexNote]:
    """Streams <note> elements so large .enex files (inline base64 PDFs) don't
    need to be held fully in memory."""
    for _, elem in ET.iterparse(str(enex_path), events=("end",)):
        if elem.tag != "note":
            continue
        title_el = elem.find("title")
        created_el = elem.find("created")
        updated_el = elem.find("updated")
        yield EnexNote(
            title=(title_el.text or "").strip() if title_el is not None else "",
            created_ms=parse_evernote_timestamp(created_el.text) if created_el is not None and created_el.text else None,
            updated_ms=parse_evernote_timestamp(updated_el.text) if updated_el is not None and updated_el.text else None,
        )
        elem.clear()


def iter_enex_files(path: Path) -> Iterator[Path]:
    if path.is_dir():
        yield from sorted(path.glob("*.enex"))
    else:
        yield path
