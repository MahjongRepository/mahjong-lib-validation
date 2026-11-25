# scoring プロファイリングの設計

scoring の処理時間が集中する箇所と、関数の呼び出し回数・呼び出し関係を
調べる。速度の変化は [ベンチマーク](validator-benchmark-design.md) で測る。

## CLI と収集範囲

```text
mahjong-validator profile DATASET --limit N --method tracing --output OUTPUT
mahjong-validator profile DATASET --limit N --method sampling --output OUTPUT
```

`--limit` は正の整数で必須とし、`--player-count` と `--case-id` は
既存の選択規則に従う。manifest 順を保ち、上限到達後もデータセット全体を
検査する。同じ選択を収集前に検証し、空選択、不一致、計算エラー、
ケース全体の未対応・スキップがあれば収集を開始しない。
項目単位の比較除外や期待値不足は既存の判定に従う。

`--method` で `tracing` または `sampling` を明示する。

収集対象はベンチマークと同じ計算バッチとする。準備済み入力を順に
計算 API へ渡し、戻り値をその場で破棄する。ループと戻り値の解放を含む。
コーパスの読み込み、入力生成、事前検証、成果物の書き込みは収集前後に
行う。収集範囲はこのバッチに固定する。

## 方式と反復

| 方式 | 収集方法 | 成果物 |
| --- | --- | --- |
| `tracing` | `profiling.tracing` で対象区間を直接囲む。呼出回数と呼出関係を調べる | `profile.pstats` |
| `sampling` | Tachyon の標準 CLI で対象プロセスのスタックを定期的に取得する。時間分布を調べる | `profile.html` |

tracing の既定は一反復とする。短い処理から標本を得る sampling では、
指定した最短時間に達するまでバッチの完了単位で反復する。
sampling の既定は `--min-seconds 3`、`--sampling-rate 1000` Hz とする。
実行後に、実際の反復回数と処理件数を記録する。

収集前に入力を準備し、必要な反復では準備済み入力を
再利用する。入力が計算で変化しないことを再利用の提供前に検証する。
プロセス内キャッシュは同じ収集内で維持し、ウォームアップの有無、
入力再利用、GC の条件を結果に記録する。

tracing は事前検証と同じプロセスで、検証済みのレコードから入力を
新たに準備する。専用のウォームアップは行わず、事前検証後の
プロセス内キャッシュと実行時の GC 設定を維持する。

## sampling の同期と再利用

worker に検証済みのレコードを渡し、入力準備と 2 回のウォームアップを
済ませてから Tachyon の標準 CLI で `attach` する。
mahjong は得点計算で設定内のドラ翻数などを更新するため、
初回の計算後に入力を記録し、次の計算で値が変化する入力を拒否する。

worker は準備完了時に自身の PID を通知する。Tachyon の
`--realtime-stats` に正の収集カウンターが現れてから worker を開始し、
worker の終了で収集を止めて HTML を生成する。
Windows 11 / CPython 3.15.2 の通常権限でこの経路を確認した。
`sample_batches` が得点計算区間、`wait_for_sampling` が開始待機を表す。
同期や終了処理の標本は HTML に残り、`sample_count` は
Tachyon が HTML に格納した全標本数を表す。
`elapsed_ns` は worker のバッチ反復時間を表す。

対応する Python ビルドと OS で開始・終了の同期、収集件数の取得、
HTML の生成を確認する。Windows では利用可能な権限で実際に収集できるかを
確認する。利用できない環境では理由を返し、利用可能なら tracing の
指定方法を案内する。収集のための権限昇格や方式の自動切替は行わない。

## 結果と失敗

`summary.json` に方式、ケース種別、選択条件と順序の識別情報、事前検証結果、
ケース数、反復回数、実際の処理件数、収集時間、実行環境を保存する。
sampling では実際の収集件数と設定した収集頻度も記録する。
成果物は一時ディレクトリで生成し、収集完了後に新規ディレクトリへ公開する。
事前検証の失敗は診断を残して終了コード 1、収集基盤の失敗や
未対応の方式は終了コード 2 とし、完成したプロファイルとして公開しない。

tracing の結果は `purpose: profile`、`schema_version: v1` とする。
`preflight` に検証結果、選択条件、選択順序のハッシュ、コーパス識別情報、
実行環境を格納する。`settings` にウォームアップ回数、入力再利用、
キャッシュ、GC の条件を格納する。`elapsed_ns` は profiler の開始・停止を
含む経過時間である。事前検証の失敗時は `summary.json` と `cases.jsonl` を保存し、
`complete` は false、`repetitions` と `processed_count` は 0、
`elapsed_ns` は null とする。
