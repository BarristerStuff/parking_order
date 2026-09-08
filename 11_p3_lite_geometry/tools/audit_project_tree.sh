#!/usr/bin/env bash
set -euo pipefail

project_root=/home/yanbo/net_vlm_yanboversion/vlm
expected_count=1636
expected_hash=e7cb1ef92f1af22b4333a7a9e53f3a95c3c56bc1971d51f8dd53fcf221263846

actual_count=$(find "$project_root" -type f -print | wc -l)
actual_hash=$(find "$project_root" -type f -print0 | LC_ALL=C sort -z | xargs -0 sha256sum | sha256sum | cut -d' ' -f1)

if [[ "$actual_count" != "$expected_count" || "$actual_hash" != "$expected_hash" ]]; then
    printf '{"status":"mismatch","file_count":%s,"tree_sha256":"%s"}\n' "$actual_count" "$actual_hash"
    exit 1
fi

printf '{"status":"unchanged","file_count":%s,"tree_sha256":"%s"}\n' "$actual_count" "$actual_hash"
