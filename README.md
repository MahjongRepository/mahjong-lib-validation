# mahjong-lib-validation

Validation and benchmarking tools for the [mahjong](https://github.com/MahjongRepository/mahjong) library.

> 🚧 **Work in Progress**
>
> Scoring validation is available. Benchmarking and profiling are planned.

## Convert Tenhou logs

Install the workspace packages with [uv](https://docs.astral.sh/uv/):

```console
uv sync --all-packages --python 3.15
uv run tenhou-converter mjlog logs/tenhou --output data/tenhou-scoring
```

The converter accepts a file or a directory containing XML or gzip-compressed
`.xml` / `.mjlog` files. It supports four-player and three-player ranked games
with red fives and open tanyao, including north extraction.

Output contains a `manifest.json` and compressed scoring JSONL files.
Use `--no-compress` for plain JSONL, `--cases-per-file` to change shard size,
and `--report artifacts/conversion.json` to save conversion diagnostics.
Output directories must be new. Failed conversions prevent dataset publication.
SQLite input is not available yet.

## Validate a scoring corpus

The validator requires Python 3.15 or newer and uses `mahjong` 2.1.x.
Run it against a dataset produced by the converter:

```console
uv run mahjong-validator validate data/tenhou-scoring --output validation-results
```

It supports four-player and three-player Tenhou ranked rules. Use
`--player-count 3` or `--player-count 4` to select a player count,
repeat `--case-id ID` to select particular cases, or use `--limit N` to
validate the first N matching cases. The entire corpus is checked for
integrity even when only a subset is selected.

The output directory must be new and its parent must exist. Results are
saved to `summary.json` and `cases.jsonl`; the summary is also printed to
stdout. Exit codes are 0 for a completed validation with all selected
cases passing, 1 for mismatches, calculation errors or unvalidated cases
(including an empty selection), and 2 for invalid arguments, corpus or I/O errors.
Interrupted or invalid input does not publish a result directory.

Reports include the comparison coverage and exclusions: a passing case
means that every compared field matched. Event-wide score changes are
not compared by this initial version. Dora and nuki dora are compared
together because the library returns them as a combined value.
Identifiably ambiguous multiple-ron bonuses and payments are also reported
as unsupported fields; individual bonus allocation is not present in corpus v1 input.
Majsoul rules are currently reported as unsupported.

## License

This repository is licensed under the [MIT license](LICENSE).
