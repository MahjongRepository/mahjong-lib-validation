# tenhou-converter

Convert Tenhou logs into datasets for scoring, winning hand detection, and
shanten calculation. Follow the [workspace setup](../../README.md#quick-start)
and run the commands from the repository root.

## Input and targets

Pass one XML or mjlog file, or a directory of logs. Gzip-compressed logs are
supported. The converter handles four-player and three-player Tenhou ranked
matches with red fives and open tanyao.

```sh
uv run tenhou-converter mjlog logs/tenhou --target shanten-tenpai --output corpora/shanten-tenpai
```

| Target | Hand | Expected result |
| --- | --- | --- |
| `scoring` (default) | Winning hand | Scoring values from the win record |
| `agari-complete` | With the winning tile | `is_agari = true` |
| `agari-tenpai` | Without the winning tile | `is_agari = false` |
| `shanten-agari` | With the winning tile | `shanten = -1` |
| `shanten-tenpai` | Without the winning tile | `shanten = 0` |

## Output

Set `--output` to a new directory. On success, the converter writes the
following files.

- `manifest.json` with dataset metadata and conversion counts
- `files.jsonl` with an index of the case files
- Case files in plain or gzip-compressed JSONL

If an individual input fails, the converter continues processing the remaining
inputs and does not publish the dataset.

| Exit code | Result | stderr |
| --- | --- | --- |
| `0` | Success | Conversion summary as JSON |
| `1` | Conversion or I/O error | Batch diagnostic report as JSON, or a plain-text error for I/O failures before the batch starts |
| `2` | Command-line argument error | Argument error message |

## Options

- `--report PATH` saves conversion counts and diagnostics as JSON. By default,
  no report file is written.
- `--cases-per-file N` sets the maximum number of cases per file. Defaults to
  100,000.
- `--no-compress` writes plain JSONL. Defaults to gzip-compressed JSONL when
  omitted.
- `--log-id ID` overrides the ID for a single input file. Defaults to the input
  filename without its recognized extension.
