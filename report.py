"""
振り返り用レポート：投稿済みの各投稿の反応を集めて書き出す。
  report.csv          … 1投稿1行（表示・いいね・他の人の返信・投票数・反応合計など）
  report_by_hour.csv  … 投稿した時刻（17〜22時）ごとの平均。どの時間帯が一番反応があるかを見る用

「反応合計」= いいね + 他の人の返信 + リポスト + 引用 + 投票数
「反応率」  = 反応合計 ÷ 表示回数
※ 返信数からは、自分の「あらすじ」「答え」の返信を引いています。

必要な権限: threads_manage_insights（Metaのアプリ設定で追加）
環境変数: THREADS_ACCESS_TOKEN
"""
import csv
import datetime as dt
import os
import sys
from collections import defaultdict

from post_threads import SCHEDULE, HERE, api, load_state

METRICS = ["views", "likes", "replies", "reposts", "quotes", "shares"]
OUT = os.path.join(HERE, "report.csv")
OUT_HOUR = os.path.join(HERE, "report_by_hour.csv")
WEEK = "月火水木金土日"


def votes_of(token, post_id):
    try:
        pa = api("GET", post_id, {"access_token": token,
                 "fields": "poll_attachment{total_votes}"}).get("poll_attachment") or {}
        return int(pa.get("total_votes") or 0)
    except Exception:
        return 0


def main():
    token = os.environ.get("THREADS_ACCESS_TOKEN") or sys.exit("THREADS_ACCESS_TOKEN が必要です")
    state = load_state()
    with open(SCHEDULE, encoding="utf-8-sig", newline="") as f:
        all_rows = list(csv.DictReader(f))
    own_replies = defaultdict(int)  # 自分がつけた返信の数（あらすじ・答え）
    for r in all_rows:
        if r["kind"] == "reply" and r["key"] in state:
            own_replies[r["reply_to"]] += 1
    rows = [r for r in all_rows if r["kind"] == "post" and r["key"] in state]

    out = []
    for r in rows:
        pid = state[r["key"]]["id"]
        res = api("GET", f"{pid}/insights", {"access_token": token, "metric": ",".join(METRICS)})
        v = {m["name"]: m["values"][0]["value"] for m in res.get("data", []) if m.get("values")}
        v = {m: int(v.get(m, 0)) for m in METRICS}
        others = max(0, v["replies"] - own_replies[r["key"]])
        votes = votes_of(token, pid) if r.get("poll") else 0
        posted = dt.datetime.fromisoformat(state[r["key"]]["posted_at"])
        total = v["likes"] + others + v["reposts"] + v["quotes"] + votes
        out.append({
            "cycle": r.get("cycle", ""), "posted_at": posted.strftime("%Y-%m-%d %H:%M"),
            "hour": posted.hour, "weekday": WEEK[posted.weekday()],
            "no": r["no"], "title": r["title"], "type": r["type"],
            "views": v["views"], "likes": v["likes"], "replies_others": others,
            "reposts": v["reposts"], "quotes": v["quotes"], "shares": v["shares"], "votes": votes,
            "engagement": total, "rate_%": round(total / v["views"] * 100, 1) if v["views"] else 0,
        })

    with open(OUT, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys()) if out else ["none"])
        w.writeheader()
        w.writerows(out)

    # 時間帯ごと（2択の投稿だけで比べる）
    two = [o for o in out if "2択" in o["type"]]
    by_hour = defaultdict(list)
    for o in two:
        by_hour[o["hour"]].append(o)
    cols = ["views", "likes", "replies_others", "votes", "engagement"]
    hour_rows = []
    for h in sorted(by_hour):
        xs = by_hour[h]
        row = {"hour": f"{h}時", "posts": len(xs),
               **{f"avg_{c}": round(sum(x[c] for x in xs) / len(xs), 1) for c in cols}}
        views = sum(x["views"] for x in xs)
        row["rate_%"] = round(sum(x["engagement"] for x in xs) / views * 100, 1) if views else 0
        for t in ("要約2択", "図解2択"):
            ys = [x for x in xs if x["type"] == t]
            row[f"{t}_avg_engagement"] = round(sum(y["engagement"] for y in ys) / len(ys), 1) if ys else ""
        hour_rows.append(row)
    if hour_rows:
        with open(OUT_HOUR, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(hour_rows[0].keys()))
            w.writeheader()
            w.writerows(hour_rows)

    print("■ 時間帯ごとの平均（2択の投稿）")
    print(f"{'時刻':<5}{'本数':>4}{'表示':>8}{'いいね':>7}{'返信':>6}{'投票':>6}{'反応計':>7}{'反応率%':>8}")
    for r in hour_rows:
        print(f"{r['hour']:<6}{r['posts']:>4}{r['avg_views']:>9}{r['avg_likes']:>7}"
              f"{r['avg_replies_others']:>7}{r['avg_votes']:>7}{r['avg_engagement']:>8}{r['rate_%']:>8}")
    if hour_rows:
        best = max(hour_rows, key=lambda r: r["avg_engagement"])
        print(f"\n→ いまのところ反応が一番多いのは {best['hour']}（平均 {best['avg_engagement']}）")
        if min(r["posts"] for r in hour_rows) < 4:
            print("  ※ まだ各時刻の本数が少ないので、参考程度に。3サイクル以上たまると傾向が見えてきます")
    print(f"\n{len(out)} 件を report.csv、時間帯別を report_by_hour.csv に保存しました")


if __name__ == "__main__":
    main()
