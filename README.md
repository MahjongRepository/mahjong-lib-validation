# mahjong-lib-validation

Validate, benchmark, and profile scoring, winning hand detection, and shanten
calculation in the [mahjong](https://github.com/MahjongRepository/mahjong) library.

## Installation

Use [uv](https://docs.astral.sh/uv/) with Python 3.15.

```console
uv sync --locked --all-packages --python 3.15
```

## Usage

### Convert Tenhou logs

```console
uv run tenhou-converter mjlog logs/tenhou --output corpora/scoring
uv run tenhou-converter mjlog logs/tenhou --target agari-complete --output corpora/agari-complete
uv run tenhou-converter mjlog logs/tenhou --target shanten-tenpai --output corpora/shanten-tenpai
```

The converter accepts XML or mjlog files, including gzip-compressed files, or
a directory of logs. It supports four-player and three-player Tenhou ranked
games with red fives and open tanyao. The available targets are `scoring`
(default), `agari-complete`, `agari-tenpai`, `shanten-agari`, and
`shanten-tenpai`.

### Validate and measure

```console
uv run mahjong-validator validate corpora/scoring --output validation-results
uv run mahjong-validator benchmark corpora/shanten-tenpai --limit 1000 --output shanten-benchmark
uv run mahjong-validator profile corpora/agari-complete --limit 1000 --method tracing --output agari-profile
```

All three commands select the calculation from the dataset manifest. Use a
new output directory. Validation writes `summary.json` and `cases.jsonl`,
including comparison coverage and exclusions. Benchmarking and profiling run
after preflight validation succeeds. Tracing writes `profile.pstats`.
Sampling writes an interactive `profile.html` and requires permission
for Tachyon to attach to the scoring or hand calculation worker.

Run `tenhou-converter mjlog --help` or `mahjong-validator --help` for options.

## License

This repository is licensed under the [MIT license](LICENSE).
