from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import BinaryIO
from xml.etree import ElementTree as ET

from diwan_signature.domain.contracts import PrintRequest


FLATTEN_TOLERANCE = 0.5
ARC_SEGMENTS = 72
SVG_UNIT_TO_MM = 25.4 / 96.0


@dataclass(frozen=True)
class PointD:
    x: float
    y: float


def convert_to_gcode(svg_stream: BinaryIO, req: PrintRequest) -> list[str]:
    root = _load_svg_root(svg_stream)

    min_x, min_y, svg_width, svg_height = _parse_view_box(root)
    unit_to_mm = _determine_unit_to_mm(root, svg_width, svg_height)

    offset_x = _parse_mm(req.x_position)
    offset_y = _parse_mm(req.y_position)
    scale = unit_to_mm * req.scale

    polylines: list[list[PointD]] = []
    _extract_paths(root, polylines)

    if not polylines:
        return []

    gcode: list[str] = []
    pen_is_down = False

    for polyline in polylines:
        if not polyline:
            continue

        for index, pt in enumerate(polyline):
            x = pt.x - min_x
            y = pt.y - min_y

            x *= scale
            y *= scale

            scaled_w = svg_width * scale
            scaled_h = svg_height * scale

            if req.invert_x:
                x = scaled_w - x
            if req.invert_y:
                y = scaled_h - y

            cx = scaled_w / 2.0
            cy = scaled_h / 2.0
            x, y = _rotate_point(x, y, cx, cy, req.rotation)

            final_x = offset_x + x
            final_y = offset_y + y

            if index == 0:
                if pen_is_down:
                    gcode.append("G1 E4.0 F4000")
                    pen_is_down = False

                gcode.append(f"G0 X{final_x:.3f} Y{final_y:.3f} F6000.0")
                gcode.append("G1 E8.0 F4000")
                pen_is_down = True
            else:
                gcode.append(f"G1 X{final_x:.3f} Y{final_y:.3f} F5000.0")

    if pen_is_down:
        gcode.append("G1 E0.0 F4000")

    return gcode


def _load_svg_root(svg_stream: BinaryIO) -> ET.Element:
    if hasattr(svg_stream, "seek"):
        svg_stream.seek(0)
    tree = ET.parse(svg_stream)
    return tree.getroot()


def _local_name(tag: str) -> str:
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def _parse_view_box(root: ET.Element) -> tuple[float, float, float, float]:
    min_x = 0.0
    min_y = 0.0
    width = 0.0
    height = 0.0

    view_box = root.attrib.get("viewBox")
    if view_box:
        parts = [p for p in re.split(r"[ ,]+", view_box.strip()) if p]
        if len(parts) == 4:
            min_x = _parse_double(parts[0])
            min_y = _parse_double(parts[1])
            width = _parse_double(parts[2])
            height = _parse_double(parts[3])
            return min_x, min_y, width, height

    width_attr = root.attrib.get("width")
    height_attr = root.attrib.get("height")
    if width_attr and height_attr:
        width = _parse_svg_length(width_attr)
        height = _parse_svg_length(height_attr)
        return min_x, min_y, width, height

    return min_x, min_y, 200.0, 200.0


def _determine_unit_to_mm(root: ET.Element, view_box_w: float, view_box_h: float) -> float:
    if view_box_w <= 0 or view_box_h <= 0:
        return SVG_UNIT_TO_MM

    width_attr = (root.attrib.get("width") or "").strip() or None
    height_attr = (root.attrib.get("height") or "").strip() or None

    from_width = _try_parse_explicit_mm(width_attr, view_box_w)
    if from_width is not None:
        return from_width

    from_height = _try_parse_explicit_mm(height_attr, view_box_h)
    if from_height is not None:
        return from_height

    return SVG_UNIT_TO_MM


