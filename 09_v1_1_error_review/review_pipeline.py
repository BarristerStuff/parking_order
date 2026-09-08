#!/usr/bin/env python3
"""Build DEV-only visual review artifacts for parking_order_violation v1.1."""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import random
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

TODAY = date(2026, 9, 7).isoformat()
DATASET = Path("/home/yanbo/net_vlm_xunjian_dataset")
DEV_IMAGE_ROOT = (DATASET / "00_raw/ai_generated/images/20260902_ai_generated_parking_order_violation_pov_b1_397").resolve()
OPT = Path("/home/yanbo/net_vlm_parking_optimization")
OUT = OPT / "09_v1_1_error_review"
MANIFEST = OPT / "05_p0_frozen/p0_dev_manifest.csv"
PREDICTIONS = OPT / "06_p0_results/predictions.jsonl"
RUN_SUMMARY = OPT / "06_p0_results/run_summary.json"
METRICS = OPT / "07_error_analysis/metrics.json"
FINAL_AUDIT = OPT / "08_final_audit/final_audit.json"
BIND_DIR = OUT / "00_binding_audit"
MATERIAL_DIR = OUT / "01_review_materials"
TABLE_DIR = OUT / "02_review_tables"
DEF_DIR = OUT / "03_definition_analysis"
AUDIT_DIR = OUT / "05_final_audit"
SEED = 20260907

