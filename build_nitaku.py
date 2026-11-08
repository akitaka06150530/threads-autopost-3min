"""
アプリ「30秒トレーニング」の問題データ（nitaku/app_data.json）から、
Threads用の【2択】投稿を作って schedule.csv の指定日以降を差し替えるスクリプト。

使い方:
    python build_nitaku.py --start 2026-11-15 --from-no 05
    python build_nitaku.py --start 2026-11-15 --from-no 05 --images   # 図解の画像も作り直す（要 playwright）

1作品あたりの流れ（1日1本・要約→図解の順、6日投稿→8日休み）:
    ※ 時刻は --post-hours（既定 17〜22時）を日ごとに使い、答えは12時間後。
      サイクルごとに1時間ずつずらして、時間帯ごとの反応を比べられるようにしている
    1日目 18:00  要約の2択を投稿 ＋ すぐ返信で「あらすじ」
    2日目 07:00  答え（理由つき）＋アプリへの誘導
    2日目 18:00  図解の2択（画像・コメントでA/B）を投稿 ＋ すぐ返信で「あらすじ」
    3日目 07:00  答え（理由つき）＋アプリへの誘導
"""
import argparse
import csv
import datetime as dt
import json
import os
import random

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "nitaku", "app_data.json")
SCHEDULE = os.path.join(HERE, "schedule.csv")
IMG_DIR = "nitaku/img"
APP_URL = "https://akitaka.biz/app/30sec/"
HEADERS = ["key", "cycle", "scheduled_at", "kind", "no", "title", "type",
           "reply_to", "text", "image", "enabled", "poll"]


def two_choices(item, typ):
    """正解＋1つ目の不正解で2択にし、A/Bの位置は作品ごとに固定のランダム"""
    ok = next(o for o in item["opts"] if o.get("ok"))
    ng = next(o for o in item["opts"] if not o.get("ok"))
    rnd = random.Random(f"{typ}-{item['no']}")
    return (ok, ng, "A") if rnd.random() < 0.5 else (ng, ok, "B")


def story_of(item):
    return item.get("story") or item.get("text") or ""


def youyaku_texts(item):
    a, b, ans = two_choices(item, "youyaku")
    ok, ng = (a, b) if ans == "A" else (b, a)
    no, title = item["no"], item["title"]
    post = (f"【30秒要約トレーニング #{no}】\n"
            f"『{title}』を20文字で要約。\n正しいのはどっち？\n\n"
            f"A：{a['t']}\nB：{b['t']}\n\n"
            f"👇タップで投票してね\n（あらすじはスレッドの返信に）")
    # 選択肢はThreads側の文字数の数え方が厳しいので「A」「B」だけにする
    poll = json.dumps({"option_a": "A", "option_b": "B"}, ensure_ascii=False)
    arasuji = f"📖 あらすじ\n{story_of(item)}"
    wrong = "B" if ans == "A" else "A"
    answer = (f"【答え】#{no}『{title}』\n正解は {ans}\n"
              f"{{POLL_RESULT:{ans}}}\n\n"
              f"「{ok['t']}」\n⭕ {ok['r']}\n\n"
              f"{wrong}「{ng['t']}」\n❌ {ng['r']}\n\n"
              f"▼3択版・ほかのお話もアプリで（無料・登録なし）\n{APP_URL}")
    return post, arasuji, answer, poll


def zukai_texts(item):
    a, b, ans = two_choices(item, "zukai")
    ok, ng = (a, b) if ans == "A" else (b, a)
    no, title = item["no"], item["title"]
    post = (f"【30秒図解トレーニング #{no}】\n"
            f"『{title}』を図にするなら、\nいちばん伝わるのはどっち？\n\n"
            f"画像のAとBを見くらべて、\nコメントで「A」か「B」を👇\n（あらすじはスレッドの返信に）")
    arasuji = f"📖 あらすじ\n{story_of(item)}"
    wrong = "B" if ans == "A" else "A"
    answer = (f"【答え】#{no}『{title}』\n正解は {ans}（{ok['type']}）\n"
              f"⭕ {ok['r']}\n\n"
              f"{wrong}（{ng['type']}）\n❌ {ng['r']}\n\n"
              f"▼3択版・ほかのお話もアプリで（無料・登録なし）\n{APP_URL}")
    return post, arasuji, answer, (a, b)


