"""Behavior checks for reference-free annotation helpers, using synthetic data."""

from __future__ import annotations

import base64
import copy
import hashlib
import json
import struct
import subprocess
import sys
import xml.etree.ElementTree as ET
import zlib
from pathlib import Path
from typing import Any

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "skills" / "annotate-images-directly" / "scripts" / "annotation_run.py"


def write_json(path: Path, value: Any) -> Path:
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def invoke(*args: object) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(SCRIPT), *map(str, args)], capture_output=True, text=True, check=False)


def png_bytes(width: int = 64, height: int = 48) -> bytes:
    """Create an original RGB raster with a synthetic rectangle; no image library."""
    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))

    pixels = b"".join(
        b"\x00" + b"".join(bytes((220, 40, 40) if 8 <= x < 40 and 8 <= y < 32 else (235, 235, 235)) for x in range(width))
        for y in range(height)
    )
    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(pixels)) + chunk(b"IEND", b"")


def polygon(points: list[tuple[float, float]]) -> dict[str, Any]:
    return {"class": "shape", "polygon": [{"x": x, "y": y} for x, y in points]}


def rectangle() -> dict[str, Any]:
    shape = polygon([(8, 8), (40, 8), (40, 32), (8, 32)])
    shape.update(point={"x": 24, "y": 20}, bbox={"xmin": 8, "ymin": 8, "xmax": 40, "ymax": 32})
    return shape


def run_geometry(tmp_path: Path, objects: list[Any], *options: object) -> tuple[subprocess.CompletedProcess[str], dict[str, Any]]:
    path = write_json(tmp_path / "answer.json", {"objects": objects})
    result = invoke("geometry", path, "--x-max", 64, "--y-max", 48, *options)
    return result, json.loads(result.stdout)


def codes(report: dict[str, Any], kind: str) -> set[str]:
    return {item["code"] for item in report[kind]}


@pytest.mark.parametrize("objects", [[], [{"point": [0, 0]}], [{"bbox": [0, 0, 64, 48]}], [rectangle()]])
def test_accepts_empty_points_boxes_and_consistent_regions(tmp_path: Path, objects: list[Any]) -> None:
    result, report = run_geometry(tmp_path, objects, "--point-location", "inside")
    assert result.returncode == 0, result.stderr
    assert report["ok"] is True
    assert report["errors"] == []
    assert report["object_count"] == len(objects)


def test_accepts_concavity_and_straight_through_vertices(tmp_path: Path) -> None:
    shape = polygon([(4, 4), (20, 4), (40, 4), (40, 20), (20, 20), (20, 40), (4, 40)])
    shape["point"] = [10, 30]
    result, report = run_geometry(tmp_path, [shape], "--point-location", "inside")
    assert result.returncode == 0, report


@pytest.mark.parametrize("value", [True, False, None, "4", float("nan"), float("inf"), -1, 65])
def test_rejects_non_numeric_nonfinite_and_out_of_bounds_coordinates(tmp_path: Path, value: Any) -> None:
    result, report = run_geometry(tmp_path, [{"point": [value, 10]}])
    assert result.returncode == 1
    assert report["ok"] is False
    assert report["errors"]


@pytest.mark.parametrize("box", [[10, 10, 9, 20], [10, 10, 10, 20], [10, 10, 20, 10]])
def test_rejects_reversed_or_degenerate_bbox(tmp_path: Path, box: list[int]) -> None:
    result, report = run_geometry(tmp_path, [{"bbox": box}])
    assert result.returncode == 1
    assert "invalid_bbox" in codes(report, "errors")


@pytest.mark.parametrize(
    ("points", "code"),
    [
        ([(4, 4), (40, 4)], "invalid_coordinates"),
        ([(4, 4), (40, 4), (40, 30), (4, 4)], "duplicate_vertex"),
        ([(4, 4), (20, 4), (12, 4), (40, 30), (4, 30)], "adjacent_backtrack"),
        ([(4, 4), (20, 4), (40, 4)], "zero_area"),
        ([(4, 4), (50, 40), (4, 30), (40, 4)], "self_intersection"),
        ([(4, 4), (40, 4), (40, 40), (20, 4), (4, 40)], "self_intersection"),
    ],
)
def test_rejects_non_simple_polygons(tmp_path: Path, points: list[tuple[float, float]], code: str) -> None:
    result, report = run_geometry(tmp_path, [polygon(points)])
    assert result.returncode == 1
    assert code in codes(report, "errors")


