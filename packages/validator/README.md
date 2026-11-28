# mahjong-validator

Validate and measure scoring, winning hand detection, and shanten calculation
using corpus datasets. Follow the [workspace setup](../../README.md#quick-start)
and run the commands from the repository root. The dataset manifest selects
the calculation for all three commands.

## Commands and results

The examples use the dataset from the [quick start](../../README.md#quick-start).

Benchmarking and profiling measure only after the selected cases pass
validation. Both commands also save the validation reports.

- `--output DIR` is required for each command. Specify a new directory.
  The validator creates any missing parent directories.

### Validate

```sh
uv run mahjong-validator validate corpora/scoring --output results/scoring/validation
```

Read `summary.json` for totals and comparison coverage. Read `cases.jsonl`
for individual results. A passing case means all compared fields matched.
Check the report for excluded fields.

### Benchmark

```sh
uv run mahjong-validator benchmark corpora/scoring --limit 1000 --output results/scoring/benchmark
```

The benchmark measures calculation time and writes raw timings to
`timings.json`.

- `--samples N` sets the number of timing samples. Defaults to 10.

### Profile

```sh
uv run mahjong-validator profile corpora/scoring --limit 1000 --method tracing --output results/scoring/profile
```

Profiling shows where calculation time is spent.

- `--method METHOD` is required. Use `tracing` to write `profile.pstats` or
  `sampling` to write an interactive `profile.html`. Sampling requires
  permission for Tachyon to attach to the worker.
- `--min-seconds SECONDS` sets the minimum sampling duration. Defaults to 3
  seconds. Sampling finishes at a batch boundary, so a long batch can
  extend the run beyond this duration. Available only with `sampling`.
- `--sampling-rate HZ` sets the requested sampling frequency. Defaults to
  1,000 Hz. Available only with `sampling`.

## Select cases

- `--player-count 3` or `--player-count 4` selects a player count. By default,
  neither player count is filtered out.
- `--case-id ID` selects a case. Specify this option up to 100 times. By
  default, cases are not filtered by ID.
- `--limit N` caps the number of selected cases. It is required for
  `benchmark` and `profile`. By default, `validate` checks all matching cases.

## Exit codes

- `0` means validation or measurement succeeded.
- `1` means results differed from expectations, validation was incomplete,
  no cases were selected, or a calculation failed. Check the saved reports.
- `2` means an argument, dataset, I/O, or measurement setup error.

Run `uv run mahjong-validator <command> --help` for all options.
