# validator の整理チェックリスト

validator の実装には `noqa: C901` がない。レビューの単位は、検証と測定が共有する事前検証、および測定方式ごとの処理とする。

- [x] **事前検証と結果公開の境界を明示する。** benchmark と profile は別モジュールの `_validate_dataset` を直接呼び、staging 内で一度書いた `summary.json` を各コマンドの要約で上書きしている。検証結果の収集と最終要約の書き出しを分け、各コマンドが自身の要約を一度だけ保存する。profile で選択ケースを保持するオプション、validate の逐次処理、全方式の診断ファイルを維持する。[検証処理](../../packages/validator/src/validator/validation.py) · [ベンチマーク](../../packages/validator/src/validator/benchmark.py) · [プロファイル](../../packages/validator/src/validator/profiling.py)
- [x] **事前検証の失敗と測定自体の失敗を区別する。** 空の選択では worker を起動せず、事前検証の診断を含む結果を公開する。tracing の書き込み失敗や sampling の接続失敗では出力先を公開しない。benchmark の sample がエラーを返した場合は後続 sample を打ち切り、統計を出さない。各経路の終了コード、成果物、要約の `complete` を変更前後で照合する。[ベンチマークテスト](../../packages/validator/tests/test_benchmark.py) · [プロファイルテスト](../../packages/validator/tests/test_profiling.py)
- [x] **`profile_dataset` の方式別処理をまとめる。** 現在は settings の作成と実際の収集で tracing / sampling の分岐が離れている。方式固有の設定と結果の組み立てを近づける。事前検証失敗時にも設定が出ること、sampling のみの `sample_count`、tracing の pstats と sampling の HTML をテストする。時間測定の外で入力を準備する境界、worker のウォームアップと入力再利用条件を保つ。[プロファイル実装](../../packages/validator/src/validator/profiling.py) · [sampling worker テスト](../../packages/validator/tests/test_sampling_worker.py)

事前検証・出力整理を先に、方式別の整理を後に分割できる。各 PR では `validate`、`benchmark`、`profile` を既存の引数で起動し、選択件数・順序・ダイジェストを含む JSON と終了コードを確認する。測定値そのものは実行ごとに変動するため、記録形式と測定範囲を照合する。[CLI テスト](../../packages/validator/tests/test_cli.py) · [選択テスト](../../packages/validator/tests/test_selection.py)

## 追加レビュー

### 動作上の問題

- [ ] **sampling が正常な長時間バッチをタイムアウト扱いする。** worker はバッチを完走してから `min_seconds` に達したかを調べる。一方、親は開始通知から `min_seconds + 30` 秒で待機を打ち切る。例えば下限が 3 秒で 1 バッチが 35 秒なら、worker は設計どおり計算中でも収集失敗となり、HTML は公開されない。接続待ちの期限と計算中の停止判定を分ける。修正時は時計とプロセス待機を差し替え、長い最終バッチの完走と接続失敗時の後始末をそれぞれ検証する。[親の待機処理](../../packages/validator/src/validator/sampling_profile.py#L144) · [worker の終了条件](../../packages/validator/src/validator/sampling_worker.py#L36) · [既存のバッチ境界テスト](../../packages/validator/tests/test_sampling_worker.py)

### 既存処理の整理

- [ ] **CLI の選択条件の変換と結果出力を各 1 か所にまとめる。** 3 つのハンドラーが同じ位置引数で `Selection` を組み立て、同じ JSON 出力と終了コード返却を繰り返している。選択条件を増やすと各コマンドで変更が必要になる。`main` で選択条件を一度作り、各ハンドラーには固有の引数で API を呼んで要約を返す役割を残す。共通の出力処理は現在の例外処理の範囲に置き、非 ASCII 文字、末尾改行、終了コードを維持する。[CLI ハンドラーと main](../../packages/validator/src/validator/cli.py#L66)
- [ ] **benchmark worker の照合エラーに失敗した項目を含める。** manifest のハッシュ、ケース種別、選択順序のダイジェストのどれが違っても、同じ診断を返す。worker の標準エラーは親が利用者へ伝えているので、失敗した比較項目を示すだけでデータセットの差し替えと選択処理の調査を切り分けやすくなる。測定開始前に照合する順序は維持する。[worker の照合](../../packages/validator/src/validator/benchmark_worker.py#L31) · [親の診断処理](../../packages/validator/src/validator/benchmark.py#L38)

### スタイル提案

- [ ] **和了・向聴の検証で、計算の準備と実行を読み分けやすくする。** `_validate_value` の `actual = prepare(case)()` は、末尾の括弧が対象ライブラリの呼び出しを表す。同じ `try` 内で `calculate = prepare(case)` と `actual = calculate()` の 2 文にすると、準備と実行の順序が見える。両段階の例外を同じケースの `error` として記録する挙動は保てる。[値の検証](../../packages/validator/src/validator/validation.py#L138)
