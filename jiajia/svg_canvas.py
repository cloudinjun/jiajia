from __future__ import annotations

import re
import tkinter as tk
from pathlib import Path
from xml.etree import ElementTree as ET


_NUMBER_RE = re.compile(r"-?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?")
_PATH_TOKEN_RE = re.compile(r"[MmLlHhVvCcQqAaZz]|-?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?")


def draw_svg_asset(
    canvas: tk.Canvas,
    path: Path,
    x: float,
    y: float,
    *,
    scale: float = 1.0,
    current_color: str = "#402A32",
) -> list[int]:
    if not path.exists():
        return []
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError:
        return []
    min_x, min_y, _width, _height = _viewbox(root)
    items: list[int] = []
    inherited = {
        key: value
        for key, value in root.attrib.items()
        if key in {"fill", "stroke", "stroke-width", "stroke-linecap", "stroke-linejoin"}
    }

    for element in root.iter():
        tag = _tag(element)
        if tag in {"svg", "defs", "clipPath", "g"}:
            continue
        original_attrib = dict(element.attrib)
        if inherited:
            merged = dict(inherited)
            merged.update(original_attrib)
            element.attrib.clear()
            element.attrib.update(merged)
        if tag == "path":
            items.extend(_draw_path(canvas, element, x, y, scale, min_x, min_y, current_color))
        elif tag == "rect":
            item = _draw_rect(canvas, element, x, y, scale, min_x, min_y, current_color)
            if item:
                items.append(item)
        elif tag == "circle":
            item = _draw_circle(canvas, element, x, y, scale, min_x, min_y, current_color)
            if item:
                items.append(item)
        elif tag == "ellipse":
            item = _draw_ellipse(canvas, element, x, y, scale, min_x, min_y, current_color)
            if item:
                items.append(item)
        elif tag == "line":
            item = _draw_line(canvas, element, x, y, scale, min_x, min_y, current_color)
            if item:
                items.append(item)
        elif tag in {"polyline", "polygon"}:
            item = _draw_poly(canvas, element, x, y, scale, min_x, min_y, current_color, closed=(tag == "polygon"))
            if item:
                items.append(item)
        if inherited:
            element.attrib.clear()
            element.attrib.update(original_attrib)
    return items


def _viewbox(root: ET.Element) -> tuple[float, float, float, float]:
    raw = root.attrib.get("viewBox") or root.attrib.get("viewbox") or ""
    values = [float(value) for value in _NUMBER_RE.findall(raw)]
    if len(values) >= 4:
        return values[0], values[1], values[2], values[3]
    return 0.0, 0.0, _float(root.attrib.get("width"), 48.0), _float(root.attrib.get("height"), 48.0)


def _draw_path(
    canvas: tk.Canvas,
    element: ET.Element,
    x: float,
    y: float,
    scale: float,
    min_x: float,
    min_y: float,
    current_color: str,
) -> list[int]:
    subpaths = _parse_path(element.attrib.get("d", ""))
    if not subpaths:
        return []
    fill = _color(element.attrib.get("fill"), current_color)
    stroke = _color(element.attrib.get("stroke"), current_color)
    width = _float(element.attrib.get("stroke-width"), 1.0) * scale
    items: list[int] = []
    for points, closed in subpaths:
        coords = _coords(points, x, y, scale, min_x, min_y)
        if len(coords) < 4:
            continue
        if fill and (closed or len(coords) >= 6):
            item = canvas.create_polygon(
                *coords,
                fill=fill,
                outline=stroke or "",
                width=width if stroke else 1,
                smooth=False,
                joinstyle=_joinstyle(element),
            )
        elif stroke:
            if closed:
                coords = [*coords, coords[0], coords[1]]
            item = canvas.create_line(
                *coords,
                fill=stroke,
                width=max(1.0, width),
                capstyle=_capstyle(element),
                joinstyle=_joinstyle(element),
                smooth=False,
            )
        else:
            continue
        items.append(item)
    return items


def _draw_rect(
    canvas: tk.Canvas,
    element: ET.Element,
    x: float,
    y: float,
    scale: float,
    min_x: float,
    min_y: float,
    current_color: str,
) -> int | None:
    x1 = x + (_float(element.attrib.get("x")) - min_x) * scale
    y1 = y + (_float(element.attrib.get("y")) - min_y) * scale
    x2 = x1 + _float(element.attrib.get("width")) * scale
    y2 = y1 + _float(element.attrib.get("height")) * scale
    fill = _color(element.attrib.get("fill"), current_color)
    stroke = _color(element.attrib.get("stroke"), current_color)
    width = max(1.0, _float(element.attrib.get("stroke-width"), 1.0) * scale) if stroke else 1
    rx = max(_float(element.attrib.get("rx")), _float(element.attrib.get("ry"))) * scale
    if rx > 0:
        return _rounded_rect(canvas, x1, y1, x2, y2, rx, fill=fill or "", outline=stroke or "", width=width)
    return canvas.create_rectangle(x1, y1, x2, y2, fill=fill or "", outline=stroke or "", width=width)


