# validator パッケージの設計

作成日: 2026-11-03

[全体設計](architecture.md) を具体化し、corpus を入力とする
`mahjong` の正確性検証・性能計測・プロファイルの責務と境界を定める。
scoring の初期検証 API・CLI は実装済み。benchmark・profile・compare は未実装である。
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
- validator の最低 Python を 3.15 とする。corpus と tenhou-converter は
  3.11 以上の対応を維持する。全パッケージを導入する開発環境は 3.15 を使う。
- 実行時依存は workspace の `corpus` と検証対象の `mahjong` とする。
  mahjong の初期バージョン範囲は `>=2.1.0,<2.2` とし、2.1.0 で確認した。
- corpus は validator・mahjong に依存しない。validator は変換器に依存しない。
  元牌譜や天鳳固有の符号を実行時に解釈しない。
- 検証対象は mahjong に限定し、他ライブラリ向けのプラグイン機構は設けない。

validator は corpus・tenhou-converter と異なり、Python 3.15 以上を必要とする。
Python 3.11〜3.14 上での mahjong の
実行・計測は初期対応に含めない。将来必要になった場合は、制御側と対象側の
worker の互換性を別途設計する。Tachyon で新しい Python から古い Python の
対象をプロファイルできることを前提にしない。

## 対応範囲と段階

| 段階 | 内容 | 完了条件 |
| --- | --- | --- |
| 初期実装 | corpus v1 scoring の検証 API・CLI | 四麻・三麻、役・符・翻・役満倍率・点数の比較、比較除外、失敗分類、逐次処理と結果保存を確認する |
| 性能計測 | benchmark | 計測範囲、事前検証、入力再生成、プロセス分離、計測後の検証と生の計測値保存を確認する |
| プロファイル | profile | sampling / tracing と calculation / pipeline の範囲を確認する |
| 対象間比較 | compare | 同じ選択・設定による別環境の実行、import 元の確認、比較条件の一致を確認する |

初期実装は `tenhou-ranked-match` の四麻・三麻を対象とする。
`majsoul-ranked-match` は corpus に保存できるが、mahjong へのルール対応を
確認するまで `unsupported` とする。天鳳の設定で代用しない。
役満、抜き北、副露、複数ロン、責任払いのケースも受け取り、
ケースに記録された比較除外とライブラリ側の対応範囲を区別する。

