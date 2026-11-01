# manifest とデータセット

決定日: 2026-11-01

v1 scoring コーパスを、`manifest.json` と複数の JSONL ファイルで管理する。
ケース単位の仕様は [JSON 例](corpus-json-examples.md) に従う。

## manifest の構造

```json
{
  "schema_version": "v1",
  "case_type": "scoring",
  "generator": {
    "name": "tenhou-converter",
    "version": "0.0.1",
    "settings": {"ruleset": "tenhou-ranked-match"}
  },
  "conversion": {
    "input_count": 1,
    "converted_count": 1,
    "failed_by_reason": {},
    "excluded_by_reason": {}
  },
  "record_count": 11,
  "files": [
    {
      "path": "scoring-000001.jsonl.gz",
      "record_count": 11,
      "sha256": "<64 lowercase hexadecimal characters>"
    }
  ]
}
```

ハッシュ欄は説明用のプレースホルダーである。
実データでは保存ファイル全体のバイト列の SHA-256 を記録する。
gzip のヘッダーや圧縮の違いもファイルの違いとして検出する。

- `files` の配列順がケースの読み込み順を定める。
- ファイル名はデータセット直下の `.jsonl` / `.jsonl.gz` とする。
  絶対パス、親ディレクトリ、サブディレクトリ、重複した名前を認めない。
  大文字小文字を区別しない環境で衝突する名前も重複として拒否する。
  データセット外を指すリンクも読まない。
- ファイル別件数は正の整数、合計件数は非負の整数とする。
  合計はファイル別件数の和と一致しなければならない。
  全件失敗などの調査用には、空のファイル一覧と合計 0 を保存できるが、
  読み込み・検査・公開するデータセットとしては拒否する。
- `generator` は生成した変換器の名前・版・生成条件を記録する。
  `settings` は JSON 値を保持し、corpus は変換器固有の意味を解釈しない。
- `conversion` の単位は入力牌譜。一つの牌譜から複数のケースが出ても
  `converted_count` は一件とする。和了のない牌譜の変換も一件に含める。
- 入力件数は、変換済み件数、失敗理由別件数、意図的な除外理由別件数の
  総和と一致しなければならない。理由は空でない文字列、件数は正の整数。
- 変換失敗を含む manifest は調査用に読み書きできるが、
  データセットの検査・読み込み・公開ではエラーとする。
  意図的な除外は理由と件数を記録し、変換失敗と区別する。
- 空データセットは正常なコーパスとして扱わない。
  ケースがある場合、変換済みの入力牌譜も少なくとも一件必要とする。
- 未知の版・種別・フィールドは拒否する。

## 実装のテストリスト

- [x] manifest の明示したフィールドを型付きモデルとして保持できる。
- [x] 型・必須項目・版、件数の総和、変換結果の内訳を検査する。
- [x] 不正・重複したファイル名とハッシュを拒否する。
- [x] UTF-8 の manifest を読み書きし、不正時にファイル位置を付ける。
- [x] manifest の順序で JSONL と gzip を読み込む。
- [x] 不足ファイル、ハッシュの不一致、件数の不一致を検出する。
- [x] 不正なケースとデータセット外へのリンクを検出する。
- [x] 空入力・変換失敗を含むデータセットを成功扱いしない。
- [x] 指定件数で分割し、順序・件数・保存バイト列のハッシュを記録する。
- [x] 入力の失敗時に不完全なディレクトリを公開しない。
- [x] 既存ディレクトリを上書きしない。
- [x] 独立インストールと Python 3.10・3.15、静的検査を確認する。

一項目ずつ Red → Green → Refactor で実装する。

追加して確認した項目:

- [x] ストリームの処理中に変換器が入力牌譜の集計を更新できる。
- [x] ストリーム終了時に失敗の集計が増えていても公開しない。
- [x] 全件失敗の manifest を調査用のメタデータとして保持できる。
- [x] 空の manifest を正常なデータセットとしては受理しない。

## API

モデルの `Manifest`、`GeneratorInfo`、`ConversionSummary`、`DataFile` は
`corpus.models` に定義し、`Manifest` は `corpus` からも import できる。
以下の関数はすべて `corpus` から import できる。

