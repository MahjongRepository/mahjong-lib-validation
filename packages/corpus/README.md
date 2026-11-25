# mahjong-corpus

Read, check, and write datasets for mahjong scoring, winning hand detection,
and shanten calculation. Follow the [workspace setup](../../README.md#quick-start)
and run Python from the repository root through `uv run`.

## Inspect a dataset

Check the dataset from the [quick start](../../README.md#quick-start).
The command prints its case type and record count after checking all records.

```console
uv run python -c "from corpus import check_dataset; manifest = check_dataset('corpora/scoring'); print(manifest['case_type'], manifest['record_count'])"
```

## Work with cases in Python

- `read_dataset(path)` iterates over the cases in a dataset. Consume the
  iterator to the end to check every record.
- `write_dataset(path, cases, generator=..., conversion=...)` writes cases
  and their metadata to a new dataset directory.
- `read_cases(path)` and `write_cases(path, cases)` handle standalone JSONL
  case files.

See the [dataset format](../../docs/reference.md#コーパス) for the supported
case types and files.
