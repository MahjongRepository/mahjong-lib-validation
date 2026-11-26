# majsoul-converter

Convert Mahjong Soul replays into datasets for scoring, winning hand detection,
and shanten calculation. Follow the [workspace setup](../../README.md#quick-start)
and run the commands from the repository root.

## Input and targets

Pass one `.bin` file, or a directory of `.bin` files. Each file must contain
the original binary `fetchGameRecord` response frame, including the response kind,
two-byte request number, and embedded replay data. The converter handles
four-player and three-player Mahjong Soul ranked matches. Replays without match
metadata are assumed to use ranked rules.

```sh
uv run majsoul-converter logs/majsoul --target shanten-tenpai --output corpora/majsoul-shanten
```

| Target | Hand | Expected result |
| --- | --- | --- |
| `scoring` (default) | Winning hand | Scoring values from the win record |
| `agari-complete` | With the winning tile | `is_agari = true` |
| `agari-tenpai` | Without the winning tile | `is_agari = false` |
| `shanten-agari` | With the winning tile | `shanten = -1` |
| `shanten-tenpai` | Without the winning tile | `shanten = 0` |

## Output and options

Set `--output` to a new directory. A successful conversion writes `manifest.json`,
an index, and case files. A failed conversion prevents dataset publication.
The command prints the manifest or a diagnostic to stderr.

- `--cases-per-file N` sets the maximum number of cases per file. Defaults to
  100,000.
- `--no-compress` writes plain JSONL. Defaults to gzip-compressed JSONL when
  omitted.
- `--log-id ID` overrides the ID for a single input file. Defaults to the
  response UUID if available, or the input filename without its extension.
