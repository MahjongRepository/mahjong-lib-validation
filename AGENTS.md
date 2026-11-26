# Development Guide

## Workspace Structure

This uv workspace uses expected results derived from game logs to validate and measure calculations performed by `mahjong`.

| Package | Responsibility |
| --- | --- |
| `packages/corpus` | Shared case format, manifests, dataset reading and writing, and integrity checks |
| `packages/tenhou-converter` | Reconstructing game states from Tenhou logs and generating corpora |
| `packages/majsoul-converter` | Reconstructing game states from Mahjong Soul replays and generating corpora |
| `packages/validator` | Case validation, benchmarking, and profiling |

The converters and validator depend on the corpus package. The converters extract expected results from game logs, and the validator calls `mahjong`.
See the [current specification](docs/reference.md) and [remaining work](docs/roadmap.md).
User-facing commands are documented in the [README](README.md).

## Development and Verification

Run these commands from the workspace root using Python 3.15 and uv.

```console
uv sync --locked --all-packages --python 3.15
uv run --no-sync ruff check
uv run --no-sync ruff format --check
uv run --no-sync ty check
uv run --no-sync python -m pytest
```

- Put tests in each package's `tests/` directory and shared fixtures in `conftest.py`.
- When changing behavior, define the expected result in a small test and follow Red → Green → Refactor.
- Derive expected results independently from sources such as specifications, game logs, and small calculations done by hand. Do not use output from the library under test as the expected result.
- Use small fixtures to check conversion and invalid inputs. For changes that span packages, also verify the full path from game logs to validation results. Keep checks that require large game logs or depend on benchmark speed separate from the regular tests.
- When changing an API or storage format, update callers, tests, and documentation across the workspace. Follow the backward compatibility requirements of the specific task.

See the [archive](docs/archive/initial-implementation/README.md) for the initial design, verification records, and test list.