def _try_parse_explicit_mm(attr: str | None, view_box_dim: float) -> float | None:
    if not attr or view_box_dim <= 0:
        return None
    if "%" in attr:
        return None

    attr = attr.strip()
    mm_value: float

    if attr.endswith("mm"):
        mm_value = _parse_double(attr[:-2])
    elif attr.endswith("cm"):
        mm_value = _parse_double(attr[:-2]) * 10.0
    elif attr.endswith("in"):
        mm_value = _parse_double(attr[:-2]) * 25.4
    elif attr.endswith("pt"):
        mm_value = _parse_double(attr[:-2]) * 25.4 / 72.0
    elif attr.endswith("px"):
        px = _parse_double(attr[:-2])
        if px <= 0:
            return None
        mm_value = px * SVG_UNIT_TO_MM
    else:
        px = _parse_double(attr)
        if px <= 0:
            return None
        mm_value = px * SVG_UNIT_TO_MM

    if mm_value <= 0:
        return None
    return mm_value / view_box_dim


def _extract_paths(element: ET.Element, polylines: list[list[PointD]]) -> None:
    for child in list(element):
        local_name = _local_name(child.tag)

        if local_name == "path":
            _extract_path_element(child, polylines)
        elif local_name == "line":
            _extract_line_element(child, polylines)
        elif local_name == "rect":
            _extract_rect_element(child, polylines)
        elif local_name == "circle":
            _extract_circle_element(child, polylines)
        elif local_name == "ellipse":
            _extract_ellipse_element(child, polylines)
        elif local_name == "polyline":
            _extract_polyline_element(child, polylines, close=False)
        elif local_name == "polygon":
            _extract_polyline_element(child, polylines, close=True)
        elif local_name == "defs":
            # Skip drawing content from defs.
            continue
        else:
            _extract_paths(child, polylines)


def _extract_path_element(path: ET.Element, polylines: list[list[PointD]]) -> None:
    d = path.attrib.get("d")
    if not d or not d.strip():
        return

    strokes = _parse_path_data(d)
    for stroke in strokes:
        if len(stroke) >= 1:
            polylines.append(stroke)


def _extract_line_element(el: ET.Element, polylines: list[list[PointD]]) -> None:
    x1 = _get_attr_double(el, "x1")
    y1 = _get_attr_double(el, "y1")
    x2 = _get_attr_double(el, "x2")
    y2 = _get_attr_double(el, "y2")
    polylines.append([PointD(x1, y1), PointD(x2, y2)])


def _extract_rect_element(el: ET.Element, polylines: list[list[PointD]]) -> None:
    w_str = el.attrib.get("width", "")
    h_str = el.attrib.get("height", "")
    if "%" in w_str or "%" in h_str:
        return

    x = _get_attr_double(el, "x")
    y = _get_attr_double(el, "y")
    w = _get_attr_double(el, "width")
    h = _get_attr_double(el, "height")

    if w <= 0 or h <= 0:
        return

    polylines.append(
        [
            PointD(x, y),
            PointD(x + w, y),
            PointD(x + w, y + h),
            PointD(x, y + h),
            PointD(x, y),
        ]
    )


def _extract_circle_element(el: ET.Element, polylines: list[list[PointD]]) -> None:
    cx = _get_attr_double(el, "cx")
    cy = _get_attr_double(el, "cy")
    r = _get_attr_double(el, "r")

    if r <= 0:
        return
    polylines.append(_approximate_ellipse(cx, cy, r, r))


def _extract_ellipse_element(el: ET.Element, polylines: list[list[PointD]]) -> None:
    cx = _get_attr_double(el, "cx")
    cy = _get_attr_double(el, "cy")
    rx = _get_attr_double(el, "rx")
    ry = _get_attr_double(el, "ry")

    if rx <= 0 or ry <= 0:
        return
    polylines.append(_approximate_ellipse(cx, cy, rx, ry))


def _extract_polyline_element(el: ET.Element, polylines: list[list[PointD]], close: bool) -> None:
    points = el.attrib.get("points")
    if not points or not points.strip():
        return

    nums = re.findall(r"-?[\d.]+(?:[eE][+-]?\d+)?", points)
    pts: list[PointD] = []
    for idx in range(0, len(nums) - 1, 2):
        pts.append(PointD(_parse_double(nums[idx]), _parse_double(nums[idx + 1])))

    if close and len(pts) >= 2:
        pts.append(pts[0])

    if len(pts) >= 2:
        polylines.append(pts)


def _approximate_ellipse(cx: float, cy: float, rx: float, ry: float) -> list[PointD]:
    pts: list[PointD] = []
    for i in range(ARC_SEGMENTS + 1):
        angle = 2.0 * math.pi * i / ARC_SEGMENTS
        pts.append(PointD(cx + rx * math.cos(angle), cy + ry * math.sin(angle)))
    return pts


