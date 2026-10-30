"""
docx（投稿100本）から schedule.csv を作り直すスクリプト。

使い方:
    python build_schedule.py "3分要約・図解トレーニング Threads投稿100本.docx" --start 2026-11-01 --from-no 2 --on-days 6 --off-days 8

ルール（1日1本ずつ交互。--on-days 日投稿したら --off-days 日休む）:
    1日目 18:00  #N 要約 を投稿
    2日目 07:00  ↑ に youyaku_NN.png で返信
    2日目 18:00  #N 図解 を投稿
    3日目 07:00  ↑ に zukai_NN.png で返信
    3日目 18:00  #N+1 要約 を投稿 …
"""
import argparse
import csv
import datetime as dt
import re

import docx  # pip install python-docx

HEADERS = ["key", "cycle", "scheduled_at", "kind", "no", "title", "type",
           "reply_to", "text", "image", "enabled"]


def parse_docx(path):
    d = docx.Document(path)
    works = {}
    cur = None
    for p in d.paragraphs:
        t = p.text.strip()
        m = re.match(r"^(\d{2})\s+(.+)$", t)
        if p.style.name.startswith("Heading 3") and m:
            cur = {"no": int(m.group(1)), "title": m.group(2)}
            works[cur["no"]] = cur
        elif cur is None:
            continue
        elif p.style.name == "Code" and "要約トレーニング" in t:
            cur["youyaku_post"] = p.text.strip()
        elif p.style.name == "Code" and "図解トレーニング" in t:
            cur["zukai_post"] = p.text.strip()
        elif t.startswith("要約の解答例"):
            cur["youyaku_ans"] = t.split("：", 1)[1].strip()
            cur["youyaku_len"] = re.search(r"（(\d+)文字）", t).group(1)
        elif t.startswith("図解の解答例"):
            cur["zukai_ans"] = t.split("：", 1)[1].strip()
    return works


def build_rows(works, start, from_no, post_time, reply_time, on_days=0, off_days=0, first_cycle=1):
    rows = []
    day = start
    cycle, posted_in_cycle = first_cycle, 0
    for no in sorted(n for n in works if n >= from_no):
        w = works[no]
        for typ, label in (("youyaku", "要約"), ("zukai", "図解")):
            if on_days and posted_in_cycle == on_days:  # 休みに入る
                day += dt.timedelta(days=off_days)
                cycle, posted_in_cycle = cycle + 1, 0
            posted_in_cycle += 1
            post_key = f"{typ}_{no:02d}_post"
            post_at = dt.datetime.combine(day, post_time)
            reply_at = dt.datetime.combine(day + dt.timedelta(days=1), reply_time)
            rows.append({
                "key": post_key, "cycle": cycle, "scheduled_at": post_at.strftime("%Y-%m-%d %H:%M"),
                "kind": "post", "no": f"{no:02d}", "title": w["title"], "type": label,
                "reply_to": "", "text": w[f"{typ}_post"], "image": "", "enabled": "TRUE",
            })
            if typ == "youyaku":
                reply_text = (f"【解答例】#{no:02d}『{w['title']}』\n"
                              f"{w['youyaku_ans']}（{w['youyaku_len']}文字）")
            else:
                reply_text = f"【解答例】#{no:02d}『{w['title']}』\n{w['zukai_ans']}"
            rows.append({
                "key": f"{typ}_{no:02d}_reply", "cycle": cycle, "scheduled_at": reply_at.strftime("%Y-%m-%d %H:%M"),
                "kind": "reply", "no": f"{no:02d}", "title": w["title"], "type": label,
                "reply_to": post_key, "text": reply_text,
                "image": f"{typ}_kaitourei/{typ}_{no:02d}.png", "enabled": "TRUE",
            })
            day += dt.timedelta(days=1)
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("docx")
    ap.add_argument("--start", required=True, help="最初の要約を投稿する日 YYYY-MM-DD")
    ap.add_argument("--from-no", type=int, default=2)
    ap.add_argument("--post-time", default="18:00")
    ap.add_argument("--reply-time", default="07:00")
    ap.add_argument("--on-days", type=int, default=6, help="続けて投稿する日数（0で休みなし）")
    ap.add_argument("--off-days", type=int, default=8, help="休む日数")
    ap.add_argument("--first-cycle", type=int, default=1, help="最初のサイクル番号")
    ap.add_argument("--out", default="schedule.csv")
    a = ap.parse_args()

    works = parse_docx(a.docx)
    rows = build_rows(
        works, dt.date.fromisoformat(a.start), a.from_no,
        dt.time.fromisoformat(a.post_time), dt.time.fromisoformat(a.reply_time),
        a.on_days, a.off_days, a.first_cycle)
    # Excelで文字化けしないよう BOM付きUTF-8
    with open(a.out, "w", encoding="utf-8-sig", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=HEADERS)
        wr.writeheader()
        wr.writerows(rows)
    print(f"{len(rows)} 行を {a.out} に書き出しました（{rows[0]['scheduled_at']} 〜 {rows[-1]['scheduled_at']}）")


if __name__ == "__main__":
    main()
