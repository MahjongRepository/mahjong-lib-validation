# 開発ガイド

## 構成

この uv workspace は、牌譜由来の期待値を使って `mahjong` の計算を検証・計測する。

| パッケージ | 責務 |
| --- | --- |
| `packages/corpus` | 共通ケース形式、manifest、データセットの読み書きと整合性検査 |
| `packages/tenhou-converter` | 天鳳牌譜からの局面復元とコーパス生成 |
| `packages/validator` | ケースの検証、ベンチマーク、プロファイリング |

変換器と validator は corpus に依存する。牌譜由来の期待値は変換器で抽出し、
`mahjong` の呼び出しは validator で行う。
[現行仕様](docs/reference.md)と[残課題](docs/roadmap.md)を参照する。
利用者向けのコマンドは [README](README.md) に記載する。

## 開発と検証

ルートで Python 3.15 と uv を使う。

```console
uv sync --locked --all-packages --python 3.15
uv run --no-sync ruff check
uv run --no-sync ruff format --check
uv run --no-sync ty check
uv run --no-sync python -m pytest
```

- テストは各パッケージの `tests/` に置く。共有 fixture は `conftest.py` に置く。
- 振る舞いを変更するときは、小さなテストで期待する結果を定め、Red → Green → Refactor で進める。
- 期待値は仕様、牌譜、小さな手計算などから独立して求める。検証対象のライブラリの出力を期待値に流用しない。
- 小さな fixture で変換と異常入力を確認し、パッケージをまたぐ変更は牌譜から検証結果までの経路も確認する。大規模な牌譜や計測速度に依存する確認は通常のテストから分離する。
- API や保存形式の変更では、workspace 内の呼び出し元、テスト、文書を合わせて更新する。後方互換性の要件は個別のタスクに従う。

初期実装時の設計、検証記録、テストリストは[アーカイブ](docs/archive/initial-implementation/README.md)を参照する。