def _parse_path_data(d: str) -> list[list[PointD]]:
    strokes: list[list[PointD]] = []
    current_stroke: list[PointD] = []
    tokens = _tokenize_path(d)

    cur_x = 0.0
    cur_y = 0.0
    start_x = 0.0
    start_y = 0.0
    last_cx = 0.0
    last_cy = 0.0
    last_cmd = " "

    i = 0
    while i < len(tokens):
        if len(tokens[i]) == 1 and tokens[i].isalpha():
            cmd = tokens[i]
            i += 1
        else:
            if last_cmd == "M":
                cmd = "L"
            elif last_cmd == "m":
                cmd = "l"
            else:
                cmd = last_cmd

        if not cmd.strip():
            i += 1
            continue

        is_relative = cmd.islower()
        cmd_upper = cmd.upper()

        if cmd_upper == "M":
            ok, args = _try_consume(tokens, i, 2)
            if not ok:
                break
            i += 2
            x, y = args
            if is_relative:
                x += cur_x
                y += cur_y

            if current_stroke:
                strokes.append(current_stroke)
            current_stroke = [PointD(x, y)]

            cur_x = x
            cur_y = y
            start_x = x
            start_y = y
            last_cx = cur_x
            last_cy = cur_y

        elif cmd_upper == "L":
            ok, args = _try_consume(tokens, i, 2)
            if not ok:
                break
            i += 2
            x, y = args
            if is_relative:
                x += cur_x
                y += cur_y

            current_stroke.append(PointD(x, y))
            cur_x = x
            cur_y = y
            last_cx = cur_x
            last_cy = cur_y

        elif cmd_upper == "H":
            ok, args = _try_consume(tokens, i, 1)
            if not ok:
                break
            i += 1
            x = args[0]
            if is_relative:
                x += cur_x

            current_stroke.append(PointD(x, cur_y))
            cur_x = x
            last_cx = cur_x
            last_cy = cur_y

        elif cmd_upper == "V":
            ok, args = _try_consume(tokens, i, 1)
            if not ok:
                break
            i += 1
            y = args[0]
            if is_relative:
                y += cur_y

            current_stroke.append(PointD(cur_x, y))
            cur_y = y
            last_cx = cur_x
            last_cy = cur_y

        elif cmd_upper == "C":
            ok, args = _try_consume(tokens, i, 6)
            if not ok:
                break
            i += 6
            x1, y1, x2, y2, x, y = args

            if is_relative:
                x1 += cur_x
                y1 += cur_y
                x2 += cur_x
                y2 += cur_y
                x += cur_x
                y += cur_y

            _flatten_cubic_bezier(current_stroke, cur_x, cur_y, x1, y1, x2, y2, x, y)
            last_cx = x2
            last_cy = y2
            cur_x = x
            cur_y = y

        elif cmd_upper == "S":
            ok, args = _try_consume(tokens, i, 4)
            if not ok:
                break
            i += 4
            x2, y2, x, y = args

            if is_relative:
                x2 += cur_x
                y2 += cur_y
                x += cur_x
                y += cur_y

            x1 = 2 * cur_x - last_cx
            y1 = 2 * cur_y - last_cy

            _flatten_cubic_bezier(current_stroke, cur_x, cur_y, x1, y1, x2, y2, x, y)
            last_cx = x2
            last_cy = y2
            cur_x = x
            cur_y = y

        elif cmd_upper == "Q":
            ok, args = _try_consume(tokens, i, 4)
            if not ok:
                break
            i += 4
            x1, y1, x, y = args

            if is_relative:
                x1 += cur_x
                y1 += cur_y
                x += cur_x
                y += cur_y

            _flatten_quadratic_bezier(current_stroke, cur_x, cur_y, x1, y1, x, y)
            last_cx = x1
            last_cy = y1
            cur_x = x
            cur_y = y

        elif cmd_upper == "T":
            ok, args = _try_consume(tokens, i, 2)
            if not ok:
                break
            i += 2
            x, y = args
            if is_relative:
                x += cur_x
                y += cur_y

            x1 = 2 * cur_x - last_cx
            y1 = 2 * cur_y - last_cy

            _flatten_quadratic_bezier(current_stroke, cur_x, cur_y, x1, y1, x, y)
            last_cx = x1
            last_cy = y1
            cur_x = x
            cur_y = y

        elif cmd_upper == "A":
            ok, args = _try_consume(tokens, i, 7)
            if not ok:
                break
            i += 7
            rx, ry, x_rotation, large_arc, sweep, x, y = args

            if is_relative:
                x += cur_x
                y += cur_y

            _flatten_arc(
                current_stroke,
                cur_x,
                cur_y,
                rx,
                ry,
                x_rotation,
                int(large_arc) != 0,
                int(sweep) != 0,
                x,
                y,
            )
            cur_x = x
            cur_y = y
            last_cx = cur_x
            last_cy = cur_y

        elif cmd_upper == "Z":
            if abs(cur_x - start_x) > 0.001 or abs(cur_y - start_y) > 0.001:
                current_stroke.append(PointD(start_x, start_y))

            cur_x = start_x
            cur_y = start_y
            last_cx = cur_x
            last_cy = cur_y

            if current_stroke:
                strokes.append(current_stroke)
            current_stroke = []

        else:
            i += 1

        last_cmd = cmd

    if current_stroke:
        strokes.append(current_stroke)

    return strokes


