# プロジェクト構成と設計方針

決定日: 2026-11-01

本書は、`references/benchmark/` の後継として開発する
mahjong-lib-validation の設計方針を記録する。
以下は実装の指針であり、記載したディレクトリやコマンドが
現在利用できることを示すものではない。

## 目的と対象

- 牌譜から検証用コーパスを作成し、そのコーパスを使って
  `mahjong` パッケージの正確性と性能を検証する。
- 検証対象は `mahjong` パッケージに限定する。
  複数ライブラリ向けのプラグイン機構は設けない。
- 牌譜変換もこのプロジェクトに含める。
  最初は天鳳の XML（mjlog）を入力とする。
- houou-logs の SQLite から直接牌譜を読み込む経路も検討する。
  雀魂牌譜への対応は将来の拡張とする。
- 特定の牌譜取得ツールを必須にしない。
  検証・計測処理は、牌譜取得元や変換器ではなく
  共通コーパスの仕様に依存する。

## 採用する構成

uv workspace で複数の Python パッケージを管理する。
牌譜変換器は入力元ごとに独立したパッケージとし、
検証・計測・比較・プロファイルは一つのパッケージの
サブコマンドとして提供する。
コーパスの共通処理も独立した小さなパッケージにする。

初期段階では次の三つを作成し、雀魂対応時に変換器を追加する。

| パッケージ | 責務 | 固有の実行時依存 |
| --- | --- | --- |
| corpus | 共通モデル、読み書き、形式・整合性の検査 | 当初は標準ライブラリを基本とする |
| tenhou-converter | 天鳳牌譜から共通コーパスへの変換 | 当初は標準ライブラリを基本とする |
| validation | `mahjong` の検証・計測・比較・プロファイル | `mahjong` |
| majsoul-converter（将来） | 雀魂牌譜から共通コーパスへの変換 | `protobuf` など |

corpus の配布名・import 名は、ともに `corpus` とする。
validation と将来の雀魂変換器は役割名であり、
配布名、import 名、CLI 名は実装時に確定する。

天鳳変換器の名前・初期対応範囲・変換フローは
[天鳳 converter の設計](tenhou-converter-design.md) で具体化した。
配布名・CLI 名は `tenhou-converter`、import 名は `tenhou_converter` とする。
同文書の API・CLI は実装前の設計である。
初期実装から四麻・三麻に対応し、SQLite 入力は後続段階とする。

### 分割の理由と依存方向

雀魂変換器に必要な `protobuf` は、天鳳変換器や検証ツールには
必要ない。変換器を別パッケージにして、利用するツールに応じた
依存だけをインストールできるようにする。

```text
tenhou-converter ──→ corpus
majsoul-converter ─→ corpus
validation ────────→ corpus

majsoul-converter ─→ protobuf
validation ────────→ mahjong
```

- 変換器は validation に依存しない。
- corpus は変換器、`protobuf`、`mahjong` に依存しない。
- `Meld`、`HandConfig` などの `mahjong` 固有オブジェクトは
  validation 内で生成する。
- 期待値を検証対象の `mahjong` で計算して埋めない。
  牌譜の記録から取得し、欠落や解釈上の制約は明示する。

workspace は共通のロックファイルを持つ。
パッケージの依存分離と、実行環境の分離は別の問題として扱う。
独立利用できることは、各パッケージをクリーンな環境に
インストールして確認する。
baseline と candidate の比較では、それぞれの対象を
別プロセス・必要に応じて別の Python 環境で実行する。

### ディレクトリ構成の目安

