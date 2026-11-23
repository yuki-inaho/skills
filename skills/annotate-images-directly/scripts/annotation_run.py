#!/usr/bin/env python3
"""Reference-free geometry, SVG inspection, and file-integrity helpers.

This module does not validate a task's JSON Schema, identify image content, or
score annotations. Coordinates and raster conventions must come from the task.
All commands use only the Python standard library and make no network calls.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import math
import os
import struct
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape, quoteattr


Point = tuple[Fraction, Fraction]
Box = tuple[Fraction, Fraction, Fraction, Fraction]
FREEZE_FORMAT = "annotation-freeze-v1"
SVG_NAMESPACE = "http://www.w3.org/2000/svg"


def _unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def _invalid_constant(value: str) -> None:
    raise ValueError(f"Non-JSON numeric constant: {value}")


def _json_bytes(data: bytes, *, strict_numbers: bool = True) -> Any:
    options: dict[str, Any] = {"object_pairs_hook": _unique_pairs}
    if strict_numbers:
        options["parse_constant"] = _invalid_constant
    return json.loads(data.decode("utf-8"), **options)


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"


def _write_new(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        stream.write(text)


def _number(value: Any) -> Fraction | None:
    if type(value) not in (int, float):
        return None
    try:
        if not math.isfinite(value):
            return None
    except OverflowError:
        return None
    return Fraction(value)


def _coordinates(value: Any, keys: tuple[str, ...]) -> tuple[Fraction, ...]:
    if isinstance(value, dict):
        raw = [value.get(key) for key in keys]
    elif isinstance(value, list) and len(value) == len(keys):
        raw = value
    else:
        raise ValueError(f"Expected coordinates {', '.join(keys)}")
    numbers = tuple(_number(item) for item in raw)
    if any(item is None for item in numbers):
        raise ValueError("Coordinates must be finite numbers; booleans are not coordinates")
    return numbers  # type: ignore[return-value]


def _cross(a: Point, b: Point, c: Point) -> Fraction:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _edges(polygon: tuple[Point, ...]) -> list[tuple[Point, Point]]:
    return list(zip(polygon, polygon[1:] + polygon[:1]))


def _twice_area(polygon: tuple[Point, ...]) -> Fraction:
    return sum((a[0] * b[1] - b[0] * a[1] for a, b in _edges(polygon)), Fraction())


def _on_segment(a: Point, b: Point, p: Point) -> bool:
    return (
        _cross(a, b, p) == 0
        and min(a[0], b[0]) <= p[0] <= max(a[0], b[0])
        and min(a[1], b[1]) <= p[1] <= max(a[1], b[1])
    )


def _segments_touch(a: Point, b: Point, c: Point, d: Point) -> bool:
    first, second = _cross(a, b, c), _cross(a, b, d)
    third, fourth = _cross(c, d, a), _cross(c, d, b)
    if first * second < 0 and third * fourth < 0:
        return True
    return (
        (first == 0 and _on_segment(a, b, c))
        or (second == 0 and _on_segment(a, b, d))
        or (third == 0 and _on_segment(c, d, a))
        or (fourth == 0 and _on_segment(c, d, b))
    )


def _point_in_polygon(point: Point, polygon: tuple[Point, ...], *, boundary: bool) -> bool:
    winding = 0
    for a, b in _edges(polygon):
        if _on_segment(a, b, point):
            return boundary
        if a[1] <= point[1] < b[1] and _cross(a, b, point) > 0:
            winding += 1
        elif b[1] <= point[1] < a[1] and _cross(a, b, point) < 0:
            winding -= 1
    return winding != 0


def _envelope(points: tuple[Point, ...]) -> Box:
    return min(p[0] for p in points), min(p[1] for p in points), max(p[0] for p in points), max(p[1] for p in points)


def _box_contains(box: Box, points: tuple[Point, ...]) -> bool:
    return all(box[0] <= x <= box[2] and box[1] <= y <= box[3] for x, y in points)


def _canonical_polygon(polygon: tuple[Point, ...]) -> tuple[Point, ...]:
    # Redundant straight-through vertices do not change a region's outline.
    reduced = tuple(
        point for i, point in enumerate(polygon)
        if _cross(polygon[i - 1], point, polygon[(i + 1) % len(polygon)]) != 0
    )
    if not reduced:
        return polygon
    forward = min(reduced[i:] + reduced[:i] for i in range(len(reduced)))
    reverse = reduced[::-1]
    backward = min(reverse[i:] + reverse[:i] for i in range(len(reverse)))
    return min(forward, backward)


@dataclass(frozen=True)
class Shape:
    index: int
    label: str
    point: Point | None
    bbox: Box | None
    polygon: tuple[Point, ...] | None


def _issue(report: dict[str, Any], kind: str, code: str, message: str, index: int | None = None) -> None:
    issue: dict[str, Any] = {"code": code, "message": message}
    if index is not None:
        issue["object"] = index
    report[kind].append(issue)


def _read_shape(obj: Any, index: int, report: dict[str, Any], x_max: Fraction, y_max: Fraction) -> Shape | None:
    if not isinstance(obj, dict):
        _issue(report, "errors", "invalid_object", "An object must contain coordinate fields", index)
        return None
    if not any(key in obj for key in ("point", "bbox", "polygon")):
        _issue(report, "errors", "missing_geometry", "No point, bbox, or polygon was supplied", index)
        return None
    try:
        point = _coordinates(obj["point"], ("x", "y")) if "point" in obj else None
        bbox = _coordinates(obj["bbox"], ("xmin", "ymin", "xmax", "ymax")) if "bbox" in obj else None
        polygon = None
        if "polygon" in obj:
            raw = obj["polygon"]
            if not isinstance(raw, list) or len(raw) < 3:
                raise ValueError("A polygon needs at least three vertices")
            polygon = tuple(_coordinates(p, ("x", "y")) for p in raw)
    except ValueError as exc:
        _issue(report, "errors", "invalid_coordinates", str(exc), index)
        return None
    points = (() if point is None else (point,)) + (() if polygon is None else polygon)
    if bbox is not None:
        points += ((bbox[0], bbox[1]), (bbox[2], bbox[3]))
    if any(not (0 <= x <= x_max and 0 <= y <= y_max) for x, y in points):
        _issue(report, "errors", "out_of_bounds", "Coordinates exceed the declared inclusive axis bounds", index)
        return None
    label = str(obj.get("class", obj.get("class_id", obj.get("id", index))))
    return Shape(index, label, point, bbox, polygon)  # type: ignore[arg-type]


def _check_shape(shape: Shape, report: dict[str, Any], point_location: str) -> None:
    polygon, box, point, index = shape.polygon, shape.bbox, shape.point, shape.index
    if box is not None and (box[0] >= box[2] or box[1] >= box[3]):
        _issue(report, "errors", "invalid_bbox", "A bbox must have positive width and height", index)
    if polygon is not None:
        if len(set(polygon)) != len(polygon):
            _issue(report, "errors", "duplicate_vertex", "Do not repeat vertices, including the closing vertex", index)
        if _twice_area(polygon) == 0:
            _issue(report, "errors", "zero_area", "The polygon has zero signed area", index)
        for i, current in enumerate(polygon):
            before, after = polygon[i - 1], polygon[(i + 1) % len(polygon)]
            dot = (current[0] - before[0]) * (after[0] - current[0]) + (current[1] - before[1]) * (after[1] - current[1])
            if _cross(before, current, after) == 0 and dot < 0:
                _issue(report, "errors", "adjacent_backtrack", "Adjacent edges reverse over the same segment", index)
                break
        edges = _edges(polygon)
        crossing = any(
            _segments_touch(a, b, c, d)
            for i, (a, b) in enumerate(edges)
            for j, (c, d) in enumerate(edges[i + 1:], i + 1)
            if j != i + 1 and (i, j) != (0, len(edges) - 1)
        )
        if crossing:
            _issue(report, "errors", "self_intersection", "Non-adjacent edges intersect or touch", index)
        if point is not None and point_location != "any":
            if not _point_in_polygon(point, polygon, boundary=point_location == "covered"):
                _issue(report, "errors", "point_location", f"The point does not meet the {point_location} polygon rule", index)
    if box is not None:
        enclosed = (() if polygon is None else polygon) + (() if point is None else (point,))
        if not _box_contains(box, enclosed):
            _issue(report, "errors", "bbox_enclosure", "The bbox does not enclose the associated point or polygon", index)
        elif polygon is not None and box != _envelope(polygon):
            _issue(report, "warnings", "bbox_padding", "The bbox extends beyond the polygon envelope; inspect task tolerance", index)


def _regions_contact(first: Shape, second: Shape) -> bool:
    assert first.polygon is not None and second.polygon is not None
    a, b = _envelope(first.polygon), _envelope(second.polygon)
    if a[2] < b[0] or b[2] < a[0] or a[3] < b[1] or b[3] < a[1]:
        return False
    if _point_in_polygon(first.polygon[0], second.polygon, boundary=True) or _point_in_polygon(second.polygon[0], first.polygon, boundary=True):
        return True
    return any(_segments_touch(a, b, c, d) for a, b in _edges(first.polygon) for c, d in _edges(second.polygon))


def _pixel_point(point: Point, args: argparse.Namespace, *, overlay: bool) -> Point:
    spans = (args.width - 1, args.height - 1) if args.coordinate_frame == "pixel-centers" else (args.width, args.height)
    offset = Fraction(1, 2) if overlay and args.coordinate_frame == "pixel-centers" else Fraction()
    return (
        point[0] * spans[0] / Fraction(args.x_max) + offset,
        point[1] * spans[1] / Fraction(args.y_max) + offset,
    )


def geometry(data: Any, args: argparse.Namespace) -> tuple[dict[str, Any], list[Shape]]:
    """Check coordinate geometry only; leave category and schema rules to the task."""
    report: dict[str, Any] = {"ok": False, "errors": [], "warnings": [], "object_count": 0}
    objects = data.get("objects") if isinstance(data, dict) else data
    if not isinstance(objects, list):
        _issue(report, "errors", "invalid_objects", "Expected an objects list or a top-level list")
        return report, []
    report["object_count"] = len(objects)
    shapes: list[Shape] = []
    valid_regions: list[Shape] = []
    for index, obj in enumerate(objects):
        shape = _read_shape(obj, index, report, Fraction(args.x_max), Fraction(args.y_max))
        if shape is None:
            continue
        errors_before = len(report["errors"])
        _check_shape(shape, report, args.point_location)
        shapes.append(shape)
        if len(report["errors"]) != errors_before or shape.polygon is None:
            continue
        valid_regions.append(shape)
        if args.width is not None:
            rounded = tuple(tuple(Fraction(round(v)) for v in _pixel_point(point, args, overlay=False)) for point in shape.polygon)
            if len(set(rounded)) != len(rounded) or _twice_area(rounded) == 0:
                _issue(report, "warnings", "rounded_pixel_degeneracy", "Nearest-integer pixel vertices collapse or lose area; inspect the task rasterizer without deleting the region", index)
    for i, first in enumerate(valid_regions):
        for second in valid_regions[i + 1:]:
            if _canonical_polygon(first.polygon) == _canonical_polygon(second.polygon):
                _issue(report, "warnings", "duplicate_region", f"Same polygon region as object {first.index}; labels are not used to remove it", second.index)
            elif _regions_contact(first, second):
                _issue(report, "warnings", "region_contact_or_overlap", f"Boundary contact or overlap with object {first.index}; resolve using the task contract", second.index)
    report["ok"] = not report["errors"]
    return report, shapes


def _image_info(data: bytes) -> tuple[str, int, int]:
    """Read raster header dimensions, without claiming a full image decode."""
    if data.startswith(b"\x89PNG\r\n\x1a\n") and len(data) >= 24 and data[12:16] == b"IHDR":
        width, height = struct.unpack(">II", data[16:24])
        return "image/png", width, height
    if data[:6] in (b"GIF87a", b"GIF89a") and len(data) >= 10:
        width, height = struct.unpack("<HH", data[6:10])
        return "image/gif", width, height
    if data.startswith(b"\xff\xd8"):
        offset = 2
        frames = {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}
        while offset < len(data):
            if data[offset] != 0xFF:
                break
            while offset < len(data) and data[offset] == 0xFF:
                offset += 1
            if offset >= len(data):
                break
            marker = data[offset]
            offset += 1
            if marker in (0xD9, 0xDA):
                break
            if marker == 0x01 or 0xD0 <= marker <= 0xD8:
                continue
            if offset + 2 > len(data):
                break
            length = int.from_bytes(data[offset:offset + 2], "big")
            if length < 2 or offset + length > len(data):
                break
            if marker in frames and length >= 7:
                height, width = struct.unpack(">HH", data[offset + 3:offset + 7])
                return "image/jpeg", width, height
            offset += length
    raise ValueError("Expected a PNG, JPEG, or GIF with readable raster dimensions; orient the image before annotation")


def _svg_number(value: Fraction | float) -> str:
    return format(float(value), ".10g")


def overlay(data: Any, args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    report, shapes = geometry(data, args)
    if not report["ok"]:
        return report, 1
    image_data = args.image.read_bytes()
    mime, width, height = _image_info(image_data)
    if (width, height) != (args.width, args.height):
        raise ValueError(f"Declared image dimensions {args.width}x{args.height} differ from the raster header {width}x{height}")
    details = f"image={width}x{height}; x=[0,{args.x_max:g}]; y=[0,{args.y_max:g}]; frame={args.coordinate_frame}; image_sha256={_digest(image_data)}"
    encoded = base64.b64encode(image_data).decode("ascii")
    lines = [
        f'<svg xmlns="{SVG_NAMESPACE}" width="{width}" height="{height + 42}" viewBox="0 0 {width} {height + 42}">',
        f"<title>Annotation inspection</title><desc>{escape(details)}</desc>",
        f'<image x="0" y="0" width="{width}" height="{height}" preserveAspectRatio="none" href="data:{mime};base64,{encoded}"/>',
    ]
    colors = ("#ef4444", "#2563eb", "#059669", "#9333ea", "#d97706")
    radius = max(1.5, min(width, height) / 180)
    for shape in shapes:
        color = colors[shape.index % len(colors)]
        lines.append(f'<g id="object-{shape.index}" stroke="{color}" stroke-width="1.5">')
        anchor = (Fraction(), Fraction())
        if shape.polygon is not None:
            points = [_pixel_point(p, args, overlay=True) for p in shape.polygon]
            coordinates = " ".join(f"{_svg_number(x)},{_svg_number(y)}" for x, y in points)
            lines.append(f'<polygon points="{coordinates}" fill="{color}" fill-opacity="0.18"/>')
            anchor = points[0]
        if shape.bbox is not None:
            box = shape.bbox
            lower = _pixel_point((box[0], box[1]), args, overlay=True)
            upper = _pixel_point((box[2], box[3]), args, overlay=True)
            lines.append(f'<rect x="{_svg_number(lower[0])}" y="{_svg_number(lower[1])}" width="{_svg_number(upper[0] - lower[0])}" height="{_svg_number(upper[1] - lower[1])}" fill="none" stroke-dasharray="4 3"/>')
            anchor = lower
        if shape.point is not None:
            center = _pixel_point(shape.point, args, overlay=True)
            lines.append(f'<circle cx="{_svg_number(center[0])}" cy="{_svg_number(center[1])}" r="{radius:g}" fill="{color}"/>')
            if shape.polygon is None and shape.bbox is None:
                anchor = center
        label = escape(f"{shape.index}: {shape.label}")
        lines.append(f'<text x="{_svg_number(anchor[0] + 3)}" y="{_svg_number(max(Fraction(12), anchor[1] - 3))}" font-size="12" fill="{color}" stroke="white" stroke-width="2" paint-order="stroke">{label}</text></g>')
    lines.extend([
        f'<rect x="0" y="{height}" width="{width}" height="42" fill="white"/>',
        f'<text x="4" y="{height + 15}" font-size="11">{escape(f"image {width} x {height}; x max {args.x_max:g}; y max {args.y_max:g}")}</text>',
        f'<text x="4" y="{height + 31}" font-size="11">{escape(args.coordinate_frame)}; geometry is not semantic quality</text>',
        "</svg>\n",
    ])
    _write_new(args.output, "\n".join(lines))
    report["output"] = str(args.output)
    return report, 0


def _absolute(path: Path) -> Path:
    # Keep a symlink's lexical path so retargeting it remains observable.
    return Path(os.path.abspath(path))


def _record_file(identifier: str, path: Path | None, base: Path, *, answer: bool = False) -> dict[str, Any]:
    record: dict[str, Any] = {"id": identifier, "path": None, "status": "unsubmitted", "sha256": None, "size": None}
    if path is None:
        return record
    record["path"] = os.path.relpath(path, base)
    try:
        data = path.read_bytes()
    except FileNotFoundError:
        record["status"] = "missing"
        return record
    except OSError as exc:
        record["status"] = "unreadable"
        record["reason"] = type(exc).__name__
        return record
    record.update(status="recorded", sha256=_digest(data), size=len(data))
    if answer:
        try:
            _json_bytes(data)
        except (UnicodeError, ValueError):
            record["status"] = "invalid_json"
    return record


def _read_plan(path: Path) -> dict[str, Any]:
    plan = _json_bytes(path.read_bytes())
    if not isinstance(plan, dict):
        raise ValueError("A freeze plan must be an object")
    permitted = {"run_id", "expected_answer_ids", "inputs", "settings", "answers"}
    if set(plan) - permitted:
        raise ValueError("The freeze plan contains unsupported fields; prepare an explicit file allowlist")
    expected = plan.get("expected_answer_ids")
    if not isinstance(expected, list) or not expected or any(not isinstance(item, str) or not item for item in expected):
        raise ValueError("expected_answer_ids must be a nonempty list of nonempty strings")
    if len(set(expected)) != len(expected):
        raise ValueError("expected_answer_ids contains duplicate IDs")
    if "run_id" in plan and not isinstance(plan["run_id"], str):
        raise ValueError("run_id must be a string")
    for role in ("inputs", "settings", "answers"):
        mapping = plan.get(role)
        if not isinstance(mapping, dict) or (role != "answers" and not mapping):
            raise ValueError(f"{role} must be a file mapping; inputs and settings cannot be empty")
        for key, value in mapping.items():
            if not key or not isinstance(value, str) and not (role == "answers" and value is None):
                raise ValueError(f"Invalid file entry in {role}")
            if value == "":
                raise ValueError(f"Empty path in {role}")
    if set(plan["answers"]) - set(expected):
        raise ValueError("answers contains IDs outside expected_answer_ids")
    return plan


def freeze(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    plan_path, output = _absolute(args.plan), _absolute(args.output)
    plan = _read_plan(plan_path)
    files: dict[str, list[dict[str, Any]]] = {}
    for role in ("inputs", "settings", "answers"):
        mapping = plan[role]
        identifiers = plan["expected_answer_ids"] if role == "answers" else list(mapping)
        files[role] = []
        for identifier in identifiers:
            value = mapping.get(identifier)
            path = _absolute(plan_path.parent / value) if value is not None else None
            if path == output:
                raise ValueError("The freeze output cannot be one of the recorded input, setting, or answer paths")
            files[role].append(_record_file(identifier, path, output.parent, answer=role == "answers"))
    if output == plan_path:
        raise ValueError("The freeze output cannot replace its plan")
    plan_record = _record_file("plan", plan_path, output.parent)
    complete = all(record["status"] == "recorded" for records in files.values() for record in records) and plan_record["status"] == "recorded"
    manifest = {
        "format": FREEZE_FORMAT,
        "run_id": plan.get("run_id"),
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "expected_answer_ids": plan["expected_answer_ids"],
        "answer_validation": "JSON syntax only; task schema and geometry results must be retained separately",
        "plan": plan_record,
        "files": files,
        "complete": complete,
    }
    text = _json_text(manifest)
    _write_new(output, text)
    receipt = {"output": str(args.output), "sha256": _digest(text.encode("utf-8")), "complete": complete, "answer_statuses": {record["id"]: record["status"] for record in files["answers"]}}
    return receipt, 0 if complete else 1


def verify(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    manifest_path = _absolute(args.freeze)
    raw = manifest_path.read_bytes()
    if _digest(raw) != args.sha256.lower():
        return {"ok": False, "errors": [{"code": "freeze_changed", "message": "The freeze manifest differs from the retained digest"}]}, 1
    manifest = _json_bytes(raw)
    if not isinstance(manifest, dict) or manifest.get("format") != FREEZE_FORMAT:
        raise ValueError("Unsupported freeze manifest")
    errors: list[dict[str, Any]] = []
    groups = {"plan": [manifest["plan"]], **manifest["files"]}
    for role, records in groups.items():
        for stored in records:
            path = manifest_path.parent / stored["path"] if stored["path"] is not None else None
            current = _record_file(stored["id"], path, manifest_path.parent, answer=role == "answers")
            if any(stored[key] != current[key] for key in ("status", "sha256", "size")):
                errors.append({"code": "file_changed", "role": role, "id": stored["id"], "before": stored["status"], "after": current["status"]})
    unchanged = not errors
    complete = manifest.get("complete") is True
    if not complete:
        errors.append({"code": "incomplete_run", "message": "The frozen run retains missing, unsubmitted, unreadable, or invalid-JSON files"})
    return {"ok": unchanged and complete, "unchanged": unchanged, "complete": complete, "errors": errors}, 0 if unchanged and complete else 1


def _positive_number(text: str) -> float:
    value = float(text)
    if not math.isfinite(value) or value <= 0:
        raise argparse.ArgumentTypeError("Must be a finite positive number")
    return value


def _positive_int(text: str) -> int:
    value = int(text)
    if value <= 0:
        raise argparse.ArgumentTypeError("Must be a positive integer")
    return value


def _sha256_argument(text: str) -> str:
    if len(text) != 64 or any(char not in "0123456789abcdefABCDEF" for char in text):
        raise argparse.ArgumentTypeError("Expected the 64-character digest from the freeze receipt")
    return text


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("geometry", "overlay"):
        command = sub.add_parser(name, help="Inspect coordinate geometry" if name == "geometry" else "Embed the original raster and annotations in an inspection SVG")
        command.add_argument("annotations", type=Path)
        command.add_argument("--x-max", type=_positive_number, required=True, help="Inclusive x-coordinate upper bound; lower bound is zero")
        command.add_argument("--y-max", type=_positive_number, required=True, help="Inclusive y-coordinate upper bound; lower bound is zero")
        command.add_argument("--point-location", choices=("any", "covered", "inside"), default="any", help="Relationship to the associated polygon; use the task's point definition (default: any)")
        command.add_argument("--width", type=_positive_int, required=name == "overlay", help="Oriented original raster width in pixels")
        command.add_argument("--height", type=_positive_int, required=name == "overlay", help="Oriented original raster height in pixels")
        command.add_argument("--coordinate-frame", choices=("pixel-centers", "image-edges"), required=name == "overlay", help="Axis upper bounds identify the last pixel center or outer image edge")
        if name == "overlay":
            command.add_argument("--image", type=Path, required=True)
            command.add_argument("--output", type=Path, required=True, help="New SVG path; existing files are never overwritten")
    command = sub.add_parser("freeze", help="Record all expected answer IDs and SHA-256 digests from an explicit file plan")
    command.add_argument("plan", type=Path, help="JSON file allowlist; paths are relative to this plan")
    command.add_argument("--output", type=Path, required=True, help="New freeze manifest path; retain the printed digest independently")
    command = sub.add_parser("verify", help="Check the freeze manifest digest and every recorded file")
    command.add_argument("freeze", type=Path)
    command.add_argument("--sha256", type=_sha256_argument, required=True, help="Original digest retained from freeze, not a freshly computed digest")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command in ("geometry", "overlay"):
        raster = (args.width, args.height, args.coordinate_frame)
        if any(value is not None for value in raster) and any(value is None for value in raster):
            parser.error("--width, --height, and --coordinate-frame must be supplied together")
    try:
        if args.command in ("geometry", "overlay"):
            data = _json_bytes(args.annotations.read_bytes(), strict_numbers=False)
            if args.command == "geometry":
                report, _ = geometry(data, args)
                code = 0 if report["ok"] else 1
            else:
                report, code = overlay(data, args)
        elif args.command == "freeze":
            report, code = freeze(args)
        else:
            report, code = verify(args)
        sys.stdout.write(_json_text(report))
        return code
    except (OSError, ValueError, UnicodeError, KeyError, TypeError) as exc:
        sys.stderr.write(_json_text({"ok": False, "error": str(exc)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