def _draw_circle(
    canvas: tk.Canvas,
    element: ET.Element,
    x: float,
    y: float,
    scale: float,
    min_x: float,
    min_y: float,
    current_color: str,
) -> int | None:
    cx = x + (_float(element.attrib.get("cx")) - min_x) * scale
    cy = y + (_float(element.attrib.get("cy")) - min_y) * scale
    r = _float(element.attrib.get("r")) * scale
    return _oval(canvas, cx - r, cy - r, cx + r, cy + r, element, scale, current_color)


def _draw_ellipse(
    canvas: tk.Canvas,
    element: ET.Element,
    x: float,
    y: float,
    scale: float,
    min_x: float,
    min_y: float,
    current_color: str,
) -> int | None:
    cx = x + (_float(element.attrib.get("cx")) - min_x) * scale
    cy = y + (_float(element.attrib.get("cy")) - min_y) * scale
    rx = _float(element.attrib.get("rx")) * scale
    ry = _float(element.attrib.get("ry")) * scale
    return _oval(canvas, cx - rx, cy - ry, cx + rx, cy + ry, element, scale, current_color)


def _draw_line(
    canvas: tk.Canvas,
    element: ET.Element,
    x: float,
    y: float,
    scale: float,
    min_x: float,
    min_y: float,
    current_color: str,
) -> int | None:
    stroke = _color(element.attrib.get("stroke"), current_color)
    if not stroke:
        return None
    coords = [
        x + (_float(element.attrib.get("x1")) - min_x) * scale,
        y + (_float(element.attrib.get("y1")) - min_y) * scale,
        x + (_float(element.attrib.get("x2")) - min_x) * scale,
        y + (_float(element.attrib.get("y2")) - min_y) * scale,
    ]
    return canvas.create_line(
        *coords,
        fill=stroke,
        width=max(1.0, _float(element.attrib.get("stroke-width"), 1.0) * scale),
        capstyle=_capstyle(element),
        joinstyle=_joinstyle(element),
    )


def _draw_poly(
    canvas: tk.Canvas,
    element: ET.Element,
    x: float,
    y: float,
    scale: float,
    min_x: float,
    min_y: float,
    current_color: str,
    *,
    closed: bool,
) -> int | None:
    values = [float(value) for value in _NUMBER_RE.findall(element.attrib.get("points", ""))]
    if len(values) < 4:
        return None
    coords: list[float] = []
    for index in range(0, len(values), 2):
        coords.extend((x + (values[index] - min_x) * scale, y + (values[index + 1] - min_y) * scale))
    fill = _color(element.attrib.get("fill"), current_color)
    stroke = _color(element.attrib.get("stroke"), current_color)
    width = max(1.0, _float(element.attrib.get("stroke-width"), 1.0) * scale)
    if closed:
        return canvas.create_polygon(*coords, fill=fill or "", outline=stroke or "", width=width, joinstyle=_joinstyle(element))
    if not stroke:
        return None
    return canvas.create_line(*coords, fill=stroke, width=width, capstyle=_capstyle(element), joinstyle=_joinstyle(element))


def _oval(
    canvas: tk.Canvas,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    element: ET.Element,
    scale: float,
    current_color: str,
) -> int | None:
    fill = _color(element.attrib.get("fill"), current_color)
    stroke = _color(element.attrib.get("stroke"), current_color)
    width = max(1.0, _float(element.attrib.get("stroke-width"), 1.0) * scale) if stroke else 1
    return canvas.create_oval(x1, y1, x2, y2, fill=fill or "", outline=stroke or "", width=width)


