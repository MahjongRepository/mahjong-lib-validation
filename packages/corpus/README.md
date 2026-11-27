# mahjong-corpus

Read, check, and write datasets for mahjong scoring, winning hand detection,
and shanten calculation. Follow the [workspace setup](../../README.md#quick-start)
and run Python from the repository root through `uv run`.

## Inspect a dataset

Check the dataset from the [quick start](../../README.md#quick-start).
The command prints its case type and record count after checking all records.

```sh
uv run python -c "from corpus import check_dataset; manifest = check_dataset('corpora/scoring'); print(manifest['case_type'], manifest['record_count'])"
```

## Work with cases in Python

- `read_dataset(path)` iterates over the cases in a dataset. Consume the
  iterator to the end to check every record.
- `write_dataset(path, cases, generator=..., conversion=...)` writes cases
  and their metadata to a new dataset directory.
- `read_cases(path)` and `write_cases(path, cases)` handle standalone JSONL
  case files.

Converters can use `corpus.conversion_reports.new_report` to initialize a
report and pass its mutable `conversion` summary to `write_dataset`. Update
the summary as the case iterator runs. Use `record_diagnostic` to tally a
failed or excluded input by reason and keep the first 100 diagnostics.
`write_report` saves the final report as UTF-8 JSON at a new path.
