# majsoul-converter の整理チェックリスト

## バッチ変換とレポート

- [x] **個別の牌譜が失敗しても後続の入力を処理する。** 読み込み・デコード・局面復元の失敗を理由別に加算し、診断を記録して次のファイルに進む。入力一覧の取得やデータセットの書き込みに失敗した場合はその時点で停止し、走査の完了状況と実際の公開状態を報告する。この挙動を実装 PR で[入力・出力仕様](../../packages/majsoul-converter/README.md)にも反映する。[バッチ実装](../../packages/majsoul-converter/src/majsoul_converter/datasets.py)
- [x] **全件走査後の失敗を CLI から検証する。** 相対パス順に「正常・不正・正常」の 3 入力を置き、終了コード 1、入力 3・変換 2・失敗 1、`summary_complete=true`、`dataset_published=false`、出力ディレクトリ未作成を確認する。不正な入力にはイベント位置が分かる牌譜を使い、診断のパスと位置も照合する。[変換テスト](../../packages/majsoul-converter/tests/test_conversion.py)
- [x] [corpus の共通レポート](corpus.md)で型・初期化・件数更新・保存を揃える。同じ理由で複数回失敗したときも全件を加算する。天鳳と同じく診断の詳細は先頭 100 件とし、超過分は `omitted_diagnostic_count` で確認できるようにする。
- [x] ファイル探索・SQLite によるソートと、変換件数の集計を別々に読めるよう、`_find_files` と `_input_paths` を入力側にまとめる。相対 POSIX パス順、単一ファイルだけの ID 上書き、UUID → ファイル名のフォールバックは既存の契約。再帰探索のために全パスをメモリへ集める変更は避ける。[入力仕様](../../packages/majsoul-converter/README.md)
- [x] CLI は直下に入力を取り、天鳳と同じ形式で stderr に出力する。成功時は公開状態・変換集計・件数、バッチ失敗時はレポートの JSON を出す。`--report` の有無で出力形式は変わらず、不正な `--cases-per-file 0` は終了コード 2 を返す。レポートの保存に失敗した場合も実際の公開状態を返す。[CLI](../../packages/majsoul-converter/src/majsoul_converter/cli.py)

## 局面変換

- [x] **C901 の対象 `convert_log`** では ID 決定（明示値、記録 UUID、フォールバックの順）をイベントループの外で独立させ、`RecordHule` の全和了ケースの重複検査と登録をまとめる。局開始待ち・局進行中の区別、流局・和了による局終了、末尾の完局検査はループから追える形に保つ。抑制を外して Ruff を実行し、空ログ、未完局、和了内の複数勝者、重複ケース ID、イベント例外の位置と型名を確認する。[変換処理](../../packages/majsoul-converter/src/majsoul_converter/conversion.py)
- [x] `_win_cases` 内の形判定ターゲットは天鳳と同じ 4 種類である。両者で「和了牌を含むか」「期待値が真偽値か向聴数か」の対応を同じ表で検証する。雀魂の和了牌の取り出し方、連続イベントの位置、三麻の抜き北と赤牌の復元は protobuf のフィクスチャで検証する。[共通のテスト表](../../packages/test-data/shape-targets.json) · [変換テスト](../../packages/majsoul-converter/tests/test_conversion.py) · [天鳳の形判定テスト](../../packages/tenhou-converter/tests/test_shape_conversion.py)

バッチ処理と局面変換は別 PR にできる。どちらも小さな response frame から dataset を作り、対象ケースの期待値と validator の結果を確認する。

## 不正な牌譜の診断

- [ ] **副露牌の取得元を、添字を取り出す前に検証する。** `RoundState._open_meld` は `froms` のうち他家の席を指す位置を `(called,)` に展開する。他家の位置が 0 件または複数件なら、牌数との照合より先に Python のアンパック例外が起きる。`convert_log` はイベント位置を補うが、診断からはどのフィールドが不正か読み取れない。先に `tiles` と `froms` の長さを照合し、次に他家の位置がちょうど 1 件かを検査してから、直前の打牌と席・牌を照合する。長さ不一致、他家 0 件、他家 2 件を個別の入力にして、原因とイベント位置を確認する。[副露の復元](../../packages/majsoul-converter/src/majsoul_converter/reconstruction.py) · [イベント例外の処理](../../packages/majsoul-converter/src/majsoul_converter/conversion.py)
- [ ] **局開始時の人数・親の席・場風に個別のエラーを返す。** `RoundState.__init__` は 3 条件を `or` で結び、どれが外れても同じメッセージを返す。人数、人数に依存する親の席、場風の順で検証し、エラーに該当する値を含める。例えば 2 人、三麻で `ju=3`、四麻で `chang=4` の各入力で、同じ局開始イベントから別々の原因を特定できるようにする。[局の初期化](../../packages/majsoul-converter/src/majsoul_converter/reconstruction.py)

## スタイル提案

- [ ] **形判定の期待値をケース構築の前に決める。** `_win_cases` では `cases.append(parse_case(...))` の辞書内に条件式が二重に入り、和了形かどうかと、期待値を真偽値・向聴数のどちらで表すかを同時に読む必要がある。`case_type` を決めた直後に agari と shanten の分岐で `expected` を組み立て、辞書にはその値を渡す。4 ターゲットの和了牌の有無と期待値は既存のテスト表で照合できる。[ケース構築](../../packages/majsoul-converter/src/majsoul_converter/conversion.py) · [形判定のテスト表](../../packages/test-data/shape-targets.json)
- [ ] **海底・河底の成立条件を並べて読めるようにする。** `RoundState.win_input` の `houtei` は辞書内で複数行にまたがり、対になる `haitei` と除外条件が異なる。辞書の直前で `haitei` と `houtei` を並べて計算すると、最終牌でのツモは嶺上を除き、ロンは槍槓と抜き北へのロンを除くという現在の条件を見比べやすい。変更時は通常の最終ツモ・最終打牌に加え、それぞれの除外条件でも出力を照合する。[和了状況の復元](../../packages/majsoul-converter/src/majsoul_converter/reconstruction.py)
