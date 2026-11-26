# majsoul-converter

Convert supplied four-player and three-player Mahjong Soul ranked replays to
v1 scoring datasets.

```sh
uv run majsoul-converter logs/majsoul --output corpora/majsoul
uv run mahjong-validator validate corpora/majsoul --output results/majsoul
```

Input can be one file or a directory of `.bin` and `.pb` files. The converter
accepts binary `fetchGameRecord` response frames, serialized `ResGameRecord`
messages with embedded data, and replay downloads wrapped as
`GameDetailRecords`. Supply the downloaded replay file when the response only
contains a data URL. A replay without match metadata is assumed to use ranked
rules.

Case IDs use the response UUID when available and the filename stem otherwise.
Use `--log-id` to override it for a single file. `--cases-per-file` controls
shard size and `--no-compress` writes plain JSONL. The output must be a new
directory. A conversion failure aborts the write.

The Python API exposes `convert_log(payload, log_id=...)` for in-memory scoring
cases and `convert_files(input_path, output_directory)` for datasets.
