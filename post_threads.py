"""
schedule.csv を見て、時刻が来た投稿・返信を Threads に出すスクリプト。
GitHub Actions から 1日数回呼ばれる想定（手元PCからも実行可）。

  - enabled が TRUE の行だけ対象（Excelで FALSE にすると止められる）
  - 投稿済みは state.json に記録し、二重投稿しない
  - 1回の実行で出すのは「投稿1本＋返信2本」まで（止まっていた分は次の実行で順に追いつく）
  - 返信は、返信先の投稿が済んでいないと出さない

環境変数:
  THREADS_ACCESS_TOKEN  … 長期アクセストークン（必須）
  IMAGE_BASE_URL        … 画像の公開URLの先頭（未指定なら GitHub の raw URL を自動で組み立て）
  DRY_RUN=1             … 実際には投稿せず、何を出すかだけ表示
  NOW="2026-11-02 07:10" … テスト用に現在時刻を上書き（JST）

深夜に出ないよう、出してよい時間帯（JST）を決めている:
  問題の投稿 … 17時〜22時台   返信 … 5時〜22時台
  （遅れて時間外になった分は、次の時間帯に順番に出る）
"""
import csv
import datetime as dt
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

API = "https://graph.threads.net/v1.0"
JST = dt.timezone(dt.timedelta(hours=9))
HERE = os.path.dirname(os.path.abspath(__file__))
SCHEDULE = os.path.join(HERE, "schedule.csv")
STATE = os.path.join(HERE, "state.json")


ALLOWED_HOURS = {"post": range(17, 23), "reply": range(5, 23)}


def log(*a):
    print(*a, flush=True)


def api(method, path, params):
    url = f"{API}/{path}"
    data = urllib.parse.urlencode(params).encode()
    if method == "GET":
        req = urllib.request.Request(f"{url}?{data.decode()}")
    else:
        req = urllib.request.Request(url, data=data, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        raise RuntimeError(f"Threads API エラー {e.code}: {body}") from None


def poll_result_line(token, post_id, correct):
    """アンケートの結果から「正解した人：68％（25票）」を作る。取れなければ空文字"""
    try:
        pa = api("GET", post_id, {"access_token": token, "fields":
                 "poll_attachment{option_a_votes_percentage,option_b_votes_percentage,total_votes}"}
                 ).get("poll_attachment") or {}
        total = int(pa.get("total_votes") or 0)
        pct = pa.get(f"option_{correct.lower()}_votes_percentage")
        if not total or pct is None:
            return ""
        pct = float(pct)
        pct = pct * 100 if pct <= 1 else pct
        return f"📊 正解した人：{round(pct)}％（{total}票）"
    except Exception as e:  # 結果が取れなくても答えは出す
        log(f"   投票結果を取得できませんでした: {e}")
        return ""


def fill_placeholders(token, text, parent_id):
    m = re.search(r"\{POLL_RESULT:([AB])\}", text)
    if not m:
        return text
    line = poll_result_line(token, parent_id, m.group(1)) if token and parent_id else ""
    text = text.replace(m.group(0), line)
    return re.sub(r"\n{3,}", "\n\n", text)


def publish(token, text, image_url=None, reply_to_id=None, poll=None):
    params = {"access_token": token, "text": text}
    if poll:
        params["poll_attachment"] = poll
    if image_url:
        params.update(media_type="IMAGE", image_url=image_url)
    else:
        params["media_type"] = "TEXT"
    if reply_to_id:
        params["reply_to_id"] = reply_to_id
    container = api("POST", "me/threads", params)["id"]

    # 画像の取り込みが終わるまで待つ（テキストでも少し待つのが推奨）
    for _ in range(30):
        time.sleep(5 if image_url else 2)
        st = api("GET", container, {"access_token": token, "fields": "status,error_message"})
        if st.get("status") == "FINISHED":
            break
        if st.get("status") in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"コンテナ作成に失敗: {st}")
    else:
        raise RuntimeError("コンテナの準備がタイムアウトしました")

    return api("POST", "me/threads_publish", {"access_token": token, "creation_id": container})["id"]


def image_base_url():
    if os.environ.get("IMAGE_BASE_URL"):
        return os.environ["IMAGE_BASE_URL"].rstrip("/")
    repo = os.environ.get("GITHUB_REPOSITORY")
    branch = os.environ.get("GITHUB_REF_NAME", "main")
    if not repo:
        sys.exit("IMAGE_BASE_URL か GITHUB_REPOSITORY を設定してください")
    return f"https://raw.githubusercontent.com/{repo}/{branch}"


def load_state():
    if os.path.exists(STATE):
        with open(STATE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_state(state):
    with open(STATE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def main():
    dry = os.environ.get("DRY_RUN") == "1"
    token = os.environ.get("THREADS_ACCESS_TOKEN")
    if not token and not dry:
        sys.exit("THREADS_ACCESS_TOKEN が設定されていません")

    now = (dt.datetime.strptime(os.environ["NOW"], "%Y-%m-%d %H:%M").replace(tzinfo=JST)
           if os.environ.get("NOW") else dt.datetime.now(JST))
    log(f"現在時刻(JST): {now:%Y-%m-%d %H:%M}  {'[DRY RUN]' if dry else ''}")

    with open(SCHEDULE, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    state = load_state()
    base = image_base_url() if any(r["image"] for r in rows) else ""

    MAX_PER_RUN = {"post": 1, "reply": 2}  # 投稿1本＋返信2本（あらすじ＋遅れた答え）まで
    done_count = {"post": 0, "reply": 0}
    for r in rows:
        key = r["key"]
        if key in state or r["enabled"].strip().upper() not in ("TRUE", "1", "YES", "OK"):
            continue
        when = dt.datetime.strptime(r["scheduled_at"], "%Y-%m-%d %H:%M").replace(tzinfo=JST)
        if when > now or done_count[r["kind"]] >= MAX_PER_RUN[r["kind"]]:
            continue
        if now.hour not in ALLOWED_HOURS.get(r["kind"], range(24)):
            log(f"時間外のため見送り: {key}（{r['kind']}は{ALLOWED_HOURS[r['kind']].start}〜{ALLOWED_HOURS[r['kind']].stop - 1}時台のみ）")
            done_count[r["kind"]] = MAX_PER_RUN[r["kind"]]
            continue

        reply_to_id = None
        if r["kind"] == "reply":
            parent = state.get(r["reply_to"])
            if not parent:
                log(f"保留: {key}（返信先 {r['reply_to']} がまだ投稿されていません）")
                continue
            reply_to_id = parent["id"]

        image_url = f"{base}/{urllib.parse.quote(r['image'])}" if r["image"] else None
        poll = (r.get("poll") or "").strip() or None
        text = fill_placeholders(token if not dry else None, r["text"], reply_to_id)
        log(f"→ {key}  予定 {r['scheduled_at']}  画像: {image_url or 'なし'}  アンケート: {poll or 'なし'}")
        log("   " + text.replace("\n", "\n   "))

        if dry:
            state[key] = {"id": f"DRY-{key}", "posted_at": now.isoformat()}
        else:
            post_id = publish(token, text, image_url, reply_to_id, poll)
            state[key] = {"id": post_id, "posted_at": now.isoformat()}
            save_state(state)  # 1件ごとに保存（途中で失敗しても二重投稿しない）
            log(f"   投稿完了 id={post_id}")
        done_count[r["kind"]] += 1

    if not any(done_count.values()):
        log("今回出すものはありませんでした")
    if dry:
        log("（DRY RUN のため state.json は更新していません）")


if __name__ == "__main__":
    main()
