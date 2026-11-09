# 外部依存と参照資料

ゲーム本体、外部ツールの実行ファイル、Windowsフォントは同梱していません。
依存ライブラリは利用者の環境へインストールし、字形は端末内のフォントから生成します。
本プロジェクトのMIT Licenseは、これらの外部資産には適用されません。

| 対象 | 用途・権利情報 |
| --- | --- |
| [Pillow](https://github.com/python-pillow/Pillow) | フォントのラスタライズとTGA画像生成。利用者がpipで導入。[ライセンス原文](https://github.com/python-pillow/Pillow/blob/main/LICENSE)を参照 |
| Windowsの游ゴシック | 追加字形の生成元。各利用者のWindowsにあるフォントをローカルで使用。フォント・生成画像をリポジトリには含めない |
| [MystIVAssetExplorer](https://github.com/jnm2/MystIVAssetExplorer) | M4Bの形式を調べる際の参照資料。C#ソースや実行ファイルは同梱していない |
| Myst IV: Revelation | 必須のゲーム本体。著作権・商標は各権利者に帰属 |

Pillowやフォントを別途再配布する場合の権利処理は、このリポジトリでは行いません。

## Non-goals

依存ソフトウェアやフォントのライセンスを置き換えること、原ゲームや互換DLLの配布。
