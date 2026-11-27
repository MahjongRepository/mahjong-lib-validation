# majsoul-converter の整理チェックリスト

## バッチ変換とレポート

- [x] **個別の牌譜が失敗しても後続の入力を処理する。** 読み込み・デコード・局面復元の失敗を理由別に加算し、診断を記録して次のファイルに進む。入力一覧の取得やデータセットの書き込みに失敗した場合はその時点で停止し、走査の完了状況と実際の公開状態を報告する。この挙動を実装 PR で[入力・出力仕様](../../packages/majsoul-converter/README.md)にも反映する。[バッチ実装](../../packages/majsoul-converter/src/majsoul_converter/datasets.py)
- [x] **全件走査後の失敗を CLI から検証する。** 相対パス順に「正常・不正・正常」の 3 入力を置き、終了コード 1、入力 3・変換 2・失敗 1、`summary_complete=true`、`dataset_published=false`、出力ディレクトリ未作成を確認する。不正な入力にはイベント位置が分かる牌譜を使い、診断のパスと位置も照合する。[変換テスト](../../packages/majsoul-converter/tests/test_conversion.py)
- [x] [corpus の共通レポート](corpus.md)で型・初期化・件数更新・保存を揃える。同じ理由で複数回失敗したときも全件を加算する。天鳳と同じく診断の詳細は先頭 100 件とし、超過分は `omitted_diagnostic_count` で確認できるようにする。
- [x] ファイル探索・SQLite によるソートと、変換件数の集計を別々に読めるよう、`_find_files` と `_input_paths` を入力側にまとめる。相対 POSIX パス順、単一ファイルだけの ID 上書き、UUID → ファイル名のフォールバックは既存の契約。再帰探索のために全パスをメモリへ集める変更は避ける。[入力仕様](../../packages/majsoul-converter/README.md)
- [x] CLI は直下に入力を取り、成功時は manifest 全体の JSON、変換失敗時は診断文を stderr に出す。共通レポートの導入後も `--report` の有無でこの出力形式が変わらないことと、不正な `--cases-per-file 0` の終了コード 1 を確認する。天鳳と引数定義を共用する場合に後者が argparse エラーの 2 に変わり得る。[CLI](../../packages/majsoul-converter/src/majsoul_converter/cli.py)

## 局面変換

- [ ] **C901 の対象 `convert_log`** では ID 決定（明示値、記録 UUID、フォールバックの順）をイベントループの外で独立させ、`RecordHule` の全和了ケースの重複検査と登録をまとめる。局開始待ち・局進行中の区別、流局・和了による局終了、末尾の完局検査はループから追える形に保つ。抑制を外して Ruff を実行し、空ログ、未完局、和了内の複数勝者、重複ケース ID、イベント例外の位置と型名を確認する。[変換処理](../../packages/majsoul-converter/src/majsoul_converter/conversion.py)
- [ ] `_win_cases` 内の形判定ターゲットは天鳳と同じ 4 種類である。両者で「和了牌を含むか」「期待値が真偽値か向聴数か」の対応を同じ表で検証する。雀魂の和了牌の取り出し方、連続イベントの位置、三麻の抜き北と赤牌の復元は protobuf のフィクスチャで検証する。[変換テスト](../../packages/majsoul-converter/tests/test_conversion.py) · [天鳳の形判定テスト](../../packages/tenhou-converter/tests/test_shape_conversion.py)

バッチ処理と局面変換は別 PR にできる。どちらも小さな response frame から dataset を作り、対象ケースの期待値と validator の結果を確認する。
