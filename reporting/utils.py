from __future__ import annotations

import base64
import html
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Optional, Tuple


def fmt1(x: Optional[float]) -> str:
    """Format a number with 1 decimal place for display."""
    if x is None:
        return "—"
    try:
        return f"{float(x):.1f}"
    except Exception:
        return "—"


def fmt_pct1(x: Optional[float], signed: bool = True) -> str:
    """Format a percent value with 1 decimal place, optionally forcing sign."""
    if x is None:
        return "—"
    try:
        v = float(x)
    except Exception:
        return "—"
    sign = "+" if (signed and v >= 0) else ""
    return f"{sign}{v:.1f}%"


def fmt_prob_pct0(p: Optional[float]) -> str:
    """Format probability as a whole percent string (e.g., 97%)."""
    if p is None:
        return "—"
    try:
        return f"{float(p) * 100:.0f}%"
    except Exception:
        return "—"


def confidence_tier(p: Optional[float], *, shared: bool = False) -> Tuple[str, str]:
    """
    Map probability to (label, css_class) per contract.

    Returns:
      (label, css_class) where css_class is one of:
        - pill-high, pill-med, pill-low, pill-na
    """
    if shared:
        return ("SHARED", "pill-na")
    if p is None:
        return ("NOT RELIABLE", "pill-na")
    try:
        prob = float(p)
    except Exception:
        return ("NOT RELIABLE", "pill-na")
    if prob >= 0.95:
        return ("HIGH CONFIDENCE", "pill-high")
    if prob >= 0.80:
        return ("MODERATE", "pill-med")
    if prob >= 0.50:
        return ("LOW", "pill-low")
    return ("NOT RELIABLE", "pill-na")


def pill_html(p: Optional[float], *, shared: bool = False) -> str:
    label, cls = confidence_tier(p, shared=shared)
    # Keep pill label shorter in UI; preserve contract terms.
    short = {
        "HIGH CONFIDENCE": "HIGH CONFIDENCE",
        "MODERATE": "MODERATE",
        "LOW": "LOW",
        "NOT RELIABLE": "NOT RELIABLE",
        "SHARED": "SHARED",
    }[label]
    return f'<span class="pill {cls}">{html.escape(short)}</span>'


def embed_image_as_img_tag(path: Path, *, alt: str = "") -> str:
    """Return an <img> tag with an image embedded as base64 (png/jpg/jpeg/gif/webp)."""
    with open(path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("utf-8")
    alt_esc = html.escape(alt or path.name)
    ext = path.suffix.lower().lstrip(".")
    mime = {
        "png": "image/png",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "gif": "image/gif",
        "webp": "image/webp",
    }.get(ext, "application/octet-stream")
    return f'<img alt="{alt_esc}" src="data:{mime};base64,{encoded}" style="max-width:100%; height:auto;" />'


def json_for_script_tag(data: Any) -> str:
    """
    Dump JSON for embedding inside a <script type=\"application/json\"> tag.
    Escapes closing tags to avoid prematurely terminating the script element.
    """
    s = json.dumps(data, ensure_ascii=False)
    return s.replace("</", "<\\/")


def html_escape_text(s: Any) -> str:
    return html.escape("" if s is None else str(s))


@dataclass(frozen=True)
class TemplateReplacement:
    start: str
    end: str
    new_block: str


def replace_between(text: str, start: str, end: str, new_block: str) -> str:
    """
    Replace the text between `start` and `end` markers (markers kept).
    Raises ValueError if markers are missing or out of order.
    """
    i = text.find(start)
    if i < 0:
        raise ValueError(f"Start marker not found: {start!r}")
    j = text.find(end, i + len(start))
    if j < 0:
        raise ValueError(f"End marker not found: {end!r}")
    if j < i:
        raise ValueError("Markers out of order.")
    return text[: i + len(start)] + new_block + text[j:]


def replace_all(text: str, replacements: Mapping[str, str]) -> str:
    for k, v in replacements.items():
        text = text.replace(k, v)
    return text


def ensure_parent_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_text(path: Path, content: str) -> None:
    ensure_parent_dir(path)
    path.write_text(content, encoding="utf-8")

