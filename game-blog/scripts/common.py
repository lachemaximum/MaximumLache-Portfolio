"""scripts 共通の小さなヘルパー。外部ライブラリなし（標準ライブラリのみ）で動かす。"""

import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JST = timezone(timedelta(hours=9))

# 枠番号 → 公開時刻
SLOTS = {1: "08:00", 2: "12:00", 3: "18:00"}

POST_LOG = ROOT / "logs" / "post_log.md"
USED_PRODUCTS = ROOT / "data" / "used_products.json"
# この状態の枠は、再実行しても投稿しない
DONE_STATUSES = ("投稿済", "下書き保存")


def today_jst():
    return datetime.now(JST).strftime("%Y-%m-%d")


def load_env():
    """.env を読み、まだ設定されていない環境変数だけを入れる（実行環境側の設定を優先）。"""
    path = ROOT / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def require_env(*names):
    load_env()
    missing = [n for n in names if not os.environ.get(n)]
    if missing:
        sys.exit(f"環境変数が足りません: {', '.join(missing)}（.env か実行環境の設定に入れてください）")
    return [os.environ[n] for n in names]


def load_json_block(md_path, label):
    """Markdown 内の ```json <label> ... ``` ブロックを読む。"""
    text = Path(md_path).read_text(encoding="utf-8")
    m = re.search(r"```json[ \t]+" + re.escape(label) + r"\s*\n(.*?)```", text, re.S)
    if not m:
        sys.exit(f"{md_path} に ```json {label} ブロックがありません")
    return json.loads(m.group(1))


def read_draft(path):
    """下書きファイルを (フロントマターの dict, 本文) に分ける。"""
    text = Path(path).read_text(encoding="utf-8")
    meta = {}
    m = re.match(r"---\s*\n(.*?)\n---\s*\n", text, re.S)
    if not m:
        return meta, text
    for line in m.group(1).splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            meta[key.strip()] = value.strip()
    return meta, text[m.end():]


def split_list(value):
    return [v.strip() for v in (value or "").split(",") if v.strip()]


def slot_datetime(date_str, slot):
    hh, mm = SLOTS[int(slot)].split(":")
    d = datetime.strptime(date_str, "%Y-%m-%d")
    return d.replace(hour=int(hh), minute=int(mm), tzinfo=JST)


def draft_paths(date_str):
    folder = ROOT / "drafts" / date_str
    return sorted(p for p in folder.glob("*.md") if p.stem.isdigit() and int(p.stem) in SLOTS)


def read_post_log():
    """投稿ログの表を dict のリストで返す。"""
    rows = []
    if not POST_LOG.exists():
        return rows
    for line in POST_LOG.read_text(encoding="utf-8").splitlines():
        if not re.match(r"\|\s*\d{4}-\d{2}-\d{2}\s*\|", line):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        cells += [""] * (7 - len(cells))
        rows.append(dict(zip(("date", "slot", "scheduled", "status", "title", "url", "products"), cells)))
    return rows


def append_post_log(date_str, slot, scheduled, status, title="", url="", products=""):
    def clean(s):
        return str(s).replace("|", "／").replace("\n", " ")

    cells = [date_str, slot, scheduled, status, title, url, products]
    with POST_LOG.open("a", encoding="utf-8") as f:
        f.write("| " + " | ".join(clean(c) for c in cells) + " |\n")


def is_done(date_str, slot):
    return any(
        r["date"] == date_str and r["slot"] == str(slot) and r["status"] in DONE_STATUSES
        for r in read_post_log()
    )


def load_used_products():
    if not USED_PRODUCTS.exists():
        return {"items": []}
    return json.loads(USED_PRODUCTS.read_text(encoding="utf-8"))


def save_used_products(data):
    USED_PRODUCTS.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
