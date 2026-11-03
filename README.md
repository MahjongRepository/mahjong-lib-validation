# mahjong-lib-validation

Validation and benchmarking tools for the [mahjong](https://github.com/MahjongRepository/mahjong) library.

> 🚧 **Work in Progress**
>
> Validation and benchmarking commands are still under development.

## Convert Tenhou logs

Install the workspace packages with [uv](https://docs.astral.sh/uv/):

```console
uv sync --all-packages
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

## License

This repository is licensed under the [MIT license](LICENSE).