def test_nonzero_signed_area_does_not_excuse_self_intersection(tmp_path: Path) -> None:
    shape = polygon([(10, 10), (90, 90), (10, 70), (70, 10)])
    shape["point"] = {"x": 20, "y": 15}
    answer = write_json(tmp_path / "answer.json", {"objects": [shape]})
    result = invoke("geometry", answer, "--x-max", 100, "--y-max", 100, "--point-location", "inside")
    report = json.loads(result.stdout)
    assert result.returncode == 1
    assert "self_intersection" in codes(report, "errors")
    assert "zero_area" not in codes(report, "errors")


def test_point_boundary_rule_is_explicit(tmp_path: Path) -> None:
    shape = rectangle()
    shape["point"] = [8, 20]
    inside, report = run_geometry(tmp_path, [shape], "--point-location", "inside")
    assert inside.returncode == 1
    assert "point_location" in codes(report, "errors")
    covered, _ = run_geometry(tmp_path, [shape], "--point-location", "covered")
    assert covered.returncode == 0


def test_enclosure_error_differs_from_bbox_padding_warning(tmp_path: Path) -> None:
    shape = rectangle()
    shape["bbox"]["xmin"] = 10
    result, report = run_geometry(tmp_path, [shape])
    assert result.returncode == 1
    assert "bbox_enclosure" in codes(report, "errors")
    shape["bbox"]["xmin"] = 2
    result, report = run_geometry(tmp_path, [shape])
    assert result.returncode == 0
    assert "bbox_padding" in codes(report, "warnings")


def test_duplicate_regions_warn_without_removing_or_modifying_objects(tmp_path: Path) -> None:
    first = rectangle()
    second = copy.deepcopy(first)
    second["polygon"] = second["polygon"][::-1]
    answer = write_json(tmp_path / "answer.json", {"objects": [first, second]})
    original = answer.read_bytes()
    result = invoke("geometry", answer, "--x-max", 64, "--y-max", 48)
    report = json.loads(result.stdout)
    assert result.returncode == 0
    assert "duplicate_region" in codes(report, "warnings")
    assert report["object_count"] == 2
    assert answer.read_bytes() == original


def test_shared_boundary_between_classes_remains_a_warning(tmp_path: Path) -> None:
    first = polygon([(0, 0), (10, 0), (10, 10), (0, 10)])
    second = polygon([(10, 0), (20, 0), (20, 10), (10, 10)])
    second["class"] = "another-shape"
    result, report = run_geometry(tmp_path, [first, second])
    assert result.returncode == 0
    assert "region_contact_or_overlap" in codes(report, "warnings")
    assert report["object_count"] == 2


def test_subpixel_nonzero_region_warns_without_deletion(tmp_path: Path) -> None:
    tiny = polygon([(0.001, 0.001), (0.002, 0.001), (0.001, 0.002)])
    result, report = run_geometry(tmp_path, [tiny], "--width", 64, "--height", 48, "--coordinate-frame", "pixel-centers")
    assert result.returncode == 0
    assert report["errors"] == []
    assert "rounded_pixel_degeneracy" in codes(report, "warnings")
    assert report["object_count"] == 1


def test_geometry_does_not_replace_category_schema_validation(tmp_path: Path) -> None:
    result, report = run_geometry(tmp_path, [{"class": "task-specific-value", "point": [2.5, 3.5], "extra": "task-validator-decides"}])
    assert result.returncode == 0
    assert report["ok"] is True


def test_multiple_invalid_objects_remain_in_count_and_findings(tmp_path: Path) -> None:
    result, report = run_geometry(tmp_path, [{"point": [-1, 0]}, {"bbox": [10, 10, 5, 5]}])
    assert result.returncode == 1
    assert report["object_count"] == 2
    assert {issue["object"] for issue in report["errors"]} == {0, 1}


def overlay_args(answer: Path, image: Path, output: Path, width: int, height: int, frame: str) -> list[object]:
    return ["overlay", answer, "--image", image, "--output", output, "--width", width, "--height", height, "--x-max", 64, "--y-max", 48, "--coordinate-frame", frame]