def render_images(pairs):
    """図解の2択画像（A/Bを縦に並べたPNG）を作る"""
    from playwright.sync_api import sync_playwright
    os.makedirs(os.path.join(HERE, IMG_DIR), exist_ok=True)
    font = "'Noto Sans CJK JP','Noto Sans JP',sans-serif"
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1080, "height": 1080}, device_scale_factor=1)
        for item, (a, bb) in pairs:
            html = f"""<html><body style="margin:0;background:#FAF6F0;font-family:{font};color:#1F2A36">
<div id="c" style="width:1080px;padding:40px 48px;box-sizing:border-box">
 <div style="font-size:30px;font-weight:700;color:#E8603C">30秒図解トレーニング #{item['no']}</div>
 <div style="font-size:44px;font-weight:800;margin:6px 0 2px">『{item['title']}』</div>
 <div style="font-size:34px;font-weight:700;margin:0 0 26px">いちばん伝わる図は、AとBのどっち？</div>
 {''.join(f'''<div style="display:flex;align-items:center;gap:20px;background:#fff;border:3px solid #1F2A36;border-radius:20px;padding:18px 22px;margin-bottom:24px">
   <div style="flex:none;width:84px;height:84px;border-radius:50%;background:#1F2A36;color:#fff;font-size:52px;font-weight:800;display:flex;align-items:center;justify-content:center">{lab}</div>
   <div style="flex:1">{o['svg'].replace('<svg ', '<svg style="width:100%;height:auto;display:block" ', 1)}</div></div>'''
              for lab, o in (("A", a), ("B", bb)))}
 <div style="text-align:right;font-size:26px;color:#6B7480">ノバスケ｜akitaka.biz/app/30sec</div>
</div></body></html>"""
            pg.set_content(html)
            pg.wait_for_timeout(150)
            pg.locator("#c").screenshot(path=os.path.join(HERE, IMG_DIR, f"zukai_{item['no']}.png"))
        b.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", required=True, help="最初の要約2択を投稿する日 YYYY-MM-DD")
    ap.add_argument("--from-no", required=True, help="アプリの何番から始めるか（例 05）")
    ap.add_argument("--first-cycle", type=int, default=2)
    ap.add_argument("--on-days", type=int, default=6)
    ap.add_argument("--off-days", type=int, default=8)
    ap.add_argument("--post-hours", default="17,18,19,20,21,22",
                    help="1サイクル内の投稿時刻（日ごと）。答えは12時間後")
    ap.add_argument("--no-rotate", action="store_true",
                    help="サイクルごとに時刻をずらさない（既定はずらす）")
    ap.add_argument("--images", action="store_true")
    a = ap.parse_args()

    data = json.load(open(DATA, encoding="utf-8"))
    nos = [x["no"] for x in data["youyaku"]]
    start_i = nos.index(a.from_no)
    yk = {x["no"]: x for x in data["youyaku"]}
    zk = {x["no"]: x for x in data["zukai"]}

    with open(SCHEDULE, encoding="utf-8-sig", newline="") as f:
        old = list(csv.DictReader(f))
    start_dt = f"{a.start} 00:00"
    kept = [r for r in old if r["scheduled_at"] < start_dt]
    for r in kept:
        r.setdefault("poll", "")

    hours = [int(h) for h in a.post_hours.split(",")]
    rows, pairs = [], []
    day, cycle, n = dt.date.fromisoformat(a.start), a.first_cycle, 0
    for no in nos[start_i:]:
        for typ, label in (("youyaku", "要約"), ("zukai", "図解")):
            if n == a.on_days:
                day += dt.timedelta(days=a.off_days)
                cycle, n = cycle + 1, 0
            n += 1
            item = yk[no] if typ == "youyaku" else zk[no]
            if typ == "youyaku":
                post, arasuji, answer, poll = youyaku_texts(item)
                img = ""
            else:
                post, arasuji, answer, ab = zukai_texts(item)
                poll = ""
                img = f"{IMG_DIR}/zukai_{no}.png"
                pairs.append((item, ab))
            base = f"n_{typ}_{no}"
            # サイクルごとに1つずつずらす → どの時刻も要約・図解・いろいろな曜日に当たる
            shift = 0 if a.no_rotate else (cycle - a.first_cycle)
            h = hours[(n - 1 + shift) % len(hours)]
            p_dt = dt.datetime.combine(day, dt.time(h))
            p_at = p_dt.strftime("%Y-%m-%d %H:%M")
            r_at = (p_dt + dt.timedelta(hours=12)).strftime("%Y-%m-%d %H:%M")
            common = {"cycle": cycle, "no": no, "title": item["title"], "type": label + "2択", "enabled": "TRUE"}
            rows += [
                {**common, "key": f"{base}_post", "scheduled_at": p_at, "kind": "post",
                 "reply_to": "", "text": post, "image": img, "poll": poll},
                {**common, "key": f"{base}_arasuji", "scheduled_at": p_at, "kind": "reply",
                 "reply_to": f"{base}_post", "text": arasuji, "image": ""},
                {**common, "key": f"{base}_answer", "scheduled_at": r_at, "kind": "reply",
                 "reply_to": f"{base}_post", "text": answer, "image": ""},
            ]
            day += dt.timedelta(days=1)

    for r in rows:
        r.setdefault("poll", "")
        if r["poll"] and any(not 1 <= len(v) <= 25 for v in json.loads(r["poll"]).values()):
            raise SystemExit(f"アンケートの選択肢が25文字を超えています: {r['key']}")
    too_long = [r["key"] for r in rows if len(r["text"]) > 500]
    if too_long:
        raise SystemExit(f"500文字を超えた投稿があります: {too_long}")

    with open(SCHEDULE, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=HEADERS)
        w.writeheader()
        w.writerows(kept + rows)
    if a.images:
        render_images(pairs)
    print(f"残した行 {len(kept)} ／ 2択の行 {len(rows)}（{rows[0]['scheduled_at']} 〜 {rows[-1]['scheduled_at']}）")


if __name__ == "__main__":
    main()