和了判定・向聴数は将来の独立したケース種別とする。
scoring の和了牌姿から作る正例だけの検査を、一般的な正確性検証として
提供しない。初期段階でケース種別や対象ライブラリの汎用実行基盤を作らない。

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
compare   : 同じ選択・設定で別プロセスの benchmark を制御 → 結果比較
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
│   ├── benchmark.py
│   ├── profiling.py
│   ├── comparison.py
│   └── reporting.py
└── tests/
```

`selection` は読込・選択・順序・識別、`adapter` は mahjong 固有の
入力生成・呼び出し・結果正規化、`validation` は期待値比較と検証フローを担う。
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
  一括処理のループと結果保持を共通化するが、その中で比較・表示しない。
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

計測単位は、準備済み入力のバッチに対する一括計算とする。
`perf_counter_ns` で区間を計り、ライブラリ呼び出し・呼び出しループ・
生の結果保持を含める。読込・解凍・入力生成・正規化・比較・表示と、
以前の結果の解放は区間外に置く。

各標本は新しい worker プロセスで取得する。worker は入力準備、
ウォームアップ、計測用入力の再生成、一回の計測、区間外での全結果比較を行う。
制御側は各 worker の結果を集計する。途中の標本の誤りも無視しない。
計測中に例外が発生した標本は無効とし、有効な標本として平均等に混ぜない。

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

プロファイラを起動しない benchmark と、原因調査用の profile を分離する。
profile の時間や sample 数を速度改善・悪化の判定に使わない。

| 方式 | 用途 | 成果物 |
| --- | --- | --- |
| sampling（既定） | Tachyon による時間分布・ボトルネックの調査 | 標準の HTML フレームグラフと収集情報 |
| tracing | `profiling.tracing` による呼出回数・呼出関係の調査 | pstats 形式と収集情報 |

範囲は `calculation`（既定）と `pipeline` を設ける。
calculation は入力準備後の一括計算、pipeline は読込・入力変換・計算・
正規化・比較を対象とし、事前検証と成果物の書込は含めない。
どちらも範囲の名前・反復回数・ケース数・キャッシュ条件を保存する。

sampling は標準 CLI の run / attach を使い、非公開 Python API に依存しない。
calculation では worker が入力準備後に待機し、制御側が attach の収集開始を
確認してから計算を開始させる。終了時にも同期して収集を止める。
入力準備のスタックを関数名で隠すだけで、計算部分だけを収集したと扱わない。
この同期方法は対応 Python / OS で実証してから提供する。
標準 CLI だけで開始確認を実現できない場合は未対応として明示し、
全プロセスの収集を calculation と偽って提供しない。

短い計算は指定時間以上になるまでバッチを反復し、標本を確保する。
反復では入力を再利用するため、benchmark の入力再生成条件との違いを記録する。
再利用で入力が変化しないことは実装時に検査する。
pipeline の反復では読込からやり直す。tracing は対象区間を直接囲む。

Tachyon は Python 3.15 で追加された標準の sampling profiler である。
収集側と対象側は同じ Python minor 版を要求し、pre-release 版や
free-threaded ビルドについても公式の互換条件を確認する。
Windows では管理者権限または `SeDebugPrivilege` が必要とされる。
ツールは自動的に昇格せず、利用できない理由と tracing の選択方法を表示する。
別方式への無言の切替はしない。OS に依存する live TUI は初期対象外とする。

## baseline / candidate の比較

`compare` はそれぞれの Python 実行ファイルと、期待する mahjong の
import ディレクトリを明示的に受け取る。
両環境へ同じ版の validator・corpus を事前に導入し、mahjong だけを
差し替える。ツール内で checkout・依存更新・環境構築は行わない。

- 同じ選択条件と標本数を渡し、worker が返す選択ダイジェストを照合する。
- 実際の mahjong の import 元を確認し、指定先との不一致を失敗にする。
- Python の実装・版・ビルド、validator の版、ルール対応表、計測設定が
  異なる結果を、ライブラリ変更だけの速度比較として扱わない。
- A B、B A の組を交互に実行し、組数は偶数で既定 4 とする。
  各組内では新しい worker による標本を集める。
- 各側の生の標本値と組ごとの中央値、変化率・範囲を保存する。
  中央値の範囲の非重複を補助表示しても、統計的有意差とは呼ばない。
- 両側の事前検証・計測後の検証を要求する。
  corpus・選択・設定の不一致や無効標本があれば有効な比較を作らない。

## API・CLI・保存

公開 API は、データセットと型付き設定を受けて用途別の結果を返す形とする。
`validate_dataset`、`benchmark_dataset`、`profile_dataset`、`compare` を
候補名とし、具体的な引数と結果型は各段階のテストで確定する。
API は標準出力や `sys.exit` に依存せず、CLI が表示と終了コードを担う。

CLI の形は次を基本とする。validate は実装済みで、その他は未実装の使用例である。

```text
mahjong-validator validate <dataset> --output <new-result-directory>
mahjong-validator benchmark <dataset> --limit 20000 --samples 10 --output <new-result-directory>
mahjong-validator profile <dataset> --limit 20000 --method sampling --scope calculation --output <new-result-directory>
mahjong-validator compare <dataset> --limit 20000 --baseline-python <python> --baseline-library <directory> --candidate-python <python> --candidate-library <directory> --output <new-result-directory>
```

初期 validate は人数・case ID・上限の選択を提供し、指定なしでは全件を扱う。
benchmark / profile / compare では正の `--limit` を必須とする。
profiling の時間・rate、compare の組数などの追加引数は各段階で確定する。

保存先は新しいディレクトリとし、既存結果を上書きしない。
一時ディレクトリに書き、全処理を終えてから公開する。
正しく完了した不一致・計算エラーの検証結果は失敗の証拠として保存する。
中断・corpus 不正・書込失敗の結果は完全な結果として公開しない。

- `summary.json`：結果スキーマの版、用途、完了状態、設定、環境、
  corpus・選択の識別、変換時の失敗・除外情報、用途別の集計。
- `cases.jsonl`：validate の各ケースの状態・項目別診断。逐次書き込む。
- `timings.json`：benchmark / compare の生の計測値、worker 情報と検証結果。
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
- Tachyon の Windows 上での利用条件と、calculation の収集開始・終了の同期。
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
