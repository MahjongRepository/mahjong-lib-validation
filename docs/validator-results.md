# validator 初期版の API と結果形式

作成日: 2026-11-03

[設計](validator-design.md) に基づく scoring 検証の実装契約を記録する。
benchmark・profile・compare の結果形式は未実装である。

## API

```python
from validator import Selection, validate_dataset

summary = validate_dataset(
    "data/tenhou-scoring",
    "artifacts/run-001",
    selection=Selection(player_count=3, case_ids=(), limit=100),
)
```

`validate_dataset(dataset, output, *, selection=None)` は `ValidationSummary` を返す。
型は `validator.models` に定義する。API は表示・プロセス終了を行わない。
出力先の親ディレクトリは呼出側で用意し、出力先自体は未作成にする。
既存出力は `FileExistsError`、I/O 失敗は `OSError`、corpus 不正は
`CorpusError` として送出する。これらの失敗と中断では出力を公開しない。
正常に処理を完了した不一致・計算エラーの結果は公開して返す。

`Selection` は frozen dataclass で、既定は全件選択とする。
`player_count` は `None` / `3` / `4`、`case_ids` は空または非空文字列の tuple、
`limit` は `None` または正の整数とする。bool を整数指定として受理しない。
同じ case ID に該当する全レコードを対象とし、絞込後に件数上限を適用する。

CLI は `mahjong-validator validate DATASET --output OUTPUT` とし、
`--player-count`、繰返し可能な `--case-id`、`--limit` を提供する。
summary を stdout に JSON 一件で表示し、入力等の失敗は stderr に表示する。
終了コードは API の summary の `exit_code` に従い、引数・corpus・I/O の失敗は 2。

## 保存するファイル

UTF-8 の `summary.json` と `cases.jsonl` を新しいディレクトリへ保存する。
一時ディレクトリ内で処理し、最後に rename して公開する。
結果のスキーマ版は `v1`。JSONL は選択したケースごとに一行とする。
元ケースと結果の対応には corpus の識別情報・1 始まりの全体位置・case ID を使う。
case ID の一意性に依存しない。

### summary.json

| フィールド | 型・意味 |
| --- | --- |
| `schema_version` | `"v1"` |
| `purpose` | `"validate"` |
| `complete` | `true`。入力の全件検査と選択ケースの処理が完了したこと。不一致ゼロを意味しない |
| `counts` | `passed` / `mismatch` / `error` / `unsupported` / `skipped` をすべて持つ件数辞書 |
| `exit_code` | 0 または 1。一件以上が passed で、他状態がゼロの場合だけ 0 |
| `scanned_count` | corpus の全件検査で読んだ件数 |
| `selected_count` | 選択して処理した件数。counts の和と一致する |
| `field_counts` | 比較項目名 → 項目状態 → 件数。発生した状態だけを保存する |
| `field_reasons` | 比較項目名 → 理由文字列 → 件数。理由がある項目だけを保存する |
| `selection` | `player_count`、`case_ids`（JSON 配列）、`limit` |
| `selection_sha256` | 選択した `[position, case_id]` を順に JSON 化して LF を付けた UTF-8 の SHA-256 |
| `corpus` | `manifest`（読込時のモデル）と `manifest_sha256`（保存バイト列の SHA-256） |
| `environment` | 下記の実行環境 |
| `comparison_policy` | 比較の版・ドラと抜きドラの合算・イベント集約未対応を示す文字列 |

ダイジェストの各行は `json.dumps([position, case_id], ensure_ascii=False)` と
`"\n"` の連結で生成する。空選択のダイジェストも保存するが、終了コードは 1。
manifest のモデルには元ファイルの件数・ハッシュと変換器の集計も含む。

`environment` の文字列フィールドは `validator_version`、`corpus_version`、
`mahjong_version`、`mahjong_path`（実際の import ディレクトリ）、`python`、
`python_executable`、`python_implementation`、`platform`、`rules_version`。
`python_build` は文字列配列、`free_threaded` は真偽値とする。
現在のルール対応表の版は `tenhou-ranked-match-v1`。

### cases.jsonl

| フィールド | 型・意味 |
| --- | --- |
| `position` | 元データセットの 1 始まりの位置。絞込後の通し番号ではない |
| `case_id` | 元ケースの ID |
| `status` | `passed` / `mismatch` / `error` / `unsupported` / `skipped` |
| `fields` | 項目名 → 項目結果。計算前のスキップ・未対応や計算エラーでは空辞書 |
| `reason` | ケース全体のエラー・スキップ・未対応の理由。それ以外では省略 |

計算できたケースの `fields` は `Expected` の全項目を持つ。
各項目は `status`、`expected`、`actual` を持ち、除外等には `reason` も持つ。
値は corpus の項目に対応する JSON 値とし、未取得の値は `null` とする。

項目状態は `matched`、`mismatched`、`excluded`、`unavailable`、`unsupported`。
記録された比較除外を最優先し、期待値が null なら unavailable とする。
期待値があり除外がない `event_score_deltas` は unsupported とする。
一項目以上を比較してすべて一致すれば passed、一つでも不一致なら mismatch、
比較できる項目が一つもなければ skipped とする。
部分比較の passed では、除外・不足・未対応を summary にも集計する。

本場・供託のある後続ロン、または `multiple_ron_allocation_unknown` の除外が
あるケースでは、個別配分を入力から確定できない。本場・供託・和了者の収入・
席別支払いを unsupported とし、これらの actual は null とする。
記録された比較除外と期待値不足を優先し、素点などの独立した比較は続ける。

たとえばケース全体の未対応は次のように保存する。

```json
{"case_id":"example-case","status":"unsupported","reason":"majsoul-ranked-match","fields":{},"position":2}
```

`yaku` は期待値・出力それぞれの元の正規化済み配列を保存するが、比較は順序に
依存しない。ライブラリが Dora に含める抜きドラに合わせ、比較時だけ
`dora` と `nuki_dora` の翻を合算する。この場合は二つの保存配列が異なっていても
matched になり得る。赤ドラ・裏ドラと他の役は合算しない。
合計翻が一致しても、これらの役の内訳が違えば mismatch とする。

## 現時点の制約

- mahjong 2.1.0 で公開 API と実行を確認し、依存は 2.1.x とする。
- 天鳳の赤あり・喰い断あり、単独ダブル役満なし、数え役満あり、切上げなしを
  明示設定する。状況の不明値を false に補完しない。
- 抜きドラと通常ドラの内訳は独立に検証できない。
- event_score_deltas の複数和了を合わせた集約比較は実装していない。
- 個別配分が不明な複数ロンのボーナス・個別支払いは検証できない。
  最初の一件だけでは複数ロンを特定できない corpus v1 の制約も残る。
- 雀魂のルールはケース全体を unsupported とする。