```text
mahjong-lib-validation/
├── pyproject.toml                 # workspace・開発ツール設定
├── uv.lock
├── packages/
│   ├── corpus/
│   │   ├── pyproject.toml
│   │   ├── src/corpus/
│   │   │   ├── models.py
│   │   │   ├── readers.py
│   │   │   ├── writers.py
│   │   │   └── checks.py
│   │   └── tests/
│   ├── tenhou-converter/
│   │   ├── pyproject.toml
│   │   ├── src/tenhou_converter/
│   │   │   ├── cli.py
│   │   │   ├── sources.py
│   │   │   ├── parser.py
│   │   │   └── extraction.py
│   │   └── tests/
│   ├── validation/
│   │   ├── pyproject.toml
│   │   ├── src/mahjong_lib_validation/
│   │   │   ├── cli.py
│   │   │   ├── execution/
│   │   │   ├── validation/
│   │   │   ├── benchmark.py
│   │   │   ├── comparison.py
│   │   │   ├── profiling.py
│   │   │   └── reporting.py
│   │   └── tests/
│   └── majsoul-converter/          # 対応時に追加
├── docs/
├── data/                          # 大規模コーパス。Git 管理対象外
├── artifacts/                     # 実行結果・プロファイル
└── references/
```

各パッケージは `src/` レイアウトを採用する。
内部のファイル分割は実装規模に合わせて調整する。

## 牌譜変換の境界

天鳳と雀魂の変換器は、それぞれ独立した CLI を提供する。
天鳳の mjlog ファイルと houou-logs SQLite は、
同じ天鳳変換器の異なる入力経路として扱う。

```text
mjlog ファイル ────────┐
                      ├→ 天鳳解析 → ケース抽出 → 共通コーパス
houou-logs SQLite ─────┘

雀魂牌譜 ───────────────→ 雀魂解析 → ケース抽出 → 共通コーパス
```

SQLite 入力経路は牌譜 ID と牌譜内容の読み出しを担い、
天鳳形式の解析・場況の復元・ケース抽出はファイル入力と共有する。
天鳳の XML 応答を並べた形式の扱いも天鳳解析部分に閉じ込める。
houou-logs のコードへの依存は必須としない。

以下は CLI の使用イメージであり、未実装である。
天鳳の CLI 名は `tenhou-converter` に確定し、その他の CLI 名は仮名称とする。

```text
tenhou-converter mjlog <input-directory> --output <corpus-directory>
tenhou-converter houou-db <database> --output <corpus-directory>
majsoul-to-corpus ...

mjvalidate corpus check <corpus-directory>
mjvalidate validate <corpus-directory>
mjvalidate benchmark <corpus-directory>
mjvalidate compare <corpus-directory> ...
mjvalidate profile <corpus-directory>
```

## コーパスの保存形式

基本形式は UTF-8 の JSON Lines（JSONL）とし、
gzip 圧縮した `.jsonl.gz` にも対応する。
一行に一件の独立した JSON オブジェクトを保存する。

大規模コーパスは複数ファイルに分割し、
データセット単位の情報を `manifest.json` に保存する。
小さなテストデータや取り出した失敗例には非圧縮 JSONL を使える。

```text
corpus/
├── manifest.json
├── scoring-000001.jsonl.gz
├── scoring-000002.jsonl.gz
└── ...
```

manifest には次の情報を記録する方針とする。

- コーパススキーマのバージョン。
- 変換器のバージョンと生成条件。
- データファイルの一覧、順序、件数、ハッシュ。
- 入力件数、変換失敗・除外の件数と理由の集計。

ハッシュの対象と具体的なフィールドは
[manifest とデータセット](corpus-manifest.md) に記録する。

### 他形式を初期採用しない理由

| 形式 | 評価 |
| --- | --- |
| TSV | 副露・役・支払いなどの可変長データに、セル内の独自表記が必要になる |
| Parquet などのバイナリ | 列単位の分析には有用だが、初期段階では専用依存や目視確認の手間が増える |
| SQLite | 条件検索や索引には有用だが、当初の中心用途はケースの順次読み込みである |
| JSONL | 可変長・入れ子のデータを表現でき、一件の抽出・共有・順次処理を行いやすい |

