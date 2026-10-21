"""商品 JSON から、記事に貼る比較表と「楽天で見る」リンクの HTML を作る。

例:
  python3 scripts/build_parts.py --date 2026-10-22 --codes shop:item1,shop:item2
  python3 scripts/build_parts.py --date 2026-10-22 --specs drafts/2026-10-22/specs.json

--specs には、事実確認したスペックを {"itemCode": {"列名": "値", ...}} の形で渡す。
価格は表に出さない（価格帯のラベルだけ出す）。
"""

import argparse
import json
import sys
from html import escape
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common


def short_name(name, limit=40):
    return name if len(name) <= limit else name[:limit] + "…"


def link(item, text="楽天で見る"):
    return f'<a href="{escape(item["url"])}" target="_blank" rel="nofollow sponsored noopener">{escape(text)}</a>'


def table(items, specs):
    spec_cols = []
    for it in items:
        for col in specs.get(it["itemCode"], {}):
            if col not in spec_cols:
                spec_cols.append(col)
    head = ["商品", "価格帯", *spec_cols, "評価", "リンク"]
    lines = ['<table class="product-compare">', "<thead><tr>" + "".join(f"<th>{escape(h)}</th>" for h in head) + "</tr></thead>", "<tbody>"]
    for it in items:
        s = specs.get(it["itemCode"], {})
        cells = [
            escape(short_name(it["name"])),
            escape(it["tier"]),
            *(escape(str(s.get(c, "-"))) for c in spec_cols),
            f'★{it["reviewAverage"]}（{it["reviewCount"]}件）',
            link(it),
        ]
        lines.append("<tr>" + "".join(f"<td>{c}</td>" for c in cells) + "</tr>")
    lines += ["</tbody>", "</table>"]
    return "\n".join(lines)


def cards(items):
    out = []
    for it in items:
        img = f'<img src="{escape(it["image"])}" alt="" loading="lazy">' if it.get("image") else ""
        out.append(
            '<div class="product-card">'
            f"{img}<p><strong>{escape(short_name(it['name'], 60))}</strong></p>"
            f"<p>{link(it, '楽天で価格を見る')}</p></div>"
        )
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--date", default=common.today_jst())
    ap.add_argument("--codes", help="使う itemCode をカンマ区切りで。省略すると全部")
    ap.add_argument("--specs", help="スペック列の JSON ファイル")
    ap.add_argument("--only", choices=["table", "cards"], help="片方だけ出す")
    args = ap.parse_args()

    data = json.loads((common.ROOT / "data" / "products" / f"{args.date}.json").read_text(encoding="utf-8"))
    by_code = {it["itemCode"]: it for it in data["items"]}
    if args.codes:
        codes = common.split_list(args.codes)
        unknown = [c for c in codes if c not in by_code]
        if unknown:
            sys.exit(f"商品 JSON にない itemCode: {', '.join(unknown)}")
        items = [by_code[c] for c in codes]
    else:
        items = data["items"]
    specs = json.loads(Path(args.specs).read_text(encoding="utf-8")) if args.specs else {}

    parts = []
    if args.only != "cards":
        parts.append(table(items, specs))
    if args.only != "table":
        parts.append(cards(items))
    print("\n\n".join(parts))


if __name__ == "__main__":
    main()
