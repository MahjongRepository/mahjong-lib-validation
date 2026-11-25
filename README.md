# mahjong-lib-validation

Validate, benchmark, and profile scoring, winning hand detection, and shanten
calculation in the [mahjong](https://github.com/MahjongRepository/mahjong) library.

## Quick start

Install [uv](https://docs.astral.sh/uv/), then clone and set up the workspace.

```console
git clone https://github.com/MahjongRepository/mahjong-lib-validation.git
cd mahjong-lib-validation
uv sync --locked --all-packages --python 3.15
```

Convert the bundled example from the repository root. To use your own logs,
replace the input path with a Tenhou log file or directory.

```console
uv run tenhou-converter mjlog packages/tenhou-converter/tests/fixtures/four-ron.xml --output scoring-corpus
```

Validate, benchmark, and profile the same dataset. Each command needs a new
output directory.

```console
uv run mahjong-validator validate scoring-corpus --output scoring-validation
uv run mahjong-validator benchmark scoring-corpus --limit 1000 --output scoring-benchmark
uv run mahjong-validator profile scoring-corpus --limit 1000 --method tracing --output scoring-profile
```

## Tools

- [tenhou-converter](packages/tenhou-converter/README.md) describes supported logs and dataset targets.
- [mahjong-validator](packages/validator/README.md) covers case selection, measurements, and reports.
- [mahjong-corpus](packages/corpus/README.md) shows how to inspect and use datasets in Python.

## License

This repository is licensed under the [MIT license](LICENSE).