EXPECTED_FROZEN_HASHES = {
    str(PREDICTIONS): "b08d2adbc8d558f07ef2d9f1fc0e6b38f522ee26d7c3990e4d16475d1bdd5323",
    str(RUN_SUMMARY): "a01f4a51ecca4405e86e266fc5cd0d1ddffc7621e9f21bee8ff8c5523a64361d",
    str(METRICS): "7437ebda74635121544917bd5bf32145df2929ba66da59eed4c484ee54a1601f",
}
STAT_ONLY_PATHS = [
    Path("/home/yanbo/net_vlm_xunjian_dataset/01_annotations/event_definitions.md"),
    Path("/home/yanbo/net_vlm_xunjian_dataset/01_annotations/labels.csv"),
    Path("/home/yanbo/net_vlm_xunjian_dataset/01_annotations/media.csv"),
    Path("/home/yanbo/net_vlm_xunjian_dataset/01_annotations/splits.csv"),
    OPT / "04_holdout_seal/holdout_seal.json",
    OPT / "04_holdout_seal/holdout_manifest.csv",
    Path("/home/yanbo/net_vlm_yanboversion/vlm"),
]
REVIEW_FIELDS = [
    "media_id", "relative_path", "queue_type", "generation_group", "subtype",
    "gt_intent", "sample_role", "p0_prediction", "p0_reason",
    "parking_space_evidence", "vehicle_visibility", "queue_context",
    "violation_severity", "v1_1_visual_label", "candidate_v1_2_label",
    "error_attribution", "definition_issue", "generation_issue", "model_issue",
    "review_status", "review_notes",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(value, file, ensure_ascii=False, indent=2, sort_keys=True)
        file.write("\n")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def stat_record(path: Path) -> dict:
    stat = path.stat()
    return {"path": str(path), "size": stat.st_size, "mtime_ns": stat.st_mtime_ns, "mode": oct(stat.st_mode & 0o7777)}


def snapshot_immutability() -> dict:
    return {
        "captured_date": TODAY,
        "stat_only_records": [stat_record(path) for path in STAT_ONLY_PATHS],
        "frozen_content_sha256": {path: sha256(Path(path)) for path in EXPECTED_FROZEN_HASHES},
        "note": "Formal labels/splits/HOLDOUT/project content was not opened; only file stat metadata was recorded.",
    }


def load_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as file:
        return [json.loads(line) for line in file if line.strip()]


def safe_dev_image(relative_path: str) -> tuple[Path, bool]:
    image = (DATASET / relative_path).resolve()
    try:
        image.relative_to(DEV_IMAGE_ROOT)
        return image, True
    except ValueError:
        return image, False


def binding_audit() -> tuple[list[dict], dict, list[dict], dict[str, dict]]:
    manifest = read_csv(MANIFEST)
    predictions = load_jsonl(PREDICTIONS)
    pred_by_mid: dict[str, list[dict]] = defaultdict(list)
    for prediction in predictions:
        pred_by_mid[str(prediction.get("media_id", ""))].append(prediction)
    rows = []
    for item in manifest:
        matches = pred_by_mid.get(item["media_id"], [])
        prediction = matches[0] if len(matches) == 1 else {}
        image, contained = safe_dev_image(item["relative_path"])
        checks = {
            "prediction_unique": len(matches) == 1,
            "relative_path_match": prediction.get("relative_path") == item["relative_path"],
            "gt_match": str(prediction.get("gt_label", "")) == item["event_label"],
            "sample_role_match": prediction.get("sample_role") == item["sample_role"],
            "generation_group_match": prediction.get("group_id") == item["group_id"],
            "subtype_match": prediction.get("group_key") == item["group_key"],
            "source_id_match": str(prediction.get("source_id", "")) == item["source_id"],
            "split_match": prediction.get("split") == item["split"] == "train",
            "status_ok": prediction.get("status") == "ok",
            "schema_ok": prediction.get("model_label") in {"0", "1", "uncertain"}
                and isinstance(prediction.get("reason"), str)
                and isinstance(prediction.get("evidence"), str)
                and not prediction.get("parse_error") and not prediction.get("inference_error"),
            "dev_path_contained": contained,
            "image_exists": contained and image.is_file(),
            "image_sha256_match": contained and image.is_file() and sha256(image) == item["sha256"],
        }
        ok = all(checks.values())
        rows.append({
            "media_id": item["media_id"], "source_id": item["source_id"],
            "relative_path": item["relative_path"], "gt_label": item["event_label"],
            "sample_role": item["sample_role"], "generation_group": item["group_id"],
            "subtype": item["group_key"], "manifest_split": item["split"],
            "p0_prediction": prediction.get("model_label", ""),
            "p0_reason": prediction.get("reason", ""), "p0_status": prediction.get("status", "missing"),
            "http_status": "not_recorded_in_frozen_prediction",
            "schema_status": "ok" if checks["schema_ok"] else "failed",
            **{name: str(value).lower() for name, value in checks.items()},
            "binding_ok": str(ok).lower(),
        })
    manifest_ids = [row["media_id"] for row in manifest]
    prediction_ids = [str(row.get("media_id", "")) for row in predictions]
    missing = sorted(set(manifest_ids) - set(prediction_ids))
    extra = sorted(set(prediction_ids) - set(manifest_ids))
    duplicate_manifest = len(manifest_ids) - len(set(manifest_ids))
    duplicate_predictions = len(prediction_ids) - len(set(prediction_ids))
    actual_hashes = {path: sha256(Path(path)) for path in EXPECTED_FROZEN_HASHES}
    prior_audit = json.loads(FINAL_AUDIT.read_text(encoding="utf-8"))
    failed = sum(row["binding_ok"] != "true" for row in rows)
    ok = (len(manifest) == len(predictions) == 239 and duplicate_manifest == duplicate_predictions == 0
          and not missing and not extra and failed == 0 and actual_hashes == EXPECTED_FROZEN_HASHES
          and prior_audit["p0"]["prediction_val_intersection_count"] == 0
          and prior_audit["p0"]["prediction_holdout_intersection_count"] == 0)
    summary = {
        "audit_date": TODAY, "scope": "DEV/train only", "manifest_count": len(manifest),
        "prediction_count": len(predictions), "unique_manifest_media_id_count": len(set(manifest_ids)),
        "unique_prediction_media_id_count": len(set(prediction_ids)),
        "duplicate_manifest_count": duplicate_manifest, "duplicate_prediction_count": duplicate_predictions,
        "missing_prediction_count": len(missing), "extra_prediction_count": len(extra),
        "missing_prediction_media_ids": missing, "extra_prediction_media_ids": extra,
        "binding_failure_count": failed,
        "manifest_split_counts": dict(Counter(row["split"] for row in manifest)),
        "prediction_split_counts": dict(Counter(str(row.get("split")) for row in predictions)),
        "prediction_status_counts": dict(Counter(str(row.get("status")) for row in predictions)),
        "prediction_val_intersection_count": prior_audit["p0"]["prediction_val_intersection_count"],
        "prediction_holdout_intersection_count": prior_audit["p0"]["prediction_holdout_intersection_count"],
        "http_status_policy": "HTTP code was not persisted; frozen status/inference_error were audited.",
        "frozen_hashes_expected": EXPECTED_FROZEN_HASHES, "frozen_hashes_actual": actual_hashes,
        "frozen_hashes_match": actual_hashes == EXPECTED_FROZEN_HASHES,
        "binding_ok": ok, "final_decision_if_failed": "INSUFFICIENT_EVIDENCE",
        "val_consumed": False, "holdout_consumed": False,
    }
    return rows, summary, predictions, {row["media_id"]: row for row in manifest}


def queue_type(prediction: dict) -> str | None:
    gt, model = str(prediction["gt_label"]), str(prediction["model_label"])
    if gt == "1" and model == "0": return "FN"
    if gt == "0" and model == "1": return "FP"
    if gt == "uncertain": return "GT_UNCERTAIN"
    if gt == "1" and model == "1": return "TP"
    return None


def build_review_manifest(predictions: list[dict], manifest_by_mid: dict[str, dict]) -> tuple[list[dict], dict]:
    selected = [(queue_type(pred), pred) for pred in predictions if queue_type(pred)]
    tn_by_group: dict[str, list[dict]] = defaultdict(list)
    for pred in predictions:
        if str(pred["gt_label"]) == "0" and str(pred["model_label"]) == "0":
            tn_by_group[pred["group_key"]].append(pred)
    rng = random.Random(SEED)
    controls = []
    for group in sorted(tn_by_group):
        candidates = sorted(tn_by_group[group], key=lambda row: row["media_id"])
        controls.extend(rng.sample(candidates, min(5, len(candidates))))
    selected.extend(("TN_CONTROL", pred) for pred in controls)
    rank = {"FN": 0, "FP": 1, "GT_UNCERTAIN": 2, "TP": 3, "TN_CONTROL": 4}
    selected.sort(key=lambda pair: (rank[pair[0]], pair[1]["group_key"], int(pair[1]["source_id"])))
    rows = []
    for queue, pred in selected:
        item = manifest_by_mid[pred["media_id"]]
        rows.append({
            "media_id": pred["media_id"], "relative_path": item["relative_path"], "queue_type": queue,
            "generation_group": item["group_id"], "subtype": item["group_key"],
            "gt_intent": item["event_label"], "sample_role": item["sample_role"],
            "p0_prediction": pred["model_label"], "p0_reason": pred.get("reason", ""),
            "parking_space_evidence": "", "vehicle_visibility": "", "queue_context": "",
            "violation_severity": "", "v1_1_visual_label": "", "candidate_v1_2_label": "",
            "error_attribution": "needs_human_review", "definition_issue": "", "generation_issue": "",
            "model_issue": "", "review_status": "needs_human_review", "review_notes": "",
        })
    counts = Counter(row["queue_type"] for row in rows)
    expected = {"FN": 89, "FP": 3, "GT_UNCERTAIN": 25, "TP": 5, "TN_CONTROL": 30}
    if dict(counts) != expected: raise RuntimeError(f"Unexpected review queue counts: {dict(counts)}")
    summary = {
        "random_seed": SEED, "queue_counts": dict(counts), "review_total": len(rows),
        "tn_control_strategy": "Five fixed-seed samples from each available DEV TN subtype.",
        "tn_control_group_counts": dict(Counter(row["subtype"] for row in rows if row["queue_type"] == "TN_CONTROL")),
        "coverage_limitations": [
            "DEV has no faded-line group (hn02 is VAL); it was not accessed.",
            "DEV has no perspective group (hn03 is HOLDOUT); it was not accessed.",
            "DEV multi-vehicle p05 is positive-only and fully covered in FN/TP, not TN controls.",
        ], "val_consumed": False, "holdout_consumed": False,
    }
    return rows, summary


def load_font(size: int) -> ImageFont.ImageFont:
    for candidate in ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                      "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"]:
        if Path(candidate).is_file(): return ImageFont.truetype(candidate, size=size)
    return ImageFont.load_default()


