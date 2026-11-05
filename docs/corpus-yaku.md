# 共通の役 ID

決定日: 2026-11-02

`corpus.models.YakuId` に共通の役名を `Literal` で定義し、
役レコード `Yaku` の `id` に使用する。
ローマ字の小文字とアンダースコアを使い、既存の fixture の名前は維持する。

役の範囲は、指定された
[天鳳牌譜 mjlog形式について：yaku](https://m77.hatenablog.com/entry/2017/05/21/214529#yaku)
の一覧を基にする。既存の三麻 fixture で使う抜きドラも含める。
この文書は corpus 側の共通名を定めるもので、出典の数値 ID への対応や
ルールごとの役の成立条件は変換器の責務とする。

`expected.yaku` の役 ID は一件のケース内で一意とする。
同じ ID の重複は、翻・役満倍率の違いや比較除外の指定にかかわらず
不正入力として拒否する。ドラなどの翻数は一つの役レコードにまとめる。

## 名前の対応

| 役 | YakuId |
| --- | --- |
| 門前清自摸和 | `menzen_tsumo` |
| 立直 | `riichi` |
| 一発 | `ippatsu` |
| 槍槓 | `chankan` |
| 嶺上開花 | `rinshan` |
| 海底摸月 | `haitei` |
| 河底撈魚 | `houtei` |
| 平和 | `pinfu` |
| 断幺九 | `tanyao` |
| 一盃口 | `iipeikou` |
| 自風 東・南・西・北 | `jikaze_ton`・`jikaze_nan`・`jikaze_sha`・`jikaze_pei` |
| 場風 東・南・西・北 | `bakaze_ton`・`bakaze_nan`・`bakaze_sha`・`bakaze_pei` |
| 役牌 白・發・中 | `yakuhai_haku`・`yakuhai_hatsu`・`yakuhai_chun` |
| 両立直（ダブル立直） | `double_riichi` |
| 七対子 | `chiitoitsu` |
| 混全帯幺九 | `chanta` |
| 一気通貫 | `ittsuu` |
| 三色同順 | `sanshoku_doujun` |
| 三色同刻 | `sanshoku_doukou` |
| 三槓子 | `sankantsu` |
| 対々和 | `toitoi` |
| 三暗刻 | `sanankou` |
| 小三元 | `shousangen` |
| 混老頭 | `honroutou` |
| 二盃口 | `ryanpeikou` |
| 純全帯幺九 | `junchan` |
| 混一色 | `honitsu` |
| 清一色 | `chinitsu` |
| 人和 | `renhou` |
| 天和 | `tenhou` |
| 地和 | `chiihou` |
| 大三元 | `daisangen` |
| 四暗刻 | `suuankou` |
| 字一色 | `tsuuiisou` |
| 緑一色 | `ryuuiisou` |
| 清老頭 | `chinroutou` |
| 九蓮宝燈 | `chuuren_poutou` |
| 国士無双 | `kokushi_musou` |
| 小四喜 | `shousuushii` |
| 四槓子 | `suukantsu` |
| 四暗刻単騎 | `suuankou_tanki` |
| 純正九蓮宝燈 | `junsei_chuuren_poutou` |
| 国士無双13面 | `kokushi_musou_13men` |
| 大四喜 | `daisuushii` |
| ドラ | `dora` |
| 裏ドラ | `ura_dora` |
| 赤ドラ | `aka_dora` |
| 抜きドラ | `nuki_dora` |

参照先の 55 種類と、既存の抜きドラを合わせて 56 種類とする。
特殊形の役満も名前は区別し、倍率は独立した `yakuman_multiplier` に保持する。
定義した名前が対象ルールで成立するか、何倍になるかは変換器が判断する。
corpus は役名から倍率を補正したり、未定義の別名を自動変換したりしない。

ダブル立直は役名・和了状況とも `double_riichi` とする。
定義順は単独役満、ダブル役満の四種類、ドラの順にまとめる。
この分類は名前の整理であり、ルールによる役満倍率の決定は変換器の責務とする。
数え役満は役名を追加せず、通常役の内訳と `expected.title="kazoe_yakuman"` で表す。

## テストリスト

- [x] 同じ役 ID の重複を、翻・倍率や比較除外にかかわらず拒否する。
- [x] 未定義の役名を `expected.yaku[i].id` の位置付きで拒否する。
- [x] 自風・場風・通常役・ドラの共通名を保持する。
- [x] 役満の特殊形を別の共通名として保持する。
- [x] 既存 fixture と JSONL・dataset のテスト、静的検査を確認する。

一件ずつ Red → Green → Refactor で実装する。

未定義の役名・空文字・末尾に空白のある役名が受理される Red を確認後、
`Yaku.id` を `str` から `YakuId` に変更した。
既存の実行時型検査が `Literal` を扱うため、役名専用の検査処理は追加しない。

## 確認結果

- 開発環境: 156 件成功、従来の実 symlink のテスト 1 件スキップ。
- sdist・wheel の生成が成功。
- wheel をインストールした Python 3.10.22・3.15.2 の独立環境で、
  それぞれ 156 件成功、同じテスト 1 件スキップ。
- Ruff の lint・format、ty、差分の空白検査が成功。

### 役 ID の重複検査（2026-11-05）

通常役・ドラ・役満について、同じ ID で翻・倍率の異なるレコードが
比較除外の有無によらず受理される Red（6 件）を確認した。
corpus の整合性検査に一意性の検査を追加し、重複した側の
`expected.yaku[i].id` を示す `CorpusError` として拒否する。
validator の比較処理は変更しない。

- 全体 335 件成功、既存の実 symlink のテスト 1 件スキップ。
- Ruff の lint・format、ty、差分の空白検査が成功。
- 今回は開発環境で確認し、独立した旧 Python 環境での再検証は行っていない。
