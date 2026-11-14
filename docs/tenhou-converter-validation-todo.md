# 天鳳 converter の検証分割 TODO

作成日: 2026-11-14

原因別の診断を具体化するための、一時的な確認・作業リスト。
レビューで挙げた26か所を記録し、対応状況をチェックで管理する。

## 進め方

- 一件ずつ内容を確認し、修正と適切な検証が完了したら、その変更と一緒にチェックを付ける。
- 分割対象は、異なる失敗原因が同じ診断にまとめられている箇所とする。
  同じ原因や同じ制約を表す条件は、機械的に分割しない。
- 拒否・受理の条件を維持し、短絡評価が担っていた安全性と検証順序を保つ。
  `reason`・項目・イベント位置などの診断情報を維持し、原因別にメッセージを分ける。
- テストはエラーメッセージの文言を固定せず、原因ごとの入力と拒否動作・診断位置を確認する。
  既存テストの文言依存は必要に応じて調整する。
- メソッド分割や周辺の整理は、このリストだけを理由に追加しない。
- 全項目の対応完了後、このファイルと `AGENTS.md` のこのファイルへのリンクを削除する。

## 局面復元：13か所

対象: [reconstruction.py](../packages/tenhou-converter/src/tenhou_converter/reconstruction.py)

- [x] 01. `RoundState.check_tile()`
  — 136形式の範囲外と、三麻では使わない二〜八萬を分ける。
  四麻・三麻の範囲外、三麻の除外範囲、正常な境界値をテストし、
  `reason`・項目・イベント位置の維持を確認した。メッセージの文言は固定しない。
- [x] 02. `RoundState.finish_draw()` の精算情報
  — 本場・供託の不一致、`sc` の要素数不正、三麻の不使用席の点数情報を分ける。
  各原因の拒否と四麻・三麻の正常な精算を変更前後で確認した。
  `reason`・項目・イベント位置を維持し、拒否時は局を終了済みにしない。
- [x] 03. `RoundState.draw()`
  — ツモのタイミング・手番の不正、残り枚数不足、既出の牌IDを分ける。
  各原因の拒否と、通常・応答フェーズでの残り1枚のツモを変更前後で確認した。
  エラーの分類・位置情報と、拒否時に局面を変更しない動作を維持した。
- [x] 04. `RoundState.discard()`
  — 打牌のタイミング・手番の不正と、手牌にない牌の打牌を分ける。
  各原因の拒否と、手出し・ツモ切りの受理を変更前後で確認した。
  エラーの分類・位置情報と、拒否時に局面を変更しない動作を維持した。
- [x] 05. `RoundState.reach()` の宣言（`step == 1`）
  — タイミング・手番の不正、宣言待ち・成立済み、門前ではない状態を分ける。
  各原因の拒否と、暗槓を含む門前手での宣言の受理を変更前後で確認した。
  エラーの分類・位置情報と、拒否時に局面を変更しない動作を維持した。
- [ ] 06. `RoundState.reach()` の成立確認（`step == 2`）
  — 宣言がない状態と、直前の行為が本人の宣言打牌ではない状態を分ける。
- [ ] 07. `RoundState.consume_call()` の他家からの副露
  — 副露できないタイミング、鳴いた牌の位置の欠落、供給者の不一致、牌IDの不一致を分ける。
- [ ] 08. `RoundState.consume_call()` の三麻制約
  — チーと、存在しない席からの副露を分ける。
- [ ] 09. `RoundState.consume_call()` の自分の手番での行為
  — タイミング・手番の不正と、直前の行為がツモではない状態を分ける。
- [ ] 10. `RoundState.dora()`
  — 追加表示の予定がない状態、既出の牌ID、表示牌の上限到達を分ける。
- [ ] 11. `RoundState.situation()` の和了照合
  — 直前の行為が和了に対応しない状態、供給者・牌IDの不一致、同じ人の重複和了、
  和了者数の上限、他の和了後のツモを分ける。
- [ ] 12. `RoundState._check_agari_tiles()` の手牌
  — 記録内の牌ID重複と、復元した手牌との不一致を分ける。
- [ ] 13. `RoundState._check_agari_tiles()` の副露・抜き北
  — 抜き北の牌ID重複、復元した抜き北との不一致、復元した副露との不一致を分ける。

## 得点・副露符号：8か所

対象: [scoring.py](../packages/tenhou-converter/src/tenhou_converter/scoring.py)、
[melds.py](../packages/tenhou-converter/src/tenhou_converter/melds.py)

- [ ] 14. `scoring.yaku_values()`
  — 役IDの重複と、通常役・役満の分類不一致を分ける。
- [ ] 15. `scoring.expected_values()` の `ten`
  — 要素数不正、点数区分の範囲外、符・点数の負数を分ける。
- [ ] 16. `scoring.expected_values()` の `sc`
  — 要素数不正と、三麻の不使用席の点数情報を分ける。
- [ ] 17. `scoring.expected_values()` の点数配分
  — 本場相当額の負数、和了者自身の支払い、個別記録での供託相当額の負数、
  個別記録での他家への加点を分ける。共有された複数ロンの例外条件を維持する。
- [ ] 18. `melds.decode_meld()` のチー
  — 順子パターンの範囲外、上家以外からのチー、未使用ビットを分ける。
- [ ] 19. `melds.decode_meld()` のポン・加槓
  — 牌パターンの範囲外、供給者が自分、未使用ビット、ポン・加槓フラグの同時指定を分ける。
- [ ] 20. `melds.decode_meld()` の抜き北
  — 下位ビットの形式不正と、牌IDが北ではない状態を分ける。
- [ ] 21. `melds.decode_meld()` の暗槓・大明槓
  — 牌IDの範囲外と、未使用ビットを分ける。

副露符号の検証では、`invalid()` に原因を渡すなどして、
`unknown_meld_code` の分類と位置情報を保ったままメッセージを具体化する。

## 入力・ルール・出力設定：5か所

- [ ] 22. [conversion.extract()](../packages/tenhou-converter/src/tenhou_converter/conversion.py) の `ba`
  — 要素数不正、本場と局の記録の不一致、供託の負数を分ける。
- [ ] 23. [parser.parse_xml()](../packages/tenhou-converter/src/tenhou_converter/parser.py) の文書構造
  — ルート直下の文字列、イベントの入れ子、イベント内・イベント間の文字列を分ける。
- [ ] 24. [rules.player_count()](../packages/tenhou-converter/src/tenhou_converter/rules.py) の対応範囲
  — コンピューター対局、非対応ルールのフラグ、段位戦以外のロビーを分ける。
  対応外ルールの除外扱いと、従来の検証順序を維持する。
- [ ] 25. [sources.log_id_from_path()](../packages/tenhou-converter/src/tenhou_converter/sources.py)
  — 非対応拡張子と、拡張子を除いたIDが空の状態を分ける。
- [ ] 26. [datasets.convert_files()](../packages/tenhou-converter/src/tenhou_converter/datasets.py) の出力設定
  — 分割件数の型不正、分割件数が0以下、圧縮指定の型不正を分ける。

## 現状維持とする箇所

- `start()` の `oya` と `expected_values()` の `paoWho` は、現在の短い検証を維持する。
- `_check_seed()` の本場・供託の非負条件と、サイコロ2個は、同じ制約としてまとめる。
- `_check_scores()` の三麻の不使用席は、点数・手牌を同じ原因としてまとめる。
- `check_settlement()` の既知値判定や、立直成立待ちの例外条件は、検証の適用条件として維持する。
- パスの一致・包含、既存ファイル・リンクは、同じ出力先制約としてまとめる。
