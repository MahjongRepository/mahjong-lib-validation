# Remaining Work

The initial implementation milestone is to generate corpora from Tenhou logs and support validation, benchmarking, and profiling for scoring, win detection, and shanten calculations.

## Top Priorities

- Convert Mahjong Soul game logs to the shared corpus format.
- Validate scoring calculations under Mahjong Soul rules.

## CI

- Run Ruff lint and formatting checks, ty, and pytest automatically in the locked uv workspace with Python 3.15.
- Release and distribution automation are out of scope.

## Deferred and Out of Scope

- SQLite input from `houou-logs` is deferred until requested.
- Further validation against real Tenhou logs is out of scope for settlements that cannot be checked by a scoring function for an individual win, such as the allocation of honba and riichi deposits in a double ron or the allocation of payments under yakuman liability (pao).
