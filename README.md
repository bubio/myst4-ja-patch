# Myst IV: Revelation 日本語化パッチ

Steam Windows版 **Myst IV: Revelation** の字幕・メニューを日本語化する、非公式のファンプロジェクトです。
正規の英語版とWindows内の日本語フォントから、利用者のPCでパッチを生成・適用します。
ゲーム本体・原本アーカイブ・フォント・生成済みゲームデータは配布しません。

## ダウンロード

[v0.1.0 配布ZIP（適用・復元スクリプト入り）](https://github.com/bubio/myst4-ja-patch/releases/download/v0.1.0/myst4-ja-patch-v0.1.0.zip)

ZIPをフォルダーごと展開し、以下の適用手順を実行してください。
必要なPythonやゲーム本体は同梱していません。配布物と変更内容は[リリースページ](https://github.com/bubio/myst4-ja-patch/releases/tag/v0.1.0)で確認できます。

## 対応内容

- 会話・回想・夢・分岐する結末の字幕：240ファイル、空でない1,118区間。
- メニュー・設定・保存・読み込み・確認ダイアログ・ヒント・クレジットの役職や説明。
- 日本語字形の追加、字幕の2行以内への整形、禁則処理、字幕欄の中央80％幅への拡張。
- 人物ごとの口調・用語の統一。方針は[翻訳方針](docs/translation-style.md)を参照。

人名・社名・作品名は、基本的に元の表記を維持します。
翻訳はAIの支援を受けて作成しています。全編の音声照合・通しプレイ・人手による全台詞の校正は未完了です。

## 必要なもの

| 項目 | 条件 |
| --- | --- |
| ゲーム | 正規のSteam Windows版。Steamのゲーム言語を**英語**にする |
| 対応データ | `tools/supported-build.json` に記載したSHA-256と一致する原本。未対応の更新版や変更済みデータへの上書きは行わない |
| OS | Windows 10 / 11。実画面の確認はWindows 11で実施 |
| Python | 64ビット版Python 3.10以降。`py` または `python` コマンドが使えること |
| フォント | 標準ではWindowsの `YuGothM.ttc`（游ゴシックMedium）を使用 |
| 空き容量 | ゲームを置いたドライブに7 GB以上を目安に確保 |
| 初回のネット接続 | Pillowを専用の `.venv` にインストールするために使用 |

ゲームの購入：[Steamストア](https://store.steampowered.com/app/925940/Myst_IV_Revelation/)。
Pythonは[公式サイト](https://www.python.org/downloads/windows/)から入手できます。

## 適用する

1. Steamでゲームの言語を**英語**にし、ゲームを終了する。
2. 上の**配布ZIP**をダウンロードし、フォルダーごと展開する。スクリプトだけを取り出さない。ソース一式は **Code → Download ZIP** からも入手できる。
3. `apply_japanese.ps1` を右クリックし、**PowerShellで実行**する。Windows 11で表示されない場合は「その他のオプションを確認」を開く。
4. 初回は専用のPython環境とPillowを用意し、原本をバックアップして、パッチを生成・適用する。数分かかる場合がある。
5. 「日本語化の適用が完了しました」と表示されたら、Enterキーで閉じる。
6. Steamの言語を**英語のまま**起動し、ゲーム設定の字幕を**ON**にする。

Steamのインストール先と `libraryfolders.vdf` からゲームを探します。
自動検出できない場合は、展開したフォルダーでPowerShellを開き、次のように指定します。

```powershell
.\apply_japanese.ps1 -GameDir 'D:\SteamLibrary\steamapps\common\Myst IV Revelation'
```

既にこの公開版と同じ翻訳が適用されていれば、確認だけで終了します。
他のツールや公開前の試験版で変更済みの場合は、**そのツールの復元機能で原本へ戻してから**適用してください。

スクリプトの実行が組織のポリシーで制限されている場合、このツールはその設定を変更しません。
Python環境を自分で用意して、以下のコマンドを使用することもできます。

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe tools\patch.py apply --game-dir 'D:\SteamLibrary\steamapps\common\Myst IV Revelation'
```

## 元に戻す

1. ゲームを終了する。
2. `restore_japanese.ps1` を右クリックし、**PowerShellで実行**する。
3. 完了を確認してEnterキーで閉じる。

```powershell
.\restore_japanese.ps1 -GameDir 'D:\SteamLibrary\steamapps\common\Myst IV Revelation'
```

`restore_trial.ps1` も同じ復元処理を呼ぶ互換用の名前として用意しています。
復元ではセーブ・字幕設定・ウィンドウ設定を変更しません。

## バックアップと変更対象

変更するのは次の3ファイルです。

```text
data/data.m4b
data/english/data.m4b
data/patch.m4b
```

ゲームフォルダー内の **`.myst4-ja-patch/backup/`** に元データを保存します。
生成済みデータ・適用情報も `.myst4-ja-patch/` 内に置きます。**復元するまで、このフォルダーを削除しないでください。**
元・適用済み双方のSHA-256を確認し、管理外の変更を見つけた場合は処理を止めます。
生成と検証が終わるまでゲーム本体を変更せず、コピー中に失敗した場合は変更済みファイルを原本へ戻します。
Steamの「ゲームファイルの整合性を確認」で日本語化が解除されることがあります。

## 起動しない場合

この公開版の適用処理は、画面設定やWindowsの設定を変更しません。
必要な場合は、ゲームの `bin` フォルダーに `game.dsc` を作り、次の内容でウィンドウ表示を試せます。

```text
{graphic
full_screen ( false )
}
```

既存の `game.dsc` がある場合は、内容を確認せず上書きしないでください。
その他の起動時クラッシュは[Cyan公式サポート](https://cyan.com/docs/myst-iv-wont-launch-crashes-on-launch-can-i-fix-this/)も参照してください。
互換DLLのダウンロード・導入を、このツールが自動で行うことはありません。

## 検証状況

- 手元の原本から生成し、既に実画面で確認したローカル版との字幕・メニュー・字形・UIデータの一致を確認。
- 字幕の開始・終了時刻、音声参照、空の区間、メニューキーと書式指定子を維持。
- 必要な字形の欠落、設定した幅の超過、禁則違反、2行を超える字幕を検査。
- 原本以外のデータの拒否、途中失敗時の復元、文字列・アーカイブの読み書きを単体テスト。
- 全体版の冒頭字幕と1〜2行表示を実画面で確認。全メニュー・全分岐の通しプレイは未実施。

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe tools\patch.py verify --game-dir 'D:\SteamLibrary\steamapps\common\Myst IV Revelation'
```

ゲームを変更せず生成結果を確認する場合：

```powershell
.\.venv\Scripts\python.exe tools\patch.py build --game-dir 'D:\SteamLibrary\steamapps\common\Myst IV Revelation' --output build
```

`build` にも未変更の対応原本が必要です。`build/` のゲーム由来データをGitHubへアップロードしないでください。

## 翻訳の修正

訳文は `translations/ja.json` にあります。字幕は仮想ファイル名と区間番号、メニューは仮想ファイル名と文字列キーで識別します。
原文は利用者の正規ゲームから読み取り、英語原文の対訳コーパスはリポジトリに含めません。
報告時は、場所・話者・表示された日本語・どの点が不自然かを添えてください。
物語の核心に触れる報告には、ネタバレを含むと分かる見出しを付けてください。

## ライセンス

独自のツール・テスト・説明文は [MIT License](LICENSE) です。
**翻訳データはMITの対象外**で、[翻訳データの注意事項](translations/NOTICE.md)が適用されます。
原ゲームや商標、Windowsフォントの権利を本プロジェクトが許諾するものではありません。
詳細は [NOTICE](NOTICE.md) と [外部依存・参照資料](THIRD_PARTY_NOTICES.md)を参照してください。

## Non-goals

- 吹き替え、映像・背景に描かれた文字、日記などのページ画像の全文翻訳。
- 独立した「日本語」の言語選択項目の追加。
- ゲーム本体、原文コーパス、画像・音声・映像・フォント・生成済みアーカイブの配布。
- 他エディション・将来の更新版・他MODとの無条件の互換性。
