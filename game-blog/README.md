# game-blog

はてなブログに、ゲーム攻略記事と周辺機器の比較記事（楽天アフィリエイト）を毎朝自動で作って投稿する仕組み。
運用の手順とルールは [CLAUDE.md](CLAUDE.md) にある。

## はじめにやること（本人）

1. 楽天アフィリエイトに、はてなブログを登録する
2. 楽天ウェブサービスでアプリを登録し、アプリIDを控える
3. はてなブログの「設定 → 詳細設定 → AtomPub」で、はてなID・ブログID・APIキーを控える
4. `.env.example` を `.env` にコピーして値を入れる（ローカルで動かす場合）
5. Claude Code のクラウド実行環境に、同じ5つの環境変数を設定する
6. 毎朝4時（日本時間）に「CLAUDE.md の手順で今日の分を作って」と送る定期タスクを作る

外部ライブラリは使わない（Python 3.9 以上の標準ライブラリだけで動く）。

## スクリプト

| コマンド | すること |
|---|---|
| `python3 scripts/fetch_products.py --theme <テーマ> --keyword <検索語>` | 楽天APIで商品を取得・絞り込み、`data/products/<日付>.json` に保存 |
| `python3 scripts/build_parts.py --date <日付> --codes <itemCode,...>` | 比較表と「楽天で見る」リンクの HTML を出す |
| `python3 scripts/check_article.py --date <日付> --log` | 公開前チェック。落ちた記事をログに残す |
| `python3 scripts/post_hatena.py --date <日付> [--draft / --dry-run]` | 予約投稿（`--draft` で下書き保存、`--dry-run` で送らずに確認） |

## 仮置きの値

まだ決まっていない数値は、仮の値を入れてある。お試しの結果を見て書き換える。

- 商品の選定基準：レビュー30件以上、評価4.0以上、価格帯ごとに3件、14日以内に使った商品は除外（`config/themes.md`）
- 公開前チェック：本文2,500〜10,000字、`##` 見出し3〜10個（`config/check-rules.md`）

## お試しで確かめること

- 実行環境から楽天APIとはてなAPIに接続できるか
- `post_hatena.py` の予約投稿（`hatenablog:scheduled`）で、本当に予約になるか。ならなければ、下書き保存して公開時刻に公開する別の処理に切り替える
- 楽天APIのエンドポイントが変わっていたら、環境変数 `RAKUTEN_ITEM_SEARCH_URL` で差し替える
