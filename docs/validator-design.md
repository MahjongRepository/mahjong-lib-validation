# validator パッケージの設計

作成日: 2026-11-03

[全体設計](architecture.md) を具体化し、corpus を入力とする
`mahjong` の正確性検証・性能計測・プロファイルの責務と境界を定める。
scoring の初期検証、benchmark、profile の API・CLI は実装済み。
シャンテン数計算と和了判定については
[CLI 拡張の設計](#シャンテン数計算と和了判定の-cli)を参照する。
確認結果は [実装記録](validator-implementation.md)、出力と API は
[初期版の結果形式](validator-results.md) を参照する。
実装は [テストリスト](validator-implementation.md) から一件ずつ進める。
前身の実装構造を互換性の要件としない。

## 名前・配置・依存

- 配布名・CLI 名は `mahjong-validator`、import 名は `validator` とする。
  リポジトリ名 `mahjong-lib-validation` は変更しない。
- 実装は `packages/validator/src/validator/`、テストは
  `packages/validator/tests/` に置く。設計資料はルートの `docs/` に置く。
- `uv_build` と src レイアウトを採用し、uv workspace に登録済み。
- ルート・corpus・tenhou-converter とともに、最低 Python を 3.15 に統一する。
  全パッケージを導入する開発環境も Python 3.15 以上を使う。
- 実行時依存は workspace の `corpus` と検証対象の `mahjong` とする。
  mahjong の対応バージョン範囲は `>=2.3.0,<3.0` とし、2.3.0 で確認した。
- corpus は validator・mahjong に依存しない。validator は変換器に依存しない。
  元牌譜や天鳳固有の符号を実行時に解釈しない。
- 検証対象は mahjong に限定し、他ライブラリ向けのプラグイン機構は設けない。

全パッケージは Python 3.15 以上を必要とする。
Python 3.11〜3.14 上での mahjong の
実行・計測は初期対応に含めない。将来必要になった場合は、制御側と対象側の
worker の互換性を別途設計する。Tachyon で新しい Python から古い Python の
対象をプロファイルできることを前提にしない。

## 対応範囲と段階

| 段階 | 内容 | 完了条件 |
| --- | --- | --- |
| 初期実装 | corpus v1 scoring の検証 API・CLI | 四麻・三麻、役・符・翻・役満倍率・点数の比較、比較除外、失敗分類、逐次処理と結果保存を確認する |
| 性能計測 | benchmark | 計測範囲、事前検証、入力再生成、プロセス分離、無効標本の検出と生の計測値保存を確認する |
| プロファイル | profile | scoring の計算バッチを tracing / sampling で収集する |

初期実装は `tenhou-ranked-match` の四麻・三麻を対象とする。
`majsoul-ranked-match` は corpus に保存できるが、mahjong へのルール対応を
確認するまで `unsupported` とする。天鳳の設定で代用しない。
役満、抜き北、副露、複数ロン、責任払いのケースも受け取り、
ケースに記録された比較除外とライブラリ側の対応範囲を区別する。

## シャンテン数計算と和了判定の CLI

以下の CLI 拡張は実装済み。

### 対象の指定

`validate`、`benchmark`、`profile` を三つのケース種別で使う。
`DATASET` は単一種別の manifest 付きデータセットとし、
`manifest.json` の `case_type` で実行対象を決める。
対象の指定はデータセットに集約し、既存の scoring の呼び出し方を維持する。
manifest とケースの種別が一致しない場合はコーパス形式のエラーとする。

| `case_type` | 実行対象 | 検証する期待値 |
| --- | --- | --- |
| `scoring` | 得点計算 | 役・符・翻・点数など |
| `shanten` | シャンテン数計算 | 全対象形の最小シャンテン数 |
| `agari` | 牌姿の和了形判定 | 和了形かどうかの真偽値 |

和了判定は牌姿の完成を判定する。役の有無やフリテンなどを含む
対局上の和了可否は、別の検証対象とする。
聴牌と和了形のシャンテン数は、同じ `shanten` 型の別データセットで扱う。
和了判定も同じ `agari` 型を使い、14枚形の正例と13枚形の負例を
別データセットで扱う。
期待値とフィールドの契約は
[corpus の設計](corpus-design.md#和了判定とシャンテン数のケース)、
牌譜からの派生規則は
[天鳳 converter の設計](tenhou-converter-design.md#和了判定シャンテン数コーパスの生成)
を参照する。

### 計算 API と入力準備

- 和了判定は `Agari.is_agari` を一回呼ぶ。残りの手牌と宣言済み面子の
  全構成牌を合わせた34種の枚数配列を渡し、面子の牌種列も第二引数に渡す。
  暗槓を含む槓は四枚分を両方の引数に含める。面子がなければ第二引数は `None`。
- シャンテン数は `Shanten.calculate_shanten` を一回呼ぶ。宣言済み面子を除いた
  残りの手牌だけを34種の枚数配列にし、三麻では `is_three_player=True` を渡す。
  通常形・七対子・国士無双の計算対象の選択は API の既定動作に従う。
- 34形式への変換では赤牌を同じ牌種に合算する。
  入力準備に期待値を使わず、事前検証と計測で同じ引数を用意する。
  結果は `is_agari` または `shanten` の一項目を比較する。
- コマンド、ケース選択、結果保存、バッチ実行は既存の流れを共有する。
  聴牌形と完成形のデータセットは、ケース種別ごとに同じアダプターで処理する。

実装は、コーパスの読み書きと種別照合、牌譜からの各対象の出力、
validator の検証、benchmark、tracing、sampling の順に確認する。
牌譜の変換では、同種牌を残す和了牌の除去、副露・暗槓、三麻の抜き北、
複数ロンと出力順を確認する。pytest では正のシャンテン数、形別の値、
14枚の非和了形も小さな手作りの入力で扱う。
形別の値は各計算方法の違いを確認するテストに使い、CLI の計測単位は最小値とする。

### コマンドとオプション

```console
mahjong-validator validate data/shanten-agari --output artifacts/shanten-agari-check
mahjong-validator benchmark data/shanten-tenpai --limit 20000 --samples 10 --output artifacts/shanten-tenpai-bench
mahjong-validator profile data/agari-complete --limit 20000 --method tracing --output artifacts/agari-complete-trace
mahjong-validator profile data/agari-tenpai --limit 20000 --method sampling --min-seconds 3 --output artifacts/agari-tenpai-sampling
```

| オプション | 対象 | 契約 |
| --- | --- | --- |
| `--output OUTPUT` | 全コマンド | 必須。既存ディレクトリの上書きはエラー |
| `--player-count {3,4}` | 全コマンド | 人数で絞り込む。省略時は全人数 |
| `--case-id ID` | 全コマンド | 繰り返し指定できる。省略時は全 ID |
| `--limit N` | 全コマンド | 絞り込み後の件数上限。正の整数。benchmark と profile では必須 |
| `--samples K` | benchmark | 正の整数。既定値は 10 |
| `--method {tracing,sampling}` | profile | 必須 |
| `--min-seconds SECONDS` | profile の sampling | 反復バッチの最小実行時間。既定値は 3 秒 |
| `--sampling-rate HZ` | profile の sampling | サンプリング頻度。既定値は 1000 Hz |

選択順は manifest に従い、上限に達した後も全件の整合性を検査する。
`validate` で `--limit` を省略した場合は、絞り込みに該当する全件を検証する。
benchmark と profile は、選択した全ケースの事前検証が成功した場合に計測する。
benchmark は標本ごとに worker を起動し、ウォームアップ後に計測用入力を再生成する。
worker は制御側が確認したケース種別、manifest のハッシュ、選択順序のハッシュを照合する。
profile は既存の tracing と sampling の方式を使う。コーパスの読み込み、
入力準備、期待値との比較は、どのケース種別でも計測区間の外に置く。
計測区間と反復・ウォームアップの詳細は
[ベンチマークの設計](validator-benchmark-design.md)と
[プロファイリングの設計](validator-profile-design.md)に従う。

### 出力と終了コード

| コマンド | 保存する成果物 |
| --- | --- |
| `validate` | `summary.json`、`cases.jsonl` |
| `benchmark` | `summary.json`、`cases.jsonl`、`timings.json` |
| `profile` | `summary.json`、`cases.jsonl`、方式に応じて `profile.pstats` または `profile.html` |

`summary.json` と標準出力の summary に `case_type` を記録する。
benchmark と profile の `preflight` にも検証した `case_type` を記録する。
profile の `scope` は `scoring_batch`、`shanten_batch`、`agari_batch` のいずれかとする。
ケース診断には全体位置と case ID を残し、新種別ではシャンテン数または和了形の
期待値と実測値を、既存の項目別比較結果と同じ形式で記録する。

| 終了コード | 意味 |
| --- | --- |
| `0` | 検証または計測が成功した |
| `1` | 検証で不一致、選択ゼロ、未対応、スキップ、計算エラーのいずれかが生じたか、benchmark の標本が計算時の例外で無効になった |
| `2` | 引数、コーパス形式、I/O、worker の照合、または収集基盤のエラー。未対応の `case_type` も含む |

事前検証に失敗した場合はケース診断と失敗の summary を保存する。
benchmark の `timings.json` は空の標本一覧とし、profile の収集ファイルは
生成しない。終了コード `2` では stderr に診断を出し、結果ディレクトリを公開しない。

## 共通部分と実行フロー

共通化するのはケースの選択、入力生成、ライブラリ呼び出し、結果の正規化、
実行情報の記録とする。三つの用途は独立したフローを持つ。
ベンチマーク設定の有無で検証フロー全体を切り替える構成にしない。

```text
corpus ─→ ケース選択 ─→ 入力生成 ─→ mahjong 呼び出し ─→ 結果正規化
                             ↑               ↑               │
                     入力・ルールのみ     期待値を渡さない    ↓
corpus の期待値・比較条件 ─────────────────────────────→ 比較

validate  : 逐次読込 → 一件ずつ計算・比較 → 集計・保存
benchmark : 選択固定 → 事前検証 → 準備・計測 → 区間外で比較 → 集計・保存
profile   : 選択固定 → 事前検証 → 対象範囲を収集 → 成果物・収集情報を保存
```

### モジュールの目安

```text
packages/validator/
├── pyproject.toml
├── src/validator/
│   ├── __init__.py
│   ├── cli.py
│   ├── selection.py
│   ├── adapter.py
│   ├── validation.py
│   ├── preparation.py
│   ├── batch.py
│   ├── benchmark.py
│   ├── profiling.py
│   ├── comparison.py
│   └── reporting.py
└── tests/
```

`selection` はデータセットの走査中に選択件数と順序のダイジェストを
記録する。検証と benchmark worker は同じ走査処理を使う。
`adapter` は mahjong 固有の入力生成・呼び出し・結果正規化、
`validation` は期待値比較と検証フローを担う。
`preparation` は選択したケースの種別に応じて実行可能な呼び出しを準備する。
`batch` は準備済みの呼び出しを順に実行し、benchmark 用の経過時間や
失敗したケースの位置を記録する。profile でも同じバッチ実行関数を使う。
`reporting` は用途別結果の保存と表示を担い、合否や計測方針を決めない。
ファイル分割と内部モデル名は、TDD で利用側を確認しながら調整する。

### ケース選択と corpus 検査

- 一つの manifest 付きデータセットを入力とし、`read_dataset` を使う。
  単体 JSONL の入力、複数データセットの結合、無作為抽出は初期対象外とする。
- manifest のファイル順と行順を保ち、重複するケースもそのまま扱う。
  case ID の一意性を前提にせず、データセット内の位置と組にして識別する。
- 初期の選択条件は人数、case ID、先頭からの件数上限とする。
  条件による絞り込みの後に上限を適用する。選択ゼロは失敗とする。
- 上限に到達しても corpus の読込・検査を最後まで進める。
  後続ファイルのハッシュ・件数・形式の不正を見逃して成功にしない。
  選択しなかったケースでは mahjong を実行しない。
- データセット全件の検査済みと、選択範囲だけの mahjong 検証済みを区別する。
  途中の I/O エラーや形式不正は実行全体の失敗とし、集計済みの部分を
  完全な結果として保存しない。
- manifest の保存バイト列のハッシュ、ファイル情報、選択条件、
  選択した位置・case ID とその順序のダイジェストを実行情報に残す。

### 入力生成とライブラリ呼び出し

- 入力生成関数にはケースの入力・局情報・ルールを渡し、期待値を渡さない。
  役一覧から和了状況を逆算しない。`source.scoring_values` も参照しない。
- `mpsz` の牌を赤牌と枚数を保つ 136 形式へ割り当てる。
  手牌・和了牌・副露を整合した物理牌へ変換し、同種牌の割当順を固定する。
  ドラ表示牌は手牌と同一の物理牌割当を要求する情報として扱わない。
- mahjong が要求する手牌の範囲に合わせ、corpus で別々に保持する
  手牌・和了牌・副露を組み立てる。副露種別・開閉・鳴いた牌・相手、
  場風・自風、和了状況、本場・供託、抜き北、ルールを明示的に変換する。
- 必要な和了状況の `null` を `false` として扱わない。
  必須入力が不明なケースは、理由付き `skipped` とする。
  対応していない既知のルール・機能は `unsupported` とする。
- ルール設定を mahjong の既定値任せにせず、対応表として固定する。
  比較時にも同じ対応表の版を記録する。
- 呼び出しは準備済み入力から mahjong の生の結果を返す。
  一括計算中の戻り値の扱いは実行目的に従い、比較・表示は計算ループの外で行う。
- 生の結果から corpus の役 ID・翻・役満倍率・点数成分へ正規化する。
  未知の役や解釈できない出力を黙って捨てない。
  牌譜固有の役 ID を比較の中間表現にしない。

## 正確性の検証

`validate` は一件ずつ入力生成・計算・正規化・比較を行い、メモリに
全ケース・全結果を保持しない。ケース単位の計算エラーは記録して続行する。
corpus の不正や出力の書込失敗は実行全体の失敗とする。

### 比較項目

`expected` の各項目と `comparison.excluded_fields` を比較の根拠とする。
除外はフィールド単位で適用し、元の理由を報告する。

- 役 ID と各役の翻数・役満倍率を照合する。役の順序は比較しない。
  mahjong 2.1.x は抜きドラを Dora に含めるため、比較時は期待値側の
  `dora` と `nuki_dora` も合算する。この二者の内訳は検証できない。
  元の期待値と正規化結果は保持し、合算の方針を summary に明示する。
- 合計翻・符・合計役満倍率・和了点の区分をそれぞれ照合する。
  通常役の翻と役満倍率を相互に置き換えない。
- 素点、本場分、供託分、和了者の収入、各席の支払いを分けて照合する。
  mahjong の費用内訳からの集計は、入力の人数・親・ロン相手に基づく。
  期待値に合わせて計算結果を補正しない。
- `event_score_deltas` は局の複数和了を合わせた値を含む。
  一件の計算結果と直接比較しない。初期版は項目単位の `unsupported` とし、
  既知の他項目の比較を続ける。イベント単位の集約比較は後続設計とする。
- 本場・供託のある後続ロン（`win_number > 1`）、または比較除外に
  `multiple_ron_allocation_unknown` があるケースでは、入力に個別配分がない。
  `honba_points`、`riichi_stick_points`、`winner_gain`、`payments_by_seat` を
  項目単位の unsupported とする。記録された除外・期待値不足を優先する。
  期待値や元牌譜から配分を逆算しない。素点・役・符等は比較する。
  最初の一件だけでは複数ロンの有無を特定できない corpus v1 の制約があり、
  任意の配分に対応済みとはしない。個別配分の入力表現は後続設計に残す。
- 比較対象の `null` は期待値不足として扱い、0 や空配列と混同しない。
- 役満の符を一律除外しない。国士無双の符、責任払いの支払い、複数ロンの
  制約は corpus に記録された除外条件に従う。
- ライブラリ内部の費用成分の整合性検査を加える場合は、牌譜との一致とは
  別の診断として報告し、期待値をライブラリで再計算する代わりにしない。

### 判定と検証範囲

項目単位では `matched`、`mismatched`、`excluded`、`unavailable`、
`unsupported` を記録する。最後の三つには理由を持たせる。
ケース単位の状態は次のとおりとする。

| 状態 | 意味 |
| --- | --- |
| passed | 一項目以上を比較し、比較した全項目が一致した |
| mismatch | 比較した項目の少なくとも一つが不一致 |
| error | ライブラリのエラー返却・例外、または結果の解釈に失敗した |
| unsupported | 入力のルール・機能が未対応で計算できない |
| skipped | 必須入力が不明、または比較できる期待値が一項目もない |

`passed` でも項目の除外・不足・未対応があり得るため、状態と検証範囲を
別々に報告する。全項目の一致を意味する表現にしない。
ケース全体の未対応・スキップと、計算できたケースの部分比較も区別する。

終了コードは 0 を完了、1 を不一致・計算エラー・検証未成立、
2 を引数不正・corpus 不正・I/O や実行基盤の失敗とする。
選択ゼロ、全件スキップ、全件未対応は 1 とし、検証成功にしない。
一件以上比較できても、ケース全体の skipped / unsupported があれば 1 とする。
項目単位の除外等は件数と理由を表示し、それだけでは終了コードを失敗にしない。
未対応の黙示的な除外や、成功扱いにするオプションは初期版に設けない。

## ベンチマーク

`benchmark` は選択したケースを保持し、すべて同じ条件で事前検証する。
不一致・エラー・ケース全体の未対応・スキップがあれば計測を開始しない。
項目単位の比較範囲も結果に残す。

計測区間、検証のタイミング、結果に保存する条件は
[scoring ベンチマークの設計](validator-benchmark-design.md) に記録する。
準備済み入力のバッチを `perf_counter_ns` で計り、各ケースの戻り値は
その場で破棄する。計測区間には計算 API の呼び出し、バッチのループ、
戻り値の解放に伴う処理が含まれる。

各標本は新しい worker プロセスで取得する。worker はウォームアップ、
計測用入力の再生成、一回の計測を行い、制御側が結果を集計する。
同じ選択の全件検証は事前に行う。計測中に例外が発生した標本は無効とする。

初期の標準条件を次のように定める。

- ウォームアップは同じケースを一回実行する。計測入力は再生成し、
  `Meld` などのインスタンスを再利用しない。
- ライブラリのプロセス内キャッシュはウォームアップ後の状態を保つ。
  同じケースの再実行でキャッシュが有効になり得る測定として記録する。
  コールドキャッシュの測定と称さない。
- GC は有効のままとし、以前の結果の解放と明示的な GC は区間外で行う。
- private API によるキャッシュ消去を標準動作にしない。
  コールド条件や別のウォームアップ方式は、必要な用途が生じた段階で追加する。
- 既定の標本数は 10 とし、正の整数で指定できる。
  計測対象件数は明示させ、全件を無意識に反復しない。
- 生の各標本値、中央値・最小・最大・ばらつき、処理件数、throughput を保存する。
  速さそのものを開発用テストの合否に使わない。

## プロファイル

[scoring プロファイリングの設計](validator-profile-design.md) に収集方式、
範囲、反復、成果物および sampling の収集境界を記録する。
速度の比較には benchmark を使う。

## 環境間の性能比較

比較する環境ごとに、同じデータセット・選択条件・標本数で `benchmark` を
手動実行する。ライブラリの変更による差を確認する場合は、Python の実装・版・
ビルドと validator・corpus の版を揃える。両方の事前検証が成功したことを確認し、
出力された `summary.json` と `timings.json` で実行環境と計測値を照合する。

## API・CLI・保存

公開 API は、データセットと型付き設定を受けて用途別の結果を返す形とする。
`validate_dataset`、`benchmark_dataset`、`profile_dataset` を
候補名とし、具体的な引数と結果型は各段階のテストで確定する。
API は標準出力や `sys.exit` に依存せず、CLI が表示と終了コードを担う。

CLI の使用例を以下に示す。

```text
mahjong-validator validate <dataset> --output <new-result-directory>
mahjong-validator benchmark <dataset> --limit 20000 --samples 10 --output <new-result-directory>
mahjong-validator profile <dataset> --limit 20000 --method tracing --output <new-result-directory>
mahjong-validator profile <dataset> --limit 20000 --method sampling --output <new-result-directory>
```

初期 validate は人数・case ID・上限の選択を提供し、指定なしでは全件を扱う。
benchmark / profile では正の `--limit` を必須とする。

保存先は新しいディレクトリとし、既存結果を上書きしない。
一時ディレクトリに書き、全処理を終えてから公開する。
正しく完了した不一致・計算エラーの検証結果は失敗の証拠として保存する。
中断・corpus 不正・書込失敗の結果は完全な結果として公開しない。

- `summary.json`：結果スキーマの版、用途、完了状態、設定、環境、
  corpus・選択の識別、変換時の失敗・除外情報、用途別の集計。
- `cases.jsonl`：validate の各ケースの状態・項目別診断。逐次書き込む。
- `timings.json`：benchmark の生の計測値、worker 情報と検証結果。
- プロファイラ固有の成果物：profile の HTML / pstats と収集情報。

validate の v1 結果形式は [初期版の結果形式](validator-results.md) に記録した。
その他の JSON スキーマは、その機能を実装する段階で例を作り確定する。
生のライブラリオブジェクトや pickle を共通の結果形式にしない。
大量の一致結果の詳細や個別スタックの保存量は実データで評価する。

## 初期実装で確かめる事項

- mahjong の導入版・公開 API・三麻と抜き北の対応、ルール設定の全項目。
- corpus の全役 ID とライブラリの役・役満倍率の対応。
- 点数区分・費用内訳から正規化できる項目と、ライブラリに出力がない項目。
- 複数ロン・責任払いの除外条件を適用した部分比較の具体例。
- Tachyon の Windows 上での利用条件と、計算バッチの収集開始・終了の同期。
- 入力の再利用・キャッシュの影響と、標本取得に必要な件数・時間。

上記の未確認事項を推測で対応済みにせず、fixture・公式 API・実行確認で
具体化する。機能の実装段階を越えた抽象化は先行して作らない。

## 参考

- [corpus の設計](corpus-design.md)
- [manifest とデータセット](corpus-manifest.md)
- [scoring ケースの補完](corpus-edge-cases.md)
- [Python 3.15 profiling](https://docs.python.org/3.15/library/profiling.html)
- [Tachyon / profiling.sampling](https://docs.python.org/3.15/library/profiling.sampling.html)
- [profiling.tracing](https://docs.python.org/3.15/library/profiling.tracing.html)