def _tokenize_path(d: str) -> list[str]:
    pattern = r"[MmLlHhVvCcSsQqTtAaZz]|-?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?"
    return re.findall(pattern, d)


def _try_consume(tokens: list[str], index: int, count: int) -> tuple[bool, list[float]]:
    if index + count > len(tokens):
        return False, []

    args: list[float] = []
    for j in range(count):
        token = tokens[index + j]
        if len(token) == 1 and token.isalpha():
            return False, []
        args.append(_parse_double(token))
    return True, args


def _flatten_cubic_bezier(
    pts: list[PointD],
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    x3: float,
    y3: float,
) -> None:
    _flatten_cubic_recursive(pts, x0, y0, x1, y1, x2, y2, x3, y3, depth=0)
    pts.append(PointD(x3, y3))


def _flatten_cubic_recursive(
    pts: list[PointD],
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    x3: float,
    y3: float,
    depth: int,
) -> None:
    if depth > 12:
        return

    dx = x3 - x0
    dy = y3 - y0
    d = math.sqrt(dx * dx + dy * dy)
    if d < 0.001:
        return

    d1 = abs((x1 - x3) * dy - (y1 - y3) * dx) / d
    d2 = abs((x2 - x3) * dy - (y2 - y3) * dx) / d
    if d1 + d2 <= FLATTEN_TOLERANCE:
        return

    x01 = (x0 + x1) / 2
    y01 = (y0 + y1) / 2
    x12 = (x1 + x2) / 2
    y12 = (y1 + y2) / 2
    x23 = (x2 + x3) / 2
    y23 = (y2 + y3) / 2
    x012 = (x01 + x12) / 2
    y012 = (y01 + y12) / 2
    x123 = (x12 + x23) / 2
    y123 = (y12 + y23) / 2
    x0123 = (x012 + x123) / 2
    y0123 = (y012 + y123) / 2

    _flatten_cubic_recursive(pts, x0, y0, x01, y01, x012, y012, x0123, y0123, depth + 1)
    pts.append(PointD(x0123, y0123))
    _flatten_cubic_recursive(pts, x0123, y0123, x123, y123, x23, y23, x3, y3, depth + 1)


def _flatten_quadratic_bezier(
    pts: list[PointD],
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
) -> None:
    cx1 = x0 + 2.0 / 3.0 * (x1 - x0)
    cy1 = y0 + 2.0 / 3.0 * (y1 - y0)
    cx2 = x2 + 2.0 / 3.0 * (x1 - x2)
    cy2 = y2 + 2.0 / 3.0 * (y1 - y2)
    _flatten_cubic_bezier(pts, x0, y0, cx1, cy1, cx2, cy2, x2, y2)


