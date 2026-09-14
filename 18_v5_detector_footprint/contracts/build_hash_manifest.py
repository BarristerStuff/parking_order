"""Build the final experiment manifest; the manifest excludes only itself."""
from pathlib import Path
import hashlib
import json
import time

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "contracts" / "hash_manifest.json"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


files = {
    str(path.relative_to(ROOT)): digest(path)
    for path in sorted(ROOT.rglob("*"))
    if path.is_file() and path != OUTPUT
}
payload = {
    "generated_at_unix": time.time(),
    "algorithm_revision": "V5_DETECTOR_FOOTPRINT",
    "scope": "all regular files recursively under experiment root except contracts/hash_manifest.json itself",
    "self_excluded": True,
    "files": files,
}
OUTPUT.write_text(json.dumps(payload, indent=2) + "\n")
print(json.dumps({"manifest": str(OUTPUT), "entries": len(files)}))