def fit_image(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    resampling = getattr(Image, "Resampling", Image)
    return ImageOps.pad(image.convert("RGB"), size, color=(24, 24, 24), method=resampling.LANCZOS)


def render_contact_sheets(rows: list[dict]) -> list[dict]:
    by_queue: dict[str, list[dict]] = defaultdict(list)
    for row in rows: by_queue[row["queue_type"]].append(row)
    tile_w, tile_h, image_h, cols, page_rows = 600, 430, 338, 3, 3
    per_page = cols * page_rows
    main_font, small_font, index = load_font(18), load_font(15), []
    for queue in ["FN", "FP", "GT_UNCERTAIN", "TP", "TN_CONTROL"]:
        queue_dir = MATERIAL_DIR / "contact_sheets" / queue
        queue_dir.mkdir(parents=True, exist_ok=True)
        for offset in range(0, len(by_queue[queue]), per_page):
            page_items = by_queue[queue][offset:offset + per_page]
            canvas = Image.new("RGB", (tile_w * cols, tile_h * page_rows), (245, 245, 245))
            draw = ImageDraw.Draw(canvas)
            for index_in_page, row in enumerate(page_items):
                x, y = (index_in_page % cols) * tile_w, (index_in_page // cols) * tile_h
                image_path, contained = safe_dev_image(row["relative_path"])
                if not contained: raise RuntimeError(f"Non-DEV image path: {image_path}")
                with Image.open(image_path) as image: canvas.paste(fit_image(image, (tile_w, image_h)), (x, y))
                draw.rectangle((x, y + image_h, x + tile_w, y + tile_h), fill=(255, 255, 255))
                draw.text((x + 8, y + image_h + 5),
                          f"{row['media_id']} queue={queue} GT={row['gt_intent']} pred={row['p0_prediction']}",
                          fill=(0, 0, 0), font=main_font)
                draw.text((x + 8, y + image_h + 32), f"role={row['sample_role']}", fill=(20, 20, 20), font=small_font)
                draw.text((x + 8, y + image_h + 55), f"subtype={row['subtype']}", fill=(20, 20, 20), font=small_font)
            page = offset // per_page + 1
            output = queue_dir / f"{queue}_page_{page:02d}.jpg"
            canvas.save(output, quality=92, subsampling=0)
            index.append({"queue_type": queue, "page": page,
                          "relative_sheet_path": output.relative_to(OUT).as_posix(),
                          "media_ids": [row["media_id"] for row in page_items]})
    return index


def render_gallery(rows: list[dict]) -> None:
    cards = []
    for row in rows:
        image, contained = safe_dev_image(row["relative_path"])
        if not contained: raise RuntimeError(f"Non-DEV image path: {image}")
        path = html.escape(str(image))
        cards.append(f"""<article class="card"><a href="file://{path}"><img loading="lazy" src="file://{path}" alt="{html.escape(row['media_id'])}"></a>
<h3>{html.escape(row['media_id'])}</h3><div>queue={row['queue_type']} | GT={row['gt_intent']} | pred={row['p0_prediction']}</div>
<div>role={html.escape(row['sample_role'])}</div><div>subtype={html.escape(row['subtype'])}</div>
<details><summary>Show frozen P0 reason</summary><p>{html.escape(row['p0_reason'])}</p></details></article>""")
    document = f"""<!doctype html><html><head><meta charset="utf-8"><title>parking_order_violation v1.1 DEV review</title><style>
body{{font:14px system-ui,sans-serif;margin:16px;background:#eee;color:#111}}.notice{{background:#fff4c2;padding:12px;margin-bottom:14px;border-left:5px solid #d69e00}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(420px,1fr));gap:14px}}.card{{background:white;padding:10px;border:1px solid #bbb}}
.card img{{width:100%;aspect-ratio:16/9;object-fit:contain;background:#222}}h3{{margin:8px 0 4px}}details{{margin-top:8px;color:#444}}</style></head><body>
<h1>parking_order_violation v1.1 — DEV-only review</h1><div class="notice">Review image first. Generation intent is not Human Gold. Frozen model reason is collapsed. No VAL/HOLDOUT media is included.</div>
<div class="grid">{''.join(cards)}</div></body></html>"""
    (MATERIAL_DIR / "review_gallery.html").write_text(document, encoding="utf-8")


def prepare() -> None:
    for directory in [BIND_DIR, MATERIAL_DIR, TABLE_DIR, DEF_DIR, AUDIT_DIR]: directory.mkdir(parents=True, exist_ok=True)
    baseline = AUDIT_DIR / "immutability_baseline.json"
    if not baseline.exists(): write_json(baseline, snapshot_immutability())
    audit_rows, summary, predictions, manifest_by_mid = binding_audit()
    write_csv(BIND_DIR / "binding_audit.csv", audit_rows, list(audit_rows[0]))
    write_json(BIND_DIR / "binding_audit_summary.json", summary)
    if not summary["binding_ok"]: raise SystemExit("Binding audit failed; FINAL_DECISION=INSUFFICIENT_EVIDENCE")
    review_rows, queue_summary = build_review_manifest(predictions, manifest_by_mid)
    write_csv(MATERIAL_DIR / "review_manifest.csv", review_rows, REVIEW_FIELDS)
    write_csv(TABLE_DIR / "v1_1_error_review.csv", review_rows, REVIEW_FIELDS)
    write_json(MATERIAL_DIR / "review_queue_summary.json", queue_summary)
    sheet_index = render_contact_sheets(review_rows)
    write_json(MATERIAL_DIR / "contact_sheet_index.json", sheet_index)
    render_gallery(review_rows)
    print(json.dumps({"binding_ok": True, "binding_count": len(audit_rows), "review_total": len(review_rows),
                      "queue_counts": dict(Counter(row["queue_type"] for row in review_rows)),
                      "contact_sheet_count": len(sheet_index), "output_root": str(OUT)}, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("command", choices=["prepare"]); args = parser.parse_args()
    if args.command == "prepare": prepare()


if __name__ == "__main__": main()