def _flatten_arc(
    pts: list[PointD],
    x1: float,
    y1: float,
    rx: float,
    ry: float,
    x_rotation_deg: float,
    large_arc: bool,
    sweep: bool,
    x2: float,
    y2: float,
) -> None:
    if abs(x1 - x2) < 0.001 and abs(y1 - y2) < 0.001:
        return

    rx = abs(rx)
    ry = abs(ry)
    if rx < 0.001 or ry < 0.001:
        pts.append(PointD(x2, y2))
        return

    phi = x_rotation_deg * math.pi / 180.0
    cos_phi = math.cos(phi)
    sin_phi = math.sin(phi)

    dx2 = (x1 - x2) / 2.0
    dy2 = (y1 - y2) / 2.0
    x1p = cos_phi * dx2 + sin_phi * dy2
    y1p = -sin_phi * dx2 + cos_phi * dy2

    x1p2 = x1p * x1p
    y1p2 = y1p * y1p
    rx2 = rx * rx
    ry2 = ry * ry
    lam = x1p2 / rx2 + y1p2 / ry2
    if lam > 1:
        sqrt_lam = math.sqrt(lam)
        rx *= sqrt_lam
        ry *= sqrt_lam
        rx2 = rx * rx
        ry2 = ry * ry

    num = rx2 * ry2 - rx2 * y1p2 - ry2 * x1p2
    den = rx2 * y1p2 + ry2 * x1p2
    if abs(den) < 1e-12:
        pts.append(PointD(x2, y2))
        return

    sq = max(0.0, num / den)
    sq_root = math.sqrt(sq) * (-1 if large_arc == sweep else 1)

    cxp = sq_root * rx * y1p / ry
    cyp = sq_root * -ry * x1p / rx

    cx = cos_phi * cxp - sin_phi * cyp + (x1 + x2) / 2.0
    cy = sin_phi * cxp + cos_phi * cyp + (y1 + y2) / 2.0

    theta1 = _angle_of(1, 0, (x1p - cxp) / rx, (y1p - cyp) / ry)
    d_theta = _angle_of(
        (x1p - cxp) / rx,
        (y1p - cyp) / ry,
        (-x1p - cxp) / rx,
        (-y1p - cyp) / ry,
    )

    if not sweep and d_theta > 0:
        d_theta -= 2 * math.pi
    if sweep and d_theta < 0:
        d_theta += 2 * math.pi

    segments = max(1, math.ceil(abs(d_theta) / (2 * math.pi) * ARC_SEGMENTS))
    for i in range(1, segments + 1):
        t = theta1 + d_theta * i / segments
        x_arc = rx * math.cos(t)
        y_arc = ry * math.sin(t)
        px = cos_phi * x_arc - sin_phi * y_arc + cx
        py = sin_phi * x_arc + cos_phi * y_arc + cy
        pts.append(PointD(px, py))


def _angle_of(ux: float, uy: float, vx: float, vy: float) -> float:
    dot = ux * vx + uy * vy
    length = math.sqrt((ux * ux + uy * uy) * (vx * vx + vy * vy))
    if length < 1e-12:
        return 0.0
    ratio = max(-1.0, min(1.0, dot / length))
    angle = math.acos(ratio)
    if ux * vy - uy * vx < 0:
        angle = -angle
    return angle


def _rotate_point(x: float, y: float, cx: float, cy: float, degrees: int) -> tuple[float, float]:
    if degrees == 0:
        return x, y

    rad = degrees * math.pi / 180.0
    cos_v = math.cos(rad)
    sin_v = math.sin(rad)
    dx = x - cx
    dy = y - cy
    return cx + dx * cos_v - dy * sin_v, cy + dx * sin_v + dy * cos_v


def _parse_mm(value: str) -> float:
    return _parse_double(value.replace("mm", "").strip())


def _parse_svg_length(value: str) -> float:
    value = value.strip()
    if value.endswith("px"):
        return _parse_double(value[:-2])
    if value.endswith("pt"):
        return _parse_double(value[:-2]) * 1.333
    if value.endswith("mm"):
        return _parse_double(value[:-2]) * 3.7795
    if value.endswith("cm"):
        return _parse_double(value[:-2]) * 37.795
    if value.endswith("in"):
        return _parse_double(value[:-2]) * 96.0
    return _parse_double(value)


def _get_attr_double(element: ET.Element, name: str) -> float:
    return _parse_double(element.attrib.get(name, "0"))


def _parse_double(value: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0

