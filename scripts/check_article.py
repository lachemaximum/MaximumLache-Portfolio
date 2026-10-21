"""公開前チェック。基準は config/check-rules.md。

例:
  python3 scripts/check_article.py --date 2026-10-22          # その日の下書きを全部
  python3 scripts/check_article.py --date 2026-10-22 --log    # 落ちた記事を logs/post_log.md に残す
  python3 scripts/check_article.py drafts/2026-10-22/2.md

1本でも落ちると終了コード 1。
"""

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common

REQUIRED_META = ("title", "date", "slot", "type", "theme", "products", "fact_check")
URL_RE = re.compile(r"https?://[^\s\"'<>)]+")
# 具体的な価格だけを拾う。「1万円台」のような帯は拾わない
PRICE_RE = re.compile(r"[¥￥]\s*\d|\d{1,3}(?:,\d{3})+\s*円|\d{4,}\s*円")


def normalize_title(title):
    return re.sub(r"\s+", "", title)


def count_chars(body):
    text = re.sub(r"<[^>]+>", "", body)
    text = URL_RE.sub("", text)
    text = re.sub(r"[#*>`|\-\[\]()!_]", "", text)
    return len(re.sub(r"\s+", "", text))


def check_file(path, rules, other_titles=()):
    """問題点のリストを返す。空なら合格。"""
    meta, body = common.read_draft(path)
    problems = []

    missing = [k for k in REQUIRED_META if not meta.get(k)]
    if missing:
        problems.append(f"フロントマター不足: {', '.join(missing)}")

    head = [l for l in body.splitlines() if l.strip()][: rules["pr_within_lines"]]
    if not any(m in l for l in head for m in rules["pr_markers"]):
        problems.append(f"PR表記が冒頭{rules['pr_within_lines']}行以内にない")

    rakuten = [u for u in URL_RE.findall(body) if "rakuten.co.jp" in u]
    if not any("hb.afl.rakuten.co.jp" in u for u in rakuten):
        problems.append("楽天のアフィリエイトリンクがない")
    bad = [u for u in rakuten if "hb.afl.rakuten.co.jp" not in u]
    if bad:
        problems.append(f"アフィリエイトでない楽天リンク: {bad[0]}")

    text = URL_RE.sub("", body)
    hits = [p for p in rules["banned_phrases"] if p in text or p in meta.get("title", "")]
    if hits:
        problems.append(f"断定表現: {', '.join(hits)}")

    m = PRICE_RE.search(text)
    if m:
        problems.append(f"価格の直書き: 「{m.group(0)}」")

    chars = count_chars(body)
    if not rules["min_chars"] <= chars <= rules["max_chars"]:
        problems.append(f"文字数 {chars}（基準 {rules['min_chars']}〜{rules['max_chars']}）")
    h2 = len(re.findall(r"^##\s", body, re.M))
    if not rules["min_h2"] <= h2 <= rules["max_h2"]:
        problems.append(f"見出し(##)の数 {h2}（基準 {rules['min_h2']}〜{rules['max_h2']}）")

    title = normalize_title(meta.get("title", ""))
    posted = {
        normalize_title(r["title"]) for r in common.read_post_log() if r["status"] in common.DONE_STATUSES
    }
    if title and (title in posted or title in other_titles):
        problems.append("タイトルが既存の記事と重複")

    if meta.get("fact_check") != "ok":
        problems.append(f"事実確認が終わっていない（fact_check: {meta.get('fact_check', '')}）")

    return problems


def load_rules():
    return common.load_json_block(common.ROOT / "config" / "check-rules.md", "check_rules")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="*")
    ap.add_argument("--date")
    ap.add_argument("--log", action="store_true", help="落ちた記事を logs/post_log.md に残す")
    args = ap.parse_args()

    paths = [Path(f) for f in args.files] or common.draft_paths(args.date or common.today_jst())
    if not paths:
        sys.exit("チェックする下書きがありません")
    rules = load_rules()

    titles = {p: normalize_title(common.read_draft(p)[0].get("title", "")) for p in paths}
    failed = 0
    for p in paths:
        others = {t for q, t in titles.items() if q != p and t}
        problems = check_file(p, rules, others)
        if problems:
            failed += 1
            print(f"NG  {p}")
            for pr in problems:
                print(f"    - {pr}")
            if args.log:
                meta = common.read_draft(p)[0]
                slot = meta.get("slot") or p.stem
                date = meta.get("date") or p.parent.name
                common.append_post_log(date, slot, common.SLOTS.get(int(slot), "") if str(slot).isdigit() else "",
                                       "不合格: " + " / ".join(problems), meta.get("title", ""))
        else:
            print(f"OK  {p}")
    print(f"{len(paths) - failed}/{len(paths)} 本が合格")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
