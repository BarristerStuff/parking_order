# v2.1.1 pipeline

v2.1.1 is a behavior-preserving maintenance refactor of v2.1. It adds an in-memory `infer_image(PIL.Image, media_id, client, detector)` API, a thin `infer_path` wrapper, full config/prompt hash validation, cached detector loading, thread-safe ledgers, and no temporary View A file. Business rules and prompts are unchanged.

All production integration is out of scope. `tests/test_replay.py` and the offline replay/regression tests must pass before use.
