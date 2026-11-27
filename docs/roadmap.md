# Remaining Work

The initial implementation milestone is to generate corpora from Tenhou logs and support validation, benchmarking, and profiling for scoring, win detection, and shanten calculations.

## Top Priorities

- Identify a source of Mahjong Soul ranked replays for validation at scale.

## Deferred and Out of Scope

- SQLite input from `houou-logs` is deferred until requested.
- Further validation against real Tenhou logs is out of scope for settlements that cannot be checked by a scoring function for an individual win, such as the allocation of honba and riichi deposits in a double ron or the allocation of payments under yakuman liability (pao).
