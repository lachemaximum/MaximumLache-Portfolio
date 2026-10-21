"""合格した下書きを、はてなブログの AtomPub API で投稿する。

例:
  python3 scripts/post_hatena.py --date 2026-10-22             # 8時・12時・18時に予約投稿
  python3 scripts/post_hatena.py --date 2026-10-22 --draft     # 下書きとして保存（お試し用）
  python3 scripts/post_hatena.py --date 2026-10-22 --dry-run   # 送る XML を表示するだけ

- 投稿の直前にもう一度公開前チェックを行い、落ちた記事は送らない
- logs/post_log.md で「投稿済」「下書き保存」の枠は飛ばす（二重投稿しない）
- 記事の更新・削除はしない（新規投稿だけ）
"""

import argparse
import base64
import json
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from xml.sax.saxutils import escape

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_article
import common


def entry_xml(meta, body, when, draft_only):
    # 予約投稿：下書き扱いにして hatenablog:scheduled と未来の updated を付ける
    # （お試しで、実際に予約投稿になるかを確認する）
    scheduled = "" if draft_only else "<hatenablog:scheduled>yes</hatenablog:scheduled>"
    categories = "".join(f'<category term="{escape(c)}"/>' for c in common.split_list(meta.get("categories")))
    return f"""<?xml version="1.0" encoding="utf-8"?>
<entry xmlns="http://www.w3.org/2005/Atom" xmlns:app="http://www.w3.org/2007/app" xmlns:hatenablog="http://www.hatena.ne.jp/info/xmlns#hatenablog">
<title>{escape(meta["title"])}</title>
<content type="text/x-markdown">{escape(body.strip())}</content>
<updated>{when.isoformat(timespec="seconds")}</updated>
{categories}
<app:control><app:draft>yes</app:draft><app:preview>no</app:preview></app:control>
{scheduled}
</entry>
"""


def post(xml, hatena_id, blog_id, api_key):
    url = f"https://blog.hatena.ne.jp/{hatena_id}/{blog_id}/atom/entry"
    token = base64.b64encode(f"{hatena_id}:{api_key}".encode()).decode()
    req = urllib.request.Request(
        url,
        data=xml.encode("utf-8"),
        method="POST",
        headers={"Authorization": f"Basic {token}", "Content-Type": "application/atom+xml; charset=utf-8"},
    )
    with urllib.request.urlopen(req, timeout=60) as res:
        text = res.read().decode("utf-8")
    m = re.search(r'<link rel="alternate" type="text/html" href="([^"]+)"', text)
    return m.group(1) if m else ""


def mark_used(codes, date_str):
    data = common.load_used_products()
    data["items"].extend({"itemCode": c, "date": date_str} for c in codes)
    common.save_used_products(data)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--date", default=common.today_jst())
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--draft", action="store_true", help="予約せず下書きとして保存")
    mode.add_argument("--dry-run", action="store_true", help="送信しない")
    args = ap.parse_args()

    if not args.dry_run:
        hatena_id, blog_id, api_key = common.require_env("HATENA_ID", "HATENA_BLOG_ID", "HATENA_API_KEY")
    rules = check_article.load_rules()
    paths = common.draft_paths(args.date)
    if not paths:
        sys.exit(f"drafts/{args.date}/ に下書きがありません")

    titles = {p: check_article.normalize_title(common.read_draft(p)[0].get("title", "")) for p in paths}
    errors = 0
    for p in paths:
        slot = int(p.stem)
        label = common.SLOTS[slot]
        if common.is_done(args.date, slot):
            print(f"skip {p}（投稿ログに記録済み）")
            continue
        problems = check_article.check_file(p, rules, {t for q, t in titles.items() if q != p and t})
        if problems:
            print(f"NG   {p}: {' / '.join(problems)}")
            errors += 1
            continue

        meta, body = common.read_draft(p)
        when = common.slot_datetime(args.date, slot)
        now = datetime.now(common.JST)
        if not args.draft and when <= now:
            # 再実行などで公開時刻を過ぎていたら、少し先に予約し直す
            when = now.replace(second=0, microsecond=0) + timedelta(minutes=10)
            label = when.strftime("%H:%M") + "（遅延）"
        xml = entry_xml(meta, body, when, args.draft)

        if args.dry_run:
            print(f"--- {p}（{label}） ---\n{xml}")
            continue
        try:
            url = post(xml, hatena_id, blog_id, api_key)
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")[:200]
            print(f"ERR  {p}: HTTP {e.code} {detail}")
            common.append_post_log(args.date, slot, label, f"投稿失敗: HTTP {e.code}", meta["title"])
            errors += 1
            continue
        except urllib.error.URLError as e:
            print(f"ERR  {p}: {e.reason}")
            common.append_post_log(args.date, slot, label, f"投稿失敗: {e.reason}", meta["title"])
            errors += 1
            continue

        codes = common.split_list(meta.get("products"))
        status = "下書き保存" if args.draft else "投稿済"
        common.append_post_log(args.date, slot, label, status, meta["title"], url, ", ".join(codes))
        mark_used(codes, args.date)
        print(f"{status} {p} → {url or '(URL 取得できず)'}（{label}）")

    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
