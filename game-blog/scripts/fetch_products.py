"""楽天市場の商品検索 API で商品を取得し、基準で絞り込んで data/products/<日付>.json に保存する。

例:
  python3 scripts/fetch_products.py --theme ラピトリキーボード --keyword "ラピッドトリガー キーボード"
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common

# 楽天側でエンドポイントが変わったときは、環境変数で差し替えられる
ENDPOINT = os.environ.get(
    "RAKUTEN_ITEM_SEARCH_URL",
    "https://app.rakuten.co.jp/services/api/IchibaItem/Search/20220601",
)
TIER_LABELS = ["エントリー", "ミドル", "ハイエンド"]


def search(app_id, affiliate_id, keyword, hits):
    params = {
        "applicationId": app_id,
        "keyword": keyword,
        "hits": hits,
        "sort": "-reviewCount",
        "availability": 1,
        "format": "json",
        "formatVersion": 2,
    }
    if affiliate_id:
        params["affiliateId"] = affiliate_id
    url = ENDPOINT + "?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=30) as res:
            return json.load(res).get("Items", [])
    except urllib.error.HTTPError as e:
        sys.exit(f"楽天 API エラー（{keyword}）: HTTP {e.code} {e.read().decode('utf-8', 'replace')[:300]}")


def recently_used(exclude_days, date_str):
    since = datetime.strptime(date_str, "%Y-%m-%d") - timedelta(days=exclude_days)
    return {
        item["itemCode"]
        for item in common.load_used_products()["items"]
        if datetime.strptime(item["date"], "%Y-%m-%d") >= since
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--theme", required=True)
    ap.add_argument("--keyword", action="append", required=True, help="複数指定できる")
    ap.add_argument("--date", default=common.today_jst())
    args = ap.parse_args()

    app_id, = common.require_env("RAKUTEN_APP_ID")
    affiliate_id = os.environ.get("RAKUTEN_AFFILIATE_ID", "")
    if not affiliate_id:
        print("注意: RAKUTEN_AFFILIATE_ID が未設定です。アフィリエイトリンクにならず、公開前チェックで落ちます", file=sys.stderr)
    rules = common.load_json_block(common.ROOT / "config" / "themes.md", "product_criteria")
    used = recently_used(rules["exclude_days"], args.date)

    found = {}
    for i, kw in enumerate(args.keyword):
        if i:
            time.sleep(1.1)  # 楽天 API は 1 秒に 1 回まで
        for item in search(app_id, affiliate_id, kw, rules["hits"]):
            found.setdefault(item["itemCode"], item)

    candidates = [
        it for it in found.values()
        if it.get("availability") == 1
        and it.get("reviewCount", 0) >= rules["min_review_count"]
        and it.get("reviewAverage", 0) >= rules["min_review_average"]
        and not any(ng in it.get("itemName", "") for ng in rules["ng_words"])
        and it["itemCode"] not in used
    ]
    candidates.sort(key=lambda it: it["itemPrice"])

    # 価格順に3等分し、各価格帯で評価の高いものを残す
    picked = []
    n = len(candidates)
    for t, label in enumerate(TIER_LABELS):
        tier = candidates[n * t // 3 : n * (t + 1) // 3]
        tier.sort(key=lambda it: (it["reviewAverage"], it["reviewCount"]), reverse=True)
        for it in tier[: rules["per_tier"]]:
            images = it.get("mediumImageUrls") or []
            picked.append({
                "itemCode": it["itemCode"],
                "name": it["itemName"],
                "tier": label,
                # 価格は価格帯の判定用。記事には書かない
                "price": it["itemPrice"],
                "url": it.get("affiliateUrl") or it["itemUrl"],
                "shop": it.get("shopName", ""),
                "reviewCount": it["reviewCount"],
                "reviewAverage": it["reviewAverage"],
                "image": images[0] if images and isinstance(images[0], str) else "",
            })

    out = common.ROOT / "data" / "products" / f"{args.date}.json"
    payload = {
        "date": args.date,
        "theme": args.theme,
        "keywords": args.keyword,
        "fetched_at": datetime.now(common.JST).isoformat(timespec="seconds"),
        "items": picked,
    }
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{len(found)} 件中 {len(candidates)} 件が基準を通過、{len(picked)} 件を保存: {out.relative_to(common.ROOT)}")
    for it in picked:
        print(f"  [{it['tier']}] {it['itemCode']}  ★{it['reviewAverage']}（{it['reviewCount']}件） {it['name'][:40]}")
    if not picked:
        sys.exit("基準を通過した商品がありません。検索語か、config/themes.md の基準を見直してください")


if __name__ == "__main__":
    main()
