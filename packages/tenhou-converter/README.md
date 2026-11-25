# tenhou-converter

Convert Tenhou logs into datasets for scoring, winning hand detection, and
shanten calculation. Follow the [workspace setup](../../README.md#quick-start)
and run the commands from the repository root.

## Input and targets

Pass one XML or mjlog file, or a directory of logs. Gzip-compressed logs are
supported. The converter handles four-player and three-player Tenhou ranked
games with red fives and open tanyao.

```console
uv run tenhou-converter mjlog logs/tenhou --target shanten-tenpai --output shanten-corpus
```

| `--target` | Expected result |
| --- | --- |
| `scoring` (default) | Scoring values from the win record |
| `agari-complete` | Winning shape with the winning tile included |
| `agari-tenpai` | Incomplete shape with the winning tile removed |
| `shanten-agari` | Shanten −1 for the completed shape |
| `shanten-tenpai` | Shanten 0 with the winning tile removed |

## Output and options

Use a new output directory. A successful conversion writes `manifest.json`,
an index, and case files. A failed conversion prevents dataset publication.
The command prints a summary or diagnostic to stderr.

- `--report PATH` saves conversion counts and diagnostics as JSON.
- `--cases-per-file N` sets the maximum number of cases per file.
- `--no-compress` writes plain JSONL.
- `--log-id ID` overrides the ID for a single input file.

Run `uv run tenhou-converter mjlog --help` for all options. Use
[mahjong-validator](../validator/README.md) to validate or measure the output.
