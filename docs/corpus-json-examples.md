# scoring コーパスの JSON 例

作成日: 2026-11-01

[corpus パッケージの設計](corpus-design.md) を具体化した、合意済みの
フィールドと JSON 例を記録する。残る未決事項は末尾に記載する。
以下の例はスキーマ実装や自動変換器の出力ではなく、ローカル牌譜と
進行を確認して作成したもの。
実装では牌譜 ID をマスクせず、原値を `source.log_id` と `case_id` に保持する。
Git にコミットするドキュメントや examples では牌譜 ID をマスクする。
本書とリンク先の JSON 例もこの方針に従う。

- [天鳳の最初の和了](examples/corpus/tenhou-scoring.json)
- [雀魂の最初の和了](examples/corpus/majsoul-scoring.json)

どちらも 40 符 2 翻・2600 点のロンだが、天鳳は立直・一発、
雀魂は立直・赤ドラであり、供託を含む和了者の収入も異なる。
ファイルは見やすさのため整形した JSON としている。
実際の JSONL では一行に一件のオブジェクトを保存する。

## 識別・場況

| 項目 | 定義 |
| --- | --- |
| `schema_version` | `"v1"`。単独で取り出したケースでも版を識別可能にする |
| `case_type` | `"scoring"`。将来の別ケース種別と区別する |
| `case_id` | 出典・牌譜 ID・場・局・本場・和了順を結合する |
| `source.platform` | `"tenhou"` または `"majsoul"` |
| `source.event_index` | 0 始まり。天鳳は XML ルートの子要素、雀魂は `records` の位置 |
| `source.winner_index` | 和了イベント内の和了者位置。0 始まり。天鳳の単独 `AGARI` は 0 |
| `ruleset` | `"tenhou-ranked-match"` / `"majsoul-ranked-match"` |
| `player_count` | ルール名とは別に `3` または `4` を保持 |
| 席 | 0 始まり。配列も席順。三麻で使える席は 0〜2 |
| `round.wind` | `"east"` / `"south"` / `"west"` / `"north"` |
| `round.number` | 1 始まり。東一局は `wind="east", number=1` |
| `round.honba` | 本場の数。0 始まり |
| `round.riichi_sticks` | 和了の精算直前に場にある供託の本数。局開始時の本数ではない |
| `win_number` | 同一局内の和了順。1 始まり、元牌譜の記録順 |

`case_id` は `tenhou:<masked-log-id>:east:1:0:1` のようにする。
末尾の和了順を除く情報で同一局のケースを関連づけられる。
雀魂の `winner_index` は一つの `hules` 内の位置を表し、
`win_number` は局内全体の順序を表す。
元牌譜 ID 部分は変換器が UTF-8 の percent encoding を行う。
原値は `source.log_id` に保持し、記録順と精算の優先順位は区別する。
具体的な規則と実ダブロンの例は [scoring ケースの補完](corpus-edge-cases.md) に記録する。

## 入力

`input` に、元牌譜を読まずに得点計算へ渡せる情報をまとめる。
`concealed_tiles` は和了牌と副露を除く配列、
`winning_tile` は和了牌、`melds` は副露の配列とする。
抜き北は `nuki_count` に保持する。
席と親の席から自風を求められるため、自風は重複して保存しない。

副露は次の形とする。牌の配列は元牌譜の順序を保つ。
以下は構造説明用で、二つの実例はいずれも門前である。

```json
{
  "type": "chii",
  "tiles": ["6p", "8p", "7p"],
  "called_tile_index": 2,
  "from_seat": 2
}
```

種別は `chii`、`pon`、`daiminkan`、`ankan`、`kakan`。
鳴いた牌・相手は、順序だけに依存せず明示する。
暗槓は `called_tile_index`・`from_seat` をともに `null` とする。
加槓は元のポンで鳴いた牌の位置と相手を保持する。

`input.situation` に、進行から復元した和了状況を保存する。
`tsumo` は真偽値とし、ツモなら `true`、ロンなら `false` とする。
`riichi` は `"none"` / `"riichi"` / `"double_riichi"` とする。
それ以外の状況役は真偽値とし、不明なら `null` とする。
人和の `renhou` は、天鳳段位戦・雀魂段位戦では常に `false` とする。
人和も進行からの判定対象とするが、その前にルールによる制約を適用する。
ルールの適用と進行からの判定は変換器の責務とし、corpus は結果を保持する。
ロンでは `discarder_seat` を保存し、ツモでは `null` とする。
槍槓時も、和了牌を提供した席を `discarder_seat` で表す。

`situation_provenance` は入力とは分け、進行由来であることと
根拠となるイベント位置を記録する。役一覧から状況を推定しない。
`renhou` も変換器の判定結果を保持し、対象ルールでは上記の制約により
`false` となる。
イベント位置は監査用であり、計算時に元牌譜を必須としない。
`situation_provenance.unknown_fields` に、不明な項目名と空でない理由を保存する。
たとえば `{"ippatsu": "missing_events"}` とする。
`null` の項目には理由を必要とし、既知の項目には不明理由を付けない。
理由がない場合も必須フィールドとして空辞書を保持する。

### 今回の進行の確認

- 天鳳: 要素 96 で席 2 が立直宣言、98 で成立。
  その後、鳴きも席 2 の次のツモもなく、要素 102 の席 0 の打牌で
  ロンするため `ippatsu=true` とした。
