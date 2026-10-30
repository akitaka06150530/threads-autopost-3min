"""
振り返り用レポート：投稿済みの各投稿の反応（表示・いいね・返信など）を集めて report.csv に書き出す。
休みの週に実行して、サイクルごと・要約/図解ごとの反応を比べる用。

必要な権限: threads_manage_insights（Metaのアプリ設定で追加）
環境変数: THREADS_ACCESS_TOKEN
"""
import csv
import json
import os
import sys
from collections import defaultdict

from post_threads import SCHEDULE, STATE, HERE, api, load_state

METRICS = ["views", "likes", "replies", "reposts", "quotes", "shares"]
OUT = os.path.join(HERE, "report.csv")


def main():
    token = os.environ.get("THREADS_ACCESS_TOKEN") or sys.exit("THREADS_ACCESS_TOKEN が必要です")
    state = load_state()
    with open(SCHEDULE, encoding="utf-8-sig", newline="") as f:
        rows = [r for r in csv.DictReader(f) if r["kind"] == "post" and r["key"] in state]

    out = []
    for r in rows:
        res = api("GET", f"{state[r['key']]['id']}/insights",
                  {"access_token": token, "metric": ",".join(METRICS)})
        vals = {m["name"]: m["values"][0]["value"] for m in res.get("data", []) if m.get("values")}
        out.append({"cycle": r.get("cycle", ""), "scheduled_at": r["scheduled_at"], "no": r["no"],
                    "title": r["title"], "type": r["type"], **{m: vals.get(m, 0) for m in METRICS},
                    "first_line": r["text"].splitlines()[0]})

    with open(OUT, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["cycle", "scheduled_at", "no", "title", "type", *METRICS, "first_line"])
        w.writeheader()
        w.writerows(out)

    # サイクル × 種類 ごとの平均をログに出す
    agg = defaultdict(list)
    for o in out:
        agg[(o["cycle"], o["type"])].append(o)
    print(f"{'サイクル':<6}{'種類':<4}{'本数':>4}" + "".join(f"{m:>9}" for m in METRICS))
    for (c, t), xs in sorted(agg.items()):
        avg = {m: sum(x[m] for x in xs) / len(xs) for m in METRICS}
        print(f"{c:<8}{t:<4}{len(xs):>5}" + "".join(f"{avg[m]:>9.1f}" for m in METRICS))
    print(f"\n{len(out)} 件を report.csv に保存しました")


if __name__ == "__main__":
    main()
