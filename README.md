<h1 align="center">y4u</h1>

<p align="center"><em>日本語 ｜ <a href="README.en.md">English</a></em></p>

<p align="center">
  CAD / GIS・エンジニアリング領域を中心に、事務系以外のソフトウェアを開発しています。<br>
  現在は iOS / クロスプラットフォームの測量・測地アプリに注力中。<br>
  <em>Software engineer in CAD/GIS and engineering domains — currently building geospatial apps for iOS &amp; desktop.</em>
</p>

<p align="center">
  <img alt="C" src="https://img.shields.io/badge/C-00599C?logo=c&logoColor=white">
  <img alt="C++" src="https://img.shields.io/badge/C++-00599C?logo=cplusplus&logoColor=white">
  <img alt="Python" src="https://img.shields.io/badge/Python-3776AB?logo=python&logoColor=white">
  <img alt="C#" src="https://img.shields.io/badge/C%23-512BD4?logo=csharp&logoColor=white">
  <img alt="Swift" src="https://img.shields.io/badge/Swift-F05138?logo=swift&logoColor=white">
</p>

---

## 📱 リリース済みアプリ

測量・測地の現場と学習を支える、日本の測地系に特化したアプリ群です。

| アプリ | 内容 | リンク |
| --- | --- | --- |
| **GeoConverter Pro** | 座標変換専用アプリ。世界測地系／平面直角座標系、セミダイナミック補正・定常時地殻変動補正に対応 | [App Store](https://apps.apple.com/jp/app/geoconverter-pro/id6761740960) ・ [Web](https://gcpro.y42u.net/) |
| **GeoPrism JP** | 測地系のズレやジオイドを地図・ヒートマップで可視化する学習アプリ | [App Store](https://apps.apple.com/app/id6780149823) ・ [Web](https://gmp.y42u.net/) |
| **GeoDiveExa** | RTK-GNSS 対応の高精度位置調査アプリ（座標変換エンジンの原点） | [Web](https://y42u.net/tec001/) |

> **GeoConverter Pro** と **GeoPrism JP** は、GeoDiveExa から抽出した座標変換エンジン **GeoCoreJP**（Swift Package）を共有しています。

---

## 📚 Kindle本（発売中）

日本の測地系の仕組みを解説する「日本の測地系」シリーズ3冊（読む・作る・あそぶ）を、Kindleで発売中です（Kindle Unlimited 対象）。

| 書籍 | 内容 | リンク |
| --- | --- | --- |
| **『日本の測地系がわかる本』**（本編） | 地図の座標はなぜズレるのか。TOKYOからJGD2024まで、百数十年の「座標の引っ越し」を1本の物語で | [Amazon](https://www.amazon.co.jp/dp/B0H971W8WX) |
| **『日本の測地系がわかる本（実装編）』** | 座標変換エンジンをPythonで作って、国土地理院の計算と1mmで一致させる | [Amazon](https://www.amazon.co.jp/dp/B0H97LPNH3) |
| **『日本の測地系Q&A』** | 地図・GPS・座標の「なぜ？」がわかる100問。クイズで腕試しする第3巻 | [Amazon](https://www.amazon.co.jp/dp/B0HF4SJC1L) |

> 🎁 3冊すべて **Kindle Unlimited 対象**（会員は追加料金なしで読めます）。
> 🧩 腕試し用の試食10問（無料・note）: [【地図クイズ10問】緯度1度は何メートル？](https://note.com/amru1957/n/n9cba2ac8d167)

「実装編」の各章「Pythonで動かして確かめる」節で使うテスト用 Python スクリプトを [geodetic-book-py](geodetic-book-py/README.md) 以下に公開しています。

---

## 📝 歴史改変ファンタジー〈円環年代記〉（Kindle・発売中）

もし、あの国の歴史が「ひとつの征服の物語」だったとしたら――。戦国から現代へ、さらに太古と未来へ。生成AIとの共作で書いた歴史改変ファンタジーです。**本編は全6巻で完結し、以降は外伝を刊行しています。** 物語の各巻には、事実と創作を判子で仕分ける「答え合わせ編」付き（Kindle Unlimited 対象）。

**▶ 入口**

- 第1巻『シン・二連環記 ―日出ずる国の円環年代記―』 [Amazon](https://www.amazon.co.jp/dp/B0HC2Y5T6L)
- 【5分で分かる】超入門 ―はじめての方へ―（note・無料） [note.com](https://note.com/amru1957/n/nec43a60fb81d)
- 【完結記念】初見のAIに本編6巻を一気読みさせた書評 ―絶賛も酷評もそのまま―（note・無料） [note.com](https://note.com/amru1957/n/ncf1ea19b6ffe)
- 制作記「12日間で小説を8冊出した話（と、その費用の全部）」（note・無料） [note.com](https://note.com/amru1957/n/n2cc8755586a2)

> note で販売していた旧有料コンテンツ（マガジン・原型版・設定資料集）は公開を終了し、Kindle 版へ統合済みです。

---

## 🧰 プロジェクト

| プロジェクト | 内容 | ライセンス |
| --- | --- | --- |
| [**UwView**](https://github.com/amru195704/UwView) | **45億行クラス**の巨大テキストを省メモリ・高速に閲覧するビューア（Avalonia / .NET 10・Windows / macOS / Linux / WASM）。文字コード自動判定・全文検索・リアルタイム Tail 対応。実測した最大は **258.68GB・4,509,830,821行**（OpenStreetMap アメリカ全土のXML展開・UwView Pro で計測／従来は8.9億行が最大でした）。現状の設定での理論上最大行数は5500億行 | [PolyForm Internal Use License 1.0.0](https://github.com/polyformproject/polyform-licenses/blob/1.0.0/PolyForm-Internal-Use-1.0.0.md) |
| [**UwView Pro**](https://uvp.y42u.net/pro/) 🚀 _発売中（Windows/macOS/Linux 対応）_ | UwView をさらに高速化した商用版。**258.68GB・45億行**の実測に成功（初回オープン5分28秒 → 2回目以降は一瞬）。圧縮サイドカーキャッシュで **2回目以降のオープンが 0.02〜0.07 秒（klogg 比 1,500 倍以上）**、全文検索は **klogg 比 最大約 9 倍**、元ファイルを削除して **約 1/9 サイズ**で保管・閲覧も可能 | 商用（[**買い切り $129／月額 $9 を購入（Polar）**](https://buy.polar.sh/polar_cl_37MuoKb8WjSfLZ7hhjaTTzwAVBxu2XyqbnuWe3aGzbj)） |
| [**runlogger**](https://github.com/amru195704/runlogger) | 旧 Objective-C 製 iOS アプリ「RunLogger」の機能を一部再現した Flutter 製テストアプリ（AI 機能の検証目的） | オープンソース |
| [**RunloggerSWUI**](https://github.com/amru195704/RunloggerSWUI) | 同「RunLogger」を SwiftUI で一部再現したテストアプリ（AI 機能の検証目的） | オープンソース |

> **UwView のライセンスについて**（この要約はライセンス本文に代わるものではありません）:
>
> - 個人、および企業の「社内業務利用」は無料です。
> - 本ソフトウェアの頒布はできません（再配布・製品/サービスへの組込み・転売・第三者への提供・ホスティング提供・OEM 組込みは許可されません）。
> - これらを行う場合は、作者から別途の商用（再配布/OEM）ライセンスが必要です。

> **🚀 UwView Pro（発売中・Windows/macOS/Linux 対応）** → [製品ページ](https://uvp.y42u.net/pro/) ／ [**購入（Polar・買い切り $129／月額 $9）**](https://buy.polar.sh/polar_cl_37MuoKb8WjSfLZ7hhjaTTzwAVBxu2XyqbnuWe3aGzbj) — 大容量ログビューア [klogg](https://klogg.filimonov.dev/) との実測比較（OpenStreetMap 日本全域 47.73GB・892,239,125 行、外付けUSB・RAM32GB・10コア Mac、検索ヒット数は klogg と厳密一致で相互検証済み）:
>
> - **2回目以降のオープン: 0.02〜0.07 秒**（klogg は毎回再索引 約110秒 ＝ **1,500倍以上**）
> - **全文検索 "Tokyo": 14.3 秒**（klogg 120〜135秒 ＝ **約9倍**。大小無視で約8.6倍、正規表現で約4.4倍）
> - **アーカイブ運用: 元ファイルを削除して 48GB→5.3GB（約 1/9）** で保管・そのまま閲覧（チェックサム保護付き）

> **さらに大きな実測（2026-07-26／klogg比較とは別条件）**: OpenStreetMap **アメリカ全土**を XML 展開した **258.68GB・4,509,830,821行（45億行）** を UwView Pro で開いた記録（OSM日本 51GB・8.9億行の約5倍）:
>
> - **初回オープン（索引構築込み）: 5分28秒**（328秒 ＝ 約 789 MB/s）／**2回目以降は一瞬**（`.uwvz` サイドカーから復元）
> - **全文検索は語やヒット数に依らず約34秒で一定**（「New York」34.8秒・100,492件ヒット）
> - **`.uwvz` サイドカー: 28.61GB（元ファイルの約11%）**
> - 総行数 4,509,830,821 は int の上限 2,147,483,647 を超えるため、**行番号を `long` で持つ設計が必須**であることが実証されました

---

## 🧭 開発の歩み

個人開発 iOS/クロスプラットフォームアプリは、GPS ログアプリ **RunLogger** を源流に進化してきました。

```mermaid
flowchart LR
    CADGIS["CAD/GIS (C/C++)"] --> RL["RunLogger<br/>Objective-C・GPSログ"]
    CADGIS --> UW1995
    RL --> GDE["GeoDiveExa<br/>C# / .NET MAUI・RTK-GNSS"]
    GDE --> NAVI["視覚障害者向け歩行者ナビ（受託）<br/>画像認識＋音声操作・iOS"]
    GDE --> TEST["runlogger / RunLoggerSWUI<br/>AI機能テスト（Flutter / SwiftUI）"]
    TEST --> SWIFT["GeoConverter Pro / GeoPrism JP<br/>Swift"]
    UW1995["UwView 1995<br/>C++・大容量テキストビューア（Vector 公開）"] --> UW2026["UwView 2026<br/>C# / Avalonia・全面再構築（Vector公開）"]
    UW2026 --> UWPRO["UwView Pro<br/>C#・高速版（Polarで発売中）"]
```

RunLogger（GPS ログ）を土台に **GeoDiveExa**（C#）を開発。その後、受託で**視覚障害者向けの歩行者ナビ**（目の代わりに *画像認識*、操作は *音声* で行う iOS アプリ）を開発しました。さらに **AI 機能の検証**として runlogger / RunLoggerSWUI を試作し、その知見を活かして Swift で **GeoConverter Pro / GeoPrism JP** を作り込みました。

**UwView** は源流が異なります。1995 年に **C++** で作った大容量テキストビューア（Vector で公開）を、2026 年に **C# / Avalonia** で全面再構築し、さらに高速版 **UwView Pro** へと発展させています。

---

## 👤 バックグラウンド

- **経歴**: 40年以上のソフトウェア開発歴。CAD / GIS から電波・測地分野まで、事務系以外のエンジニアリング領域を専門にしています。
- **主な実績**:
  - **約40年前（1980年代前半）に Apollo ワークステーション上で開発した CAD が、現在も CATV（ケーブルテレビ）設計 CAD として使われ続けています**（[開発当時の話](https://y42u.net/tec001/2024/06/17/1980/)）
  - **地上デジタル放送への移行期に電波伝搬シミュレータを開発**
  - カーナビ用地図データ作成 CAD の開発
- **主分野**: CAD / GIS・エンジニアリング系ソフトウェア開発（事務系以外）
- **資格**: 第１級無線技術者（現・第一級陸上無線技術士）
- **現在**: iOS / クロスプラットフォームの測量・測地アプリ開発

## 🛠 技術スタック

- **言語**: C / C++ / Python / C# / Swift
- **iOS**: Swift / SwiftUI / MapKit
- **クロスプラットフォーム**: .NET MAUI（現場アプリ）・Avalonia UI（デスクトップ / WASM）・Flutter
- **ドメイン**: CAD（CATV 設計 / カーナビ用地図データ作成）・GIS・RTK-GNSS 測位・測地系変換（TKY2JGD / セミダイナミック / pos2jgd）・座標系投影・画像認識・音声認識

---

<p align="center"><sub>🌐 <a href="https://y42u.net/">y42u.net</a></sub></p>