- 雀魂: レコード 51 で席 1 が立直宣言、52 で成立。
  レコード 62 に他家のチーがあり、席 1 自身もその後ツモ・打牌を
  行っている。111 の席 3 の打牌でロンするため `ippatsu=false` とした。
- 両方とも最初の打牌での立直ではなく、槓・抜き北直後の和了でも
  最終ツモ・打牌での和了でもないことを進行から確認した。

## 期待値と比較条件

`expected` は和了記録から取得する。`yaku` の各要素には、
共通の文字列 ID、翻数、役満倍率を独立して持たせる。
通常役・ドラは `yakuman_multiplier=0`、役満は `han=null` とする。
共通 ID は `corpus.models.YakuId` の `Literal` で定義する。
一覧は [共通の役 ID](corpus-yaku.md) を参照する。
0 翻の裏ドラ項目は有効な役一覧に入れない。

### 和了点の区分（title）

`expected.title` は和了点の区分を表す。
牌譜固有の数値コードではなく、共通の文字列で保存する。
複合役満の倍率は既存の `expected.yakuman_multiplier` で表すため、
title 自体に二倍・三倍などを重複して持たせない。
数え役満は通常役の翻から成立する区分として役満と区別し、
役満倍率は 0 のまま保持する。

| title | 意味 | 雀魂の `title_id` |
| --- | --- | --- |
| `below_mangan` | 満貫未満 | 0 |
| `mangan` | 満貫 | 1 |
| `haneman` | 跳満 | 2 |
| `baiman` | 倍満 | 3 |
| `sanbaiman` | 三倍満 | 4 |
| `yakuman` | 役満・複合役満 | 5〜10。倍率は `title_id - 4` |
| `kazoe_yakuman` | 数え役満 | 11 |

たとえば二倍役満は `title="yakuman", yakuman_multiplier=2` とする。
未記録で区分を特定できない場合は `title=null` とし、
`comparison.excluded_fields` に項目 `title` と理由を保持する。

元牌譜からの区分の正規化は変換器の責務とする。
corpus は区分を点数や翻から再計算せず、記録と比較条件を保持する。
雀魂の元の `title_id` は `source.scoring_values` にも保持する。

天鳳の役満区分には複合役満と数え役満も含まれるため、
変換器は「役満区分であること」を確認してから `yakuman` の要素数を調べる。
天鳳段位戦には単独ダブル役満がないため、要素数が 1 以上なら
共通の `title="yakuman"` とし、その要素数を役満倍率とする。
要素数が 0 なら `title="kazoe_yakuman"`、役満倍率は 0 とする。
役満未満の和了まで、要素数が 0 であることだけで数え役満にしない。
元の区分は既存の `source.scoring_values.ten` に保持する。

この対応は今回提示された牌譜仕様を基にした変換方針であり、
変換器の実装時には牌譜 fixture を使って対応を確認する。

### 点数と支払い

点数はすべて点単位とする。今回の例では本場が 0 のため、
和了記録と点数移動から支払いと供託を分離できる。

| 項目 | 意味 |
| --- | --- |
| `base_points` | 本場・供託を除く、和了者への支払総額。基本点ではない |
| `honba_points` | この和了者に支払われた本場分の総額 |
| `riichi_stick_points` | この和了者が受け取った供託の総額 |
| `winner_gain` | 本場・供託を含む、この和了による和了者の収入 |
| `payments_by_seat` | この和了に対する各席の支払額。支払いを正の数で表す |
| `event_score_deltas` | 和了イベント全体の席ごとの点数移動。収入が正、支出が負 |

`event_score_deltas` は雀魂のダブロンでは複数人分を含むため、
単独の和了への支払いと同一視しない。
天鳳と雀魂でイベントの単位が異なることも `source` と合わせて解釈する。
複数ロンや責任払いへの具体的な割り当ては別の例で確認する。

`source.scoring_values` は、共通期待値とは別に元の点数関連値を保存する。
雀魂の `point_sum` や、ロン時の `point_zimo_*` も保持するが、
意味や適用条件を確認せずに共通期待値へ転用しない。

`comparison.excluded_fields` は、比較しない項目と理由の配列とする。
空配列は、この例の期待値に比較除外がないことを意味する。
将来の未知フィールドまで比較対象とする意味ではない。
除外対象は `expected` からの相対パスで指定する。

```json
{
  "excluded_fields": [
    {"field": "payments_by_seat", "reason": "liability_payment"},
    {"field": "fu", "reason": "kokushi_fu_not_comparable"}
  ]
}
```

これは除外の形式説明用であり、今回の二つの和了の条件ではない。
符が未記録なら、値は `null`、理由は `not_recorded` とする。
記録された符は役満でも保持し、国士無双の場合は比較から除外する。

## 後続の変換器で確認する範囲

- 副露・槓・抜き北、三麻ツモの実牌譜からの抽出。
- 進行からの状況復元、雀魂の国士無双の符の実記録。
- 複数ロンと責任払いでの支払い・供託・本場の帰属。
- 役の出典 ID と共通 ID の全対応表。

corpus の構造検査と具体例は [scoring ケースの補完](corpus-edge-cases.md)、
データセットの保存と検査は [manifest とデータセット](corpus-manifest.md) を参照する。

合意済みの範囲からモデル・読み書き・検査のテストリストを作り、
一件ずつ Red → Green → Refactor で実装する。
