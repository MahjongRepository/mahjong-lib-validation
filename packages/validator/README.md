# mahjong-validator

Validate and measure scoring, winning hand detection, and shanten calculation
using corpus datasets. Follow the [workspace setup](../../README.md#quick-start)
and run the commands from the repository root. The dataset manifest selects
the calculation for all three commands.

## Commands and results

The examples use the dataset from the [quick start](../../README.md#quick-start).
Each command requires `--output` to point to a new directory. The validator
creates any missing parent directories.

```sh
uv run mahjong-validator validate corpora/scoring --output results/scoring/validation
uv run mahjong-validator benchmark corpora/scoring --limit 1000 --output results/scoring/benchmark
uv run mahjong-validator profile corpora/scoring --limit 1000 --method tracing --output results/scoring/profile
```

- `validate` checks expected results. Read `summary.json` for totals and
  comparison coverage, and `cases.jsonl` for individual results. A passing
  case means all compared fields matched. Check the report for excluded fields.
- `benchmark` measures calculation time and writes raw timings to
  `timings.json`. Use `--samples N` to change the number of timing samples.
- `profile` shows where calculation time is spent. Use `--method tracing`
  for `profile.pstats` or `--method sampling` for an interactive
  `profile.html`. Sampling requires permission for Tachyon to attach to the
  worker. Adjust it with `--min-seconds` and `--sampling-rate`.

Benchmarking and profiling measure only after the selected cases pass
validation. Both commands also save the validation reports.

## Select cases

- `--player-count 3` or `--player-count 4` selects a game size.
- `--case-id ID` selects a case. Specify this option up to 100 times.
- `--limit N` caps the number of selected cases. It is required for
  `benchmark` and `profile`.

## Exit codes

- `0` means validation or measurement succeeded.
- `1` means results differed from expectations, validation was incomplete,
  no cases were selected, or a calculation failed. Check the saved reports.
- `2` means an argument, dataset, I/O, or measurement setup error.

Run `uv run mahjong-validator <command> --help` for all options.