容量や読み込み性能の優劣は、実データで測定する。
SQLite 出力やバイナリ形式は、具体的な検索・性能要件が
生じた時点で検討する。入力元の SQLite 対応と、
コーパス自体の SQLite 保存は別の判断とする。

## コーパスの内容

最初の scoring コーパスは「一件＝一つの和了」とする。
各行は、manifest のスキーマ情報と合わせて解釈でき、
他のケースや元牌譜を読まずに計算・比較を実行できる情報を持つ。

| 区分 | 保持する内容 |
| --- | --- |
| 識別・出典 | ケース ID、天鳳／雀魂、牌譜 ID、局、本場、和了者、同一局内の和了順 |
| 計算入力 | 手牌、副露、和了牌、ドラ表示牌、場風・自風、和了状況、ルール |
| 期待値 | 役と各翻数、合計翻、符、役満倍率、出典から確認できる点数・支払い |
| 比較条件 | 検証可能な項目、比較対象外の項目と理由 |

天鳳の属性辞書や副露コードをそのまま実行時に解釈する構成にはせず、
変換時に共通の意味を持つデータへ整理する。
同じ牌姿でも場況・点数・支払いが異なり得るため、
初期段階では重複排除しない。

具体的なスキーマの確定前に、少なくとも次を定義する。

- 手牌に和了牌や副露を含むか。
- 牌番号、赤牌、副露、抜きドラの表現。
- 役の識別子、翻数と役満倍率の区別。
- 点数が素点・本場込み・供託込みのどれを意味するか。
- 不明値・未対応・比較対象外とゼロの区別。
- 出典固有の値の対応と、元の記録に制約がある場合の扱い。
- ケース ID とレコード順序を安定させる規則。

和了判定・向聴数は scoring とは異なるケース種別として
追加できる構造にする。ただし、和了牌姿だけでは負例や一般の
向聴数の期待値は得られない。検証できる範囲を明記し、
必要な期待値を持つデータは別途用意する。

## 検証・計測で維持する性質

- コーパスの読み込み、解凍、`mahjong` 用入力生成は
  ライブラリ計測のタイマー外に置く。
- 通常の性能計測とプロファイルを分離する。
- ウォームアップ、キャッシュ、入力再利用の方針を明示し、
  同じ設定で比較する。
- baseline と candidate には同じケースと順序を渡す。
  実際に import した `mahjong` の場所も確認する。
- コーパスの識別情報、選択したケース、実行設定、ライブラリの版と
  import 元、Python の版、各回の計測値を記録する。
- 不一致、実行エラー、未対応、期待値不足によるスキップを区別する。
  空入力や全件スキップを検証成功として扱わない。
- 変換時の欠落・失敗・除外を報告する。
  不完全な出力を正常完了したコーパスとして扱わない。

## 初期実装の範囲と未決事項

最初は三つのパッケージを用意し、天鳳 mjlog の読み込みから
scoring コーパスの出力、`mahjong` の正誤検証までを通す。
その後、計測・比較・プロファイルを移植・整理する。

以下は後続の設計・実装で確定する。

corpus に関する決定事項と残る未決事項は
[corpus パッケージの設計](corpus-design.md) に記録する。

- validation と将来の雀魂変換器の配布名・import 名、CLI 名、オプション。
- コーパススキーマ、manifest、互換性のルール。
- houou-logs SQLite 入力を実装する時期と対応スキーマ。
- コーパスの分割単位とファイルサイズの目安。
- ルール差、役満、複数ロン、責任払いなどの具体的な比較条件。
- 比較対象の環境指定・構築方法と結果ファイルのスキーマ。

## 参考

- 前身: `references/benchmark/README.md`
- [uv workspaces](https://docs.astral.sh/uv/concepts/projects/workspaces/)
- [PyPA: src layout vs flat layout](https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/)
- [JSON Lines](https://jsonlines.org/)
