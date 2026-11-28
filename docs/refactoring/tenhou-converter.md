# tenhou-converter の整理チェックリスト

## PR 1 — バッチ変換とレポート

- [x] [corpus の共通レポート](corpus.md)に `convert_files` と `_record_input_failure` を接続する。既知の非対応ルールは除外、壊れた入力は失敗として加算し、後続ファイルも処理する。診断は先頭 100 件を保持し、超過分は件数だけ記録する。失敗を含む全件走査では `summary_complete=true` と `dataset_published=false` が両立する。[バッチ実装](../../packages/tenhou-converter/src/tenhou_converter/datasets.py)
- [x] `tenhou-converter mjlog` の成功時は stderr に公開状態・変換集計・件数の JSON を出す。バッチ失敗時の JSON、引数エラーの終了コード 2、レポート保存失敗時に実際の公開状態を返す経路も維持する。既存出力・不正な shard サイズを入力走査前に拒否する順序を含め、既存テストで比較する。[CLI](../../packages/tenhou-converter/src/tenhou_converter/cli.py) · [バッチテスト](../../packages/tenhou-converter/tests/test_batch.py)

## PR 2 — 牌譜復元と得点の C901（4 件）

- [x] **`convert_log`** は時系列のループを残し、AGARI のケース登録、ID 重複検査、勝者・終了状態の更新を一まとまりにする。連続 AGARI は同じ局の複数ロンになり得るため、終了済み局の一般的な拒否より先に扱う。ダブロン、流局後の和了、末尾の未完局で分岐順と最終精算の検査を確認する。[変換処理](../../packages/tenhou-converter/src/tenhou_converter/conversion.py)
- [x] **`decode_meld`** はビット形式の判定順（チー → ポン・加槓 → 抜き北 → その他の槓）を入口に残し、長いチーとポン・加槓の復号を形式別に切り出す。ビット配置のコメントを復号処理と一緒に移す。複数の意味を持つビット、鳴いた牌の添字、不正コードの理由とフィールド `m` を照合する。[復号処理](../../packages/tenhou-converter/src/tenhou_converter/melds.py) · [副露テスト](../../packages/tenhou-converter/tests/test_melds.py)
- [x] **`RoundState.consume_call`** は相手の捨て牌を使う副露と、自分のツモ後の操作で、検査条件と消費牌が異なる。前者の打牌元・現物・三麻制約の検査を切り出し、手牌から消費する処理は一か所に保つ。一発の中断、加槓で追加牌だけを消費すること、抜き北後の嶺上ツモを局面テストで確認する。[局面復元](../../packages/tenhou-converter/src/tenhou_converter/reconstruction.py) · [局面テスト](../../packages/tenhou-converter/tests/test_situations.py)
- [x] **`expected_values`** は `ten`・`sc` 属性の検査、個別和了の支払い照合、共有精算時の比較除外に分ける。三麻の未使用席、国士の符、包と複数ロンが重なるときの除外理由の優先順を維持する。手計算または牌譜由来の期待値で金額・null・除外理由を比較する。[得点処理](../../packages/tenhou-converter/src/tenhou_converter/scoring.py) · [得点テスト](../../packages/tenhou-converter/tests/test_scoring.py) · [精算テスト](../../packages/tenhou-converter/tests/test_settlement.py)

各関数で抑制を外して Ruff を実行し、併記された PLR0912・PLR0915 も再評価する。レビュー量が多ければ得点・精算を独立させる。XML フィクスチャから生成したケースは [validator の統合テスト](../../packages/validator/tests/test_integration.py)でも確認する。

## PR 3 — 共有精算の判定を局末まで引き継ぐ

- [x] `convert_log` は同じ局の AGARI の `sc` を比較して共有精算を識別するが、`RoundState.check_settlement` は最初のケースの `riichi_stick_points is None` から同じ判定を復元している。このため、供託点の比較除外を変更する際に、局末の残高検査で選ばれる計算経路まで考慮する必要がある。最初の得点ケースの登録時に判定済みの `shared_scores` を局状態に保持し、精算にもその値を使う。個別精算と共有精算のダブロンで次局の開始残高を照合し、共有時の本場・供託の出力と除外理由も維持する。[変換処理](../../packages/tenhou-converter/src/tenhou_converter/conversion.py) · [局末の検査](../../packages/tenhou-converter/src/tenhou_converter/reconstruction.py) · [精算テスト](../../packages/tenhou-converter/tests/test_settlement.py)

## PR 4 — AGARI の副露属性の読み取りを共通化する

- [x] `RoundState._check_agari_tiles` と得点ケースを組み立てる `extract` は、どちらも任意属性 `m` を読み、各値を同じ勝者の席で `decode_meld` に渡す。属性がなければ空リスト、あれば記録順に復号する処理を小さな関数にまとめる。局面との照合では副露をソートして比較する一方、得点ケースでは牌譜順を出力している。複数の副露を復元順と異なる順序で AGARI に記録したケースで出力順を確認し、三麻の抜き北は引き続き通常の副露から除く。[局面との照合](../../packages/tenhou-converter/src/tenhou_converter/reconstruction.py) · [得点ケースの生成](../../packages/tenhou-converter/src/tenhou_converter/conversion.py)

## スタイル提案（任意）

- [x] **`_extract_shape` の期待値をケースの組み立て前に決める。** 現在は `expected` の値の中で、ケース種別と手牌が完成形かどうかの二段階で条件式を読んでいる。`case_type` を決めた直後に `if` / `else` で期待値の辞書を用意すると、和了判定は真偽値、向聴数は完成形で −1・聴牌形で 0 という対応を一か所で読める。[手牌形のケース生成](../../packages/tenhou-converter/src/tenhou_converter/conversion.py#L332)
- [x] **`RoundState.discard` の検査と状態更新を空行で区切る。** `player.hand.remove(tile136)` の直前に空行を置く。そこまでで手番と打牌の所在の検査が終わり、その行から手牌・打牌数・局の進行状態を更新すると分かる。[打牌処理](../../packages/tenhou-converter/src/tenhou_converter/reconstruction.py#L324)
