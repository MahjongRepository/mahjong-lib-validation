# majsoul-converter

Convert Mahjong Soul replays into datasets for scoring, winning hand detection,
and shanten calculation. Follow the [workspace setup](../../README.md#quick-start)
and run the commands from the repository root.

## Input and targets

Pass one `.bin` file or a directory of replays saved as original
`fetchGameRecord` response frames. The converter handles four-player and
three-player Mahjong Soul ranked matches.

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
an index, and case files. If an individual input fails, the converter continues
processing the remaining inputs and does not publish the dataset.
The command prints a conversion summary or batch diagnostic report as JSON to
stderr. A successful conversion exits with 0, a conversion or I/O error with 1,
and a command-line argument error with 2.

- `--report PATH` saves conversion counts and diagnostics as JSON. By default,
  no report file is written.
- `--cases-per-file N` sets the maximum number of cases per file. Defaults to
  100,000.
- `--no-compress` writes plain JSONL. Defaults to gzip-compressed JSONL when
  omitted.
- `--log-id ID` overrides the ID for a single input file. Defaults to the
  response UUID if available, or the input filename without its extension.