def _parse_path(d: str) -> list[tuple[list[tuple[float, float]], bool]]:
    tokens = _PATH_TOKEN_RE.findall(d)
    index = 0
    command = ""
    current = (0.0, 0.0)
    start = (0.0, 0.0)
    points: list[tuple[float, float]] = []
    subpaths: list[tuple[list[tuple[float, float]], bool]] = []

    def has_number() -> bool:
        return index < len(tokens) and not re.match(r"^[A-Za-z]$", tokens[index])

    def number() -> float:
        nonlocal index
        value = float(tokens[index])
        index += 1
        return value

    def flush(closed: bool = False) -> None:
        nonlocal points
        if len(points) >= 2:
            subpaths.append((points, closed))
        points = []

    while index < len(tokens):
        if re.match(r"^[A-Za-z]$", tokens[index]):
            command = tokens[index]
            index += 1
        if not command:
            break
        relative = command.islower()
        cmd = command.upper()

        if cmd == "M":
            first = True
            while has_number():
                x = number()
                y = number()
                if relative:
                    x += current[0]
                    y += current[1]
                current = (x, y)
                if first:
                    flush(False)
                    points = [current]
                    start = current
                    first = False
                else:
                    points.append(current)
            command = "l" if relative else "L"
        elif cmd == "L":
            while has_number():
                x = number()
                y = number()
                if relative:
                    x += current[0]
                    y += current[1]
                current = (x, y)
                points.append(current)
        elif cmd == "H":
            while has_number():
                x = number()
                if relative:
                    x += current[0]
                current = (x, current[1])
                points.append(current)
        elif cmd == "V":
            while has_number():
                y = number()
                if relative:
                    y += current[1]
                current = (current[0], y)
                points.append(current)
        elif cmd == "C":
            while has_number():
                c1 = (number(), number())
                c2 = (number(), number())
                end = (number(), number())
                if relative:
                    c1 = (c1[0] + current[0], c1[1] + current[1])
                    c2 = (c2[0] + current[0], c2[1] + current[1])
                    end = (end[0] + current[0], end[1] + current[1])
                points.extend(_cubic_points(current, c1, c2, end))
                current = end
        elif cmd == "Q":
            while has_number():
                c = (number(), number())
                end = (number(), number())
                if relative:
                    c = (c[0] + current[0], c[1] + current[1])
                    end = (end[0] + current[0], end[1] + current[1])
                points.extend(_quadratic_points(current, c, end))
                current = end
        elif cmd == "A":
            while has_number():
                _rx = number()
                _ry = number()
                _rotation = number()
                _large_arc = number()
                _sweep = number()
                x = number()
                y = number()
                if relative:
                    x += current[0]
                    y += current[1]
                current = (x, y)
                points.append(current)
        elif cmd == "Z":
            if points and points[-1] != start:
                points.append(start)
            flush(True)
            current = start
            command = ""
        else:
            break
    flush(False)
    return subpaths


def _cubic_points(
    p0: tuple[float, float],
    p1: tuple[float, float],
    p2: tuple[float, float],
    p3: tuple[float, float],
    steps: int = 10,
) -> list[tuple[float, float]]:
    result: list[tuple[float, float]] = []
    for step in range(1, steps + 1):
        t = step / steps
        mt = 1.0 - t
        result.append(
            (
                mt ** 3 * p0[0] + 3 * mt ** 2 * t * p1[0] + 3 * mt * t ** 2 * p2[0] + t ** 3 * p3[0],
                mt ** 3 * p0[1] + 3 * mt ** 2 * t * p1[1] + 3 * mt * t ** 2 * p2[1] + t ** 3 * p3[1],
            )
        )
    return result


def _quadratic_points(
    p0: tuple[float, float],
    p1: tuple[float, float],
    p2: tuple[float, float],
    steps: int = 8,
) -> list[tuple[float, float]]:
    result: list[tuple[float, float]] = []
    for step in range(1, steps + 1):
        t = step / steps
        mt = 1.0 - t
        result.append((mt * mt * p0[0] + 2 * mt * t * p1[0] + t * t * p2[0], mt * mt * p0[1] + 2 * mt * t * p1[1] + t * t * p2[1]))
    return result


def _coords(
    points: list[tuple[float, float]],
    x: float,
    y: float,
    scale: float,
    min_x: float,
    min_y: float,
) -> list[float]:
    coords: list[float] = []
    for px, py in points:
        coords.extend((x + (px - min_x) * scale, y + (py - min_y) * scale))
    return coords


def _rounded_rect(
    canvas: tk.Canvas,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    radius: float,
    *,
    fill: str,
    outline: str,
    width: float,
) -> int:
    radius = min(radius, abs(x2 - x1) / 2, abs(y2 - y1) / 2)
    points = [
        x1 + radius, y1,
        x2 - radius, y1,
        x2, y1,
        x2, y1 + radius,
        x2, y2 - radius,
        x2, y2,
        x2 - radius, y2,
        x1 + radius, y2,
        x1, y2,
        x1, y2 - radius,
        x1, y1 + radius,
        x1, y1,
    ]
    return canvas.create_polygon(points, fill=fill, outline=outline, width=width, smooth=True, splinesteps=8)


def _color(value: str | None, current_color: str) -> str:
    if value is None:
        return ""
    value = value.strip()
    if not value or value.lower() == "none":
        return ""
    if value.lower() == "currentcolor":
        return current_color
    return value


def _capstyle(element: ET.Element) -> str:
    value = element.attrib.get("stroke-linecap", "butt").lower()
    if value in {"round", "projecting"}:
        return tk.ROUND if value == "round" else tk.PROJECTING
    return tk.BUTT


def _joinstyle(element: ET.Element) -> str:
    value = element.attrib.get("stroke-linejoin", "miter").lower()
    if value == "round":
        return tk.ROUND
    if value == "bevel":
        return tk.BEVEL
    return tk.MITER


def _tag(element: ET.Element) -> str:
    return element.tag.rsplit("}", 1)[-1]


def _float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
