# majsoul-converter

Convert Mahjong Soul replays from four-player and three-player ranked
matches to v1 scoring datasets.

```sh
uv run majsoul-converter logs/majsoul --output corpora/majsoul
uv run mahjong-validator validate corpora/majsoul --output results/majsoul
```

Input can be a single `.bin` file or a directory of `.bin` files. Each
file must contain the original binary `fetchGameRecord` response frame,
including the response kind and two-byte request number. The response must
contain embedded replay data. A replay without match metadata is assumed to
use ranked rules.

Case IDs use the response UUID when available and the filename stem otherwise.
Use `--log-id` to override it for a single file. `--cases-per-file` controls
shard size and `--no-compress` writes plain JSONL. The output must be a new
directory. A conversion failure aborts the write.

The Python API exposes `convert_log(payload, log_id=...)` for in-memory scoring
cases and `convert_files(input_path, output_directory)` for datasets.