| API | 動作 |
| --- | --- |
| `parse_manifest(value)` | 型とメタデータの整合性を検査して `Manifest` を返す |
| `read_manifest(path)` | manifest ファイルを読み、構文・形式の不正にパスを付けて報告する |
| `write_manifest(path, manifest)` | 検査後、一時ファイルから置換して manifest を保存する |
| `read_dataset(directory)` | manifest に従ってケースを順に返すジェネレータ |
| `check_dataset(directory)` | 全ファイル・全ケースを最後まで検査し、成功時に manifest を返す |
| `write_dataset(directory, cases, *, generator, conversion, cases_per_file=100000, compress=True)` | 新しいディレクトリに分割出力し、manifest を返す |

```python
from corpus import check_dataset, read_dataset, write_dataset

manifest = check_dataset("data/input-corpus")
write_dataset(
    "data/copied-corpus",
    read_dataset("data/input-corpus"),
    generator=manifest["generator"],
    conversion=manifest["conversion"],
    cases_per_file=100_000,
    compress=True,
)
```

この例は既存データセットのファイル分割を変更する例であり、
変換器固有の牌譜解析は行わない。親ディレクトリの作成は呼び出し側で行う。

### 検査のタイミング

`read_manifest` はメタデータだけを検査する。実ファイルの存在・内容は
`check_dataset` または `read_dataset` で確認する。

`read_dataset` は空入力・変換失敗を最初のケースを返す前に拒否する。
各ファイルは解決後の参照先とハッシュを検査してから読み、
各ケースの形式・整合性を検査する。件数はファイルの終端で照合する。
途中でイテレータを閉じれば、その後のファイルや件数まで確認したことには
ならない。完全な検査が必要な場合は `check_dataset` を使う。
全件をメモリへ保持せず、ファイルを順に処理する。

ID の重複排除や全 ID を記憶する検査は行わず、レコードをそのまま保持する。
manifest にない追加ファイルは読み込み対象にしない。
読み込み中のファイルの書き換えや、同一出力先への同時書き込みはサポートしない。

### 書き込みと変換集計

`write_dataset` は出力先が存在する場合、入力を消費せず `FileExistsError` を
送出する。出力先と同じ親の一時ディレクトリで分割ファイルを作り、
すべて成功した後に manifest を保存してディレクトリを rename する。
メモリへ蓄積するのはファイル一覧と少数の処理中データだけである。
ケース・メタデータの不正、入力の例外、空入力、変換失敗があれば、
一時ディレクトリを除去し、出力先を公開しない。

変換器は渡した `conversion` 辞書をケース生成中に更新できる。
writer 自体は牌譜数を推定・加算しない。最終的な内訳は入力イテレータを
最後まで消費してから検査するため、変換途中の暫定値を最終集計と誤認しない。
開始時点ですでに失敗の集計がある場合もエラーとする。
`write_manifest` 単体では、失敗を含む調査用のメタデータも保存できる。

## TDD の確認記録

未実装 API の失敗に加え、合計件数・変換内訳・ハッシュ・安全でない
ファイル名が受理される Red を確認して検査を追加した。
dataset ではハッシュの未確認、終端件数の未確認、既存出力の拒否前に
入力を消費する問題を再現してから修正した。
また、集計を処理中に更新できない問題と、最後に増えた変換失敗が
公開を止めない問題もテストで確認して修正した。

実際のファイル symlink はこの Windows 環境では作成権限がなく、
対応するテストはスキップする。参照先の解決結果を差し替えるテストでは、
データセット外への参照を拒否することを確認している。

## 確認結果

- 開発環境: 117 件成功、実 symlink のテスト 1 件スキップ。
- sdist を生成し、その sdist から wheel を生成できることを確認。
- wheel をインストールした独立環境の Python 3.10.22・3.15.2 で、
  それぞれ 117 件成功、同じテスト 1 件スキップ。
- インストール済みパッケージの import 元と、実行時依存が空であることを確認。
- Ruff の lint・format、ty、差分の空白検査が成功。

Python 3.11〜3.14 の全テスト、大規模コーパスでの性能、
変換器との結合経路は今回確認していない。
