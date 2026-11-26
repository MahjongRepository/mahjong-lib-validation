# majsoul-converter

Convert Mahjong Soul replays from four-player and three-player ranked
matches to v1 scoring, winning hand detection, and shanten datasets.

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

Use `--target` to select what to generate per winner.

| Target | Hand | Expected result |
| --- | --- | --- |
| `scoring` (default) | Winning hand | Scoring values from the replay |
| `agari-complete` | With the winning tile | `is_agari = true` |
| `agari-tenpai` | Without the winning tile | `is_agari = false` |
| `shanten-agari` | With the winning tile | `shanten = -1` |
| `shanten-tenpai` | Without the winning tile | `shanten = 0` |

```sh
uv run majsoul-converter logs/majsoul --target shanten-tenpai --output corpora/majsoul-shanten
```

The Python APIs `convert_log(payload, log_id=...)` and
`convert_files(input_path, output_directory)` accept the same `target` values.
