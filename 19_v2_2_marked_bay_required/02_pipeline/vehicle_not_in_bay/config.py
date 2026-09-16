"""Frozen v2.1.1 pipeline configuration and prompt integrity checks."""
import hashlib, json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
CONFIG=json.loads((ROOT/'config.json').read_text())
def prompt_bytes(name):
 data=(ROOT/'prompts'/name).read_bytes(); actual=hashlib.sha256(data).hexdigest()
 if actual != CONFIG['prompts'][name]['sha256']: raise RuntimeError(f'prompt hash mismatch: {name}')
 return data
def load_config(): return CONFIG
