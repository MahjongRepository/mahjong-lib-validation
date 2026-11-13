# 開発ガイド

## ドキュメントの配置

- README.md は利用者向けの情報に限定する。
- 開発向けの情報へのリンクは、この AGENTS.md に記載する。

## 設計資料

開発時は [プロジェクト構成と設計方針](docs/architecture.md) を参照する。
uv workspace の構成、各パッケージの責務と依存関係、
コーパス形式、初期実装の範囲と未決事項を記録している。

corpus パッケージの開発では [corpus パッケージの設計](docs/corpus-design.md)
も参照する。対応範囲、牌・和了状況・期待値の表現方針、
比較条件と、JSON 例で具体化する未決事項を記録している。

具体的なフィールドの検討には
[scoring コーパスの JSON 例](docs/corpus-json-examples.md) を参照する。
この文書の未確定項目は、確定済みの仕様と区別する。

corpus の初期実装と API の確認事項は
[corpus 初期実装のテストリスト](docs/corpus-implementation.md) に記録する。

データセット単位の保存・検査は
[manifest とデータセット](docs/corpus-manifest.md) を参照する。

副露・不明な状況・三麻・複数ロンなどの具体例と補完仕様は
[scoring ケースの補完](docs/corpus-edge-cases.md) に記録する。

共通の役名は [共通の役 ID](docs/corpus-yaku.md) を参照する。

天鳳牌譜の変換器は [天鳳 converter の設計](docs/tenhou-converter-design.md)
を参照する。入力・局面復元・期待値の抽出・出力と、対応段階を記録する。
実装は [天鳳 converter のテストリスト](docs/tenhou-converter-implementation.md)
から一件ずつ進める。

検証処理の原因別分割は、一時的な
[検証分割 TODO](docs/tenhou-converter-validation-todo.md) で管理する。
修正ごとに更新し、全項目の対応完了後にこのリンクと TODO ファイルを削除する。

corpus を使った検証・計測・比較・プロファイルは
[validator パッケージの設計](docs/validator-design.md) を参照する。
実装先は `packages/validator/` とし、
[validator の実装テストリスト](docs/validator-implementation.md) から
一件ずつ進める。

validator の公開 API と保存する JSON の契約は
[validator 初期版の API と結果形式](docs/validator-results.md) を参照する。

## 実装方針

本プロジェクトは開発中であり、利用先も同じプロジェクト内に限られる。
API・モジュール構成・保存形式などの後方互換性を維持する必要はなく、
現在の要件に合うよう変更してよい。互換性維持だけを目的とする
ラッパー・別名・移行処理は設けず、関連する呼び出し元・テスト・
ドキュメントを合わせて更新する。個別のタスクで互換性維持を
明示された場合は、その指示を優先する。

t-wada 氏が説明するテスト駆動開発（TDD）を基本とする。
期待する振る舞いのテストリストを作り、一件ずつ
Red → Green → Refactor の短いサイクルで実装する。
テストリスト全体を先にテストコードへ変換しない。
具体的な進め方は [実装・テスト方針](docs/development.md) を参照する。
