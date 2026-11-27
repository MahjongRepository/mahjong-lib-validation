# validator の整理チェックリスト

validator の実装には `noqa: C901` がない。レビューの単位は、検証と測定が共有する事前検証、および測定方式ごとの処理とする。

- [ ] **事前検証と結果公開の境界を明示する。** benchmark と profile は別モジュールの `_validate_dataset` を直接呼び、staging 内で一度書いた `summary.json` を各コマンドの要約で上書きしている。検証結果の収集と最終要約の書き出しを分け、各コマンドが自身の要約を一度だけ保存する。profile で選択ケースを保持するオプション、validate の逐次処理、全方式の診断ファイルを維持する。[検証処理](../../packages/validator/src/validator/validation.py) · [ベンチマーク](../../packages/validator/src/validator/benchmark.py) · [プロファイル](../../packages/validator/src/validator/profiling.py)
- [ ] **事前検証の失敗と測定自体の失敗を区別する。** 空の選択では worker を起動せず、事前検証の診断を含む結果を公開する。tracing の書き込み失敗や sampling の接続失敗では出力先を公開しない。benchmark の sample がエラーを返した場合は後続 sample を打ち切り、統計を出さない。各経路の終了コード、成果物、要約の `complete` を変更前後で照合する。[ベンチマークテスト](../../packages/validator/tests/test_benchmark.py) · [プロファイルテスト](../../packages/validator/tests/test_profiling.py)
- [ ] **`profile_dataset` の方式別処理をまとめる。** 現在は settings の作成と実際の収集で tracing / sampling の分岐が離れている。方式固有の設定と結果の組み立てを近づける。事前検証失敗時にも設定が出ること、sampling のみの `sample_count`、tracing の pstats と sampling の HTML をテストする。時間測定の外で入力を準備する境界、worker のウォームアップと入力再利用条件を保つ。[プロファイル実装](../../packages/validator/src/validator/profiling.py) · [sampling worker テスト](../../packages/validator/tests/test_sampling_worker.py)

事前検証・出力整理を先に、方式別の整理を後に分割できる。各 PR では `validate`、`benchmark`、`profile` を既存の引数で起動し、選択件数・順序・ダイジェストを含む JSON と終了コードを確認する。測定値そのものは実行ごとに変動するため、記録形式と測定範囲を照合する。[CLI テスト](../../packages/validator/tests/test_cli.py) · [選択テスト](../../packages/validator/tests/test_selection.py)
