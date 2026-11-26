# Current Specification

## Corpus

A dataset consists of `manifest.json`, `files.jsonl`, and JSONL data that can be split into multiple files. The files can be plain text or gzip-compressed.
Each dataset contains cases of a single type.

| `case_type` | Expected results |
| --- | --- |
| `scoring` | Yaku, han, fu, yakuman multipliers, points, and related values |
| `agari` | Whether the tile configuration forms a winning hand |
| `shanten` | Minimum shanten across the standard hand, seven pairs, and thirteen orphans |

See the [corpus models](../packages/corpus/src/corpus/models.py) and
[dataset processing code](../packages/corpus/src/corpus/datasets.py) for types and validation rules.

## Tenhou Log Conversion

`tenhou-converter mjlog` supports four-player and three-player Tenhou ranked matches with red fives and open tanyao enabled.
It accepts individual XML or mjlog files, directories, and gzip-compressed input.
It reconstructs the course of play, including meld calls and north tile extractions, and extracts expected scoring results from win records.

For hand validation, the converter can output a complete hand containing the winning tile and a tenpai hand with that tile removed.
The expected shanten values are −1 and 0, respectively. The expected win detection results are true and false, respectively.

## Validation and Measurement

The `validate`, `benchmark`, and `profile` commands in `mahjong-validator` support all three case types.
The commands determine the case type from the manifest. Validation checks the integrity of the entire dataset even when only a subset of cases is selected.
Benchmarking and profiling begin only after the selected cases pass pre-validation.

Scoring validation compares calculation results for each individual win. The expected results, the case's comparison conditions, and the library output determine which fields can be compared.
Scoring validation excludes the allocation of honba and riichi deposits between winners in a double ron, the allocation of payments under yakuman liability (pao), and the point transfers for the win event as a whole.
The corpus and diagnostics retain records extracted from the logs and the reasons for excluding fields from comparison.

Benchmarking saves raw timing measurements for batches of calculations in `timings.json`.
Tracing produces `profile.pstats`, and sampling uses Tachyon to produce `profile.html`.
The measured interval excludes corpus loading and pre-validation.