def test_overlay_embeds_original_bytes_and_escapes_labels(tmp_path: Path) -> None:
    image = tmp_path / "image.png"
    image.write_bytes(png_bytes())
    shape = rectangle()
    shape["class"] = "shape </text><script>synthetic</script> & label"
    answer = write_json(tmp_path / "answer.json", {"objects": [shape]})
    output = tmp_path / "overlay.svg"
    result = invoke(*overlay_args(answer, image, output, 64, 48, "image-edges"))
    assert result.returncode == 0, result.stderr
    root = ET.fromstring(output.read_text(encoding="utf-8"))
    embedded = root.find("{*}image")
    assert embedded is not None
    assert base64.b64decode(embedded.attrib["href"].split(",", 1)[1]) == image.read_bytes()
    assert not root.findall(".//{*}script")
    assert any(shape["class"] in (text.text or "") for text in root.findall(".//{*}text"))
    description = root.find("{*}desc")
    assert description is not None
    assert "64x48" in description.text and "image-edges" in description.text


@pytest.mark.parametrize(("frame", "expected"), [("pixel-centers", [(0.5, 0.5), (2.5, 1.5)]), ("image-edges", [(0.0, 0.0), (3.0, 2.0)])])
def test_overlay_distinguishes_pixel_centers_from_image_edges(tmp_path: Path, frame: str, expected: list[tuple[float, float]]) -> None:
    image = tmp_path / "image.png"
    image.write_bytes(png_bytes(3, 2))
    answer = write_json(tmp_path / "answer.json", {"objects": [{"point": [0, 0]}, {"point": [64, 48]}]})
    output = tmp_path / "overlay.svg"
    result = invoke(*overlay_args(answer, image, output, 3, 2, frame))
    assert result.returncode == 0, result.stderr
    root = ET.fromstring(output.read_text(encoding="utf-8"))
    centers = [(float(item.attrib["cx"]), float(item.attrib["cy"])) for item in root.findall(".//{*}circle")]
    assert centers == expected


def test_overlay_rejects_wrong_dimensions_and_preserves_existing_output(tmp_path: Path) -> None:
    image = tmp_path / "image.png"
    image.write_bytes(png_bytes())
    answer = write_json(tmp_path / "answer.json", {"objects": [rectangle()]})
    output = tmp_path / "overlay.svg"
    bad = invoke(*overlay_args(answer, image, output, 65, 48, "image-edges"))
    assert bad.returncode != 0
    assert not output.exists()
    output.write_text("retained prior inspection", encoding="utf-8")
    result = invoke(*overlay_args(answer, image, output, 64, 48, "image-edges"))
    assert result.returncode == 2
    assert output.read_text(encoding="utf-8") == "retained prior inspection"


def make_run(tmp_path: Path) -> Path:
    (tmp_path / "image.png").write_bytes(png_bytes())
    write_json(tmp_path / "contract.json", {"coordinate_frame": "image-edges", "x_max": 64, "y_max": 48})
    write_json(tmp_path / "answer.json", {"objects": [rectangle()]})
    return write_json(tmp_path / "plan.json", {"expected_answer_ids": ["sample-01"], "inputs": {"sample-01": "image.png"}, "settings": {"contract": "contract.json"}, "answers": {"sample-01": "answer.json"}})


def freeze_run(tmp_path: Path) -> tuple[Path, dict[str, Any]]:
    plan = make_run(tmp_path)
    frozen = tmp_path / "frozen.json"
    result = invoke("freeze", plan, "--output", frozen)
    assert result.returncode == 0, result.stderr
    return frozen, json.loads(result.stdout)


def test_freeze_and_verify_record_inputs_settings_plan_and_answers(tmp_path: Path) -> None:
    frozen, receipt = freeze_run(tmp_path)
    manifest = json.loads(frozen.read_text())
    assert manifest["expected_answer_ids"] == ["sample-01"]
    assert receipt["complete"] is True
    assert receipt["sha256"] == hashlib.sha256(frozen.read_bytes()).hexdigest()
    records = [manifest["plan"], *(record for group in manifest["files"].values() for record in group)]
    assert len(records) == 4
    for record in records:
        content = (frozen.parent / record["path"]).read_bytes()
        assert record["sha256"] == hashlib.sha256(content).hexdigest()
        assert record["size"] == len(content)
    result = invoke("verify", frozen, "--sha256", receipt["sha256"])
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["unchanged"] is True


