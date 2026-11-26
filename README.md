# mahjong-lib-validation

Validation, benchmarking, and profiling tools for the
[mahjong](https://github.com/MahjongRepository/mahjong) library.

Supported calculations:

- Scoring
- Winning hand detection
- Shanten calculation

## Quick start

### Set up the workspace

Install [uv](https://docs.astral.sh/uv/), then clone and set up the workspace.

```sh
git clone https://github.com/MahjongRepository/mahjong-lib-validation.git
cd mahjong-lib-validation
uv sync --locked --all-packages --python 3.15
```

Run the remaining commands from the repository root.

### Convert Tenhou logs

Put your Tenhou mjlog files in `logs/tenhou/`, or use your own directory path.
The converter accepts `.mjlog` and `.xml` files, including gzip-compressed
`.mjlog.gz` and `.xml.gz` files.

```sh
uv run tenhou-converter mjlog logs/tenhou --output corpora/scoring
```

### Convert Mahjong Soul replays

Supply `fetchGameRecord` response frames for ranked matches, saved as `.bin` files.

```sh
uv run majsoul-converter logs/majsoul --output corpora/majsoul
```

### Validate and measure

Each command requires `--output` to point to a new directory. The validator
creates any missing parent directories.

```sh
uv run mahjong-validator validate corpora/scoring --output results/scoring/validation
uv run mahjong-validator benchmark corpora/scoring --limit 1000 --output results/scoring/benchmark
uv run mahjong-validator profile corpora/scoring --limit 1000 --method tracing --output results/scoring/profile
```

## Tools

- [tenhou-converter](packages/tenhou-converter/) converts Tenhou logs into corpus datasets.
- [majsoul-converter](packages/majsoul-converter/) converts Mahjong Soul replays into corpus datasets.
- [mahjong-validator](packages/validator/) validates, benchmarks, and profiles mahjong calculations using corpus datasets.
- [mahjong-corpus](packages/corpus/) provides Python APIs to read, write, and check corpus datasets.

## License

This repository is licensed under the [MIT license](LICENSE).