def test_freeze_preserves_missing_unsubmitted_omitted_and_invalid_answers(tmp_path: Path) -> None:
    plan_path = make_run(tmp_path)
    plan = json.loads(plan_path.read_text())
    plan["expected_answer_ids"] += ["missing", "unsubmitted", "invalid", "omitted"]
    plan["answers"].update(missing="not-created.json", unsubmitted=None, invalid="invalid.json")
    invalid = tmp_path / "invalid.json"
    invalid.write_bytes(b"{broken JSON")
    write_json(plan_path, plan)
    frozen = tmp_path / "frozen.json"
    result = invoke("freeze", plan_path, "--output", frozen)
    receipt = json.loads(result.stdout)
    assert result.returncode == 1
    assert frozen.is_file()
    assert receipt["complete"] is False
    manifest = json.loads(frozen.read_text())
    answers = {item["id"]: item for item in manifest["files"]["answers"]}
    assert set(answers) == set(plan["expected_answer_ids"])
    assert answers["missing"]["status"] == "missing"
    assert answers["unsubmitted"]["status"] == answers["omitted"]["status"] == "unsubmitted"
    assert answers["invalid"]["status"] == "invalid_json"
    assert answers["invalid"]["sha256"] == hashlib.sha256(invalid.read_bytes()).hexdigest()
    before = invoke("verify", frozen, "--sha256", receipt["sha256"])
    assert before.returncode == 1
    assert json.loads(before.stdout)["unchanged"] is True
    write_json(tmp_path / "not-created.json", {"objects": []})
    after = invoke("verify", frozen, "--sha256", receipt["sha256"])
    assert after.returncode == 1
    assert json.loads(after.stdout)["unchanged"] is False


@pytest.mark.parametrize(("filename", "action"), [("image.png", "change"), ("contract.json", "change"), ("answer.json", "change"), ("answer.json", "delete"), ("plan.json", "change")])
def test_verify_rejects_changes_or_deletion_to_any_recorded_role(tmp_path: Path, filename: str, action: str) -> None:
    frozen, receipt = freeze_run(tmp_path)
    path = tmp_path / filename
    if action == "delete":
        path.unlink()
    else:
        path.write_bytes(path.read_bytes() + b" ")
    result = invoke("verify", frozen, "--sha256", receipt["sha256"])
    assert result.returncode == 1
    report = json.loads(result.stdout)
    assert report["ok"] is False
    assert "file_changed" in codes(report, "errors")


def test_verify_rejects_changed_freeze_manifest_even_if_record_digests_are_rewritten(tmp_path: Path) -> None:
    frozen, receipt = freeze_run(tmp_path)
    answer = tmp_path / "answer.json"
    answer.write_text('{"objects": []}', encoding="utf-8")
    manifest = json.loads(frozen.read_text())
    manifest["files"]["answers"][0]["sha256"] = hashlib.sha256(answer.read_bytes()).hexdigest()
    write_json(frozen, manifest)
    result = invoke("verify", frozen, "--sha256", receipt["sha256"])
    assert result.returncode == 1
    assert "freeze_changed" in codes(json.loads(result.stdout), "errors")


@pytest.mark.parametrize("change", ["duplicate_ids", "unexpected_id", "unexpected_field", "empty_inputs"])
def test_freeze_rejects_ambiguous_or_incomplete_plans_without_creating_output(tmp_path: Path, change: str) -> None:
    plan_path = make_run(tmp_path)
    plan = json.loads(plan_path.read_text())
    if change == "duplicate_ids":
        plan["expected_answer_ids"] *= 2
    elif change == "unexpected_id":
        plan["answers"]["undeclared"] = "answer.json"
    elif change == "unexpected_field":
        plan["notes"] = "not part of the file allowlist"
    else:
        plan["inputs"] = {}
    write_json(plan_path, plan)
    output = tmp_path / "frozen.json"
    result = invoke("freeze", plan_path, "--output", output)
    assert result.returncode == 2
    assert not output.exists()


def test_freeze_refuses_overwrite(tmp_path: Path) -> None:
    frozen, _ = freeze_run(tmp_path)
    original = frozen.read_bytes()
    result = invoke("freeze", tmp_path / "plan.json", "--output", frozen)
    assert result.returncode == 2
    assert frozen.read_bytes() == original


def test_freeze_rejects_duplicate_json_keys(tmp_path: Path) -> None:
    plan = make_run(tmp_path)
    plan.write_text('{"expected_answer_ids":["first"],"expected_answer_ids":["second"]}', encoding="utf-8")
    result = invoke("freeze", plan, "--output", tmp_path / "frozen.json")
    assert result.returncode == 2


@pytest.mark.parametrize("command", ["geometry", "overlay", "freeze", "verify"])
def test_documented_commands_expose_help(command: str) -> None:
    result = invoke(command, "--help")
    assert result.returncode == 0
    assert "usage:" in result.stdout
