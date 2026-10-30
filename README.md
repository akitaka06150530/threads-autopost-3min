# Threads 自動投稿（3分要約・図解トレーニング）

`schedule.csv` に並べた投稿を、決まった時刻に GitHub Actions が Threads へ出します。PCの電源は切っていてOK・すべて無料です。

## 投稿の流れ（初期設定：6日投稿 → 8日休み）

| 日 | 07:00 | 18:00 |
|---|---|---|
| 11/1 | — | #02 要約 を投稿 |
| 11/2 | #02 要約 に `youyaku_02.png` で返信 | #02 図解 を投稿 |
| … | … | … |
| 11/6 | … | #04 図解 を投稿（サイクル1の最後） |
| 11/7 | #04 図解 に返信 | **休み（〜11/14）＝振り返り週** |
| 11/15 | — | #05 要約 を投稿（サイクル2開始） |

- 1サイクル＝3作品（要約・図解のペアが途中で分かれない）
- 2週間で1サイクル。毎回**日曜スタート・金曜終わり**
- `cycle` 列でサイクル番号がわかります
- 実際の実行は 18:05 / 07:05 ごろ（GitHubの混雑で遅れることがあり、30分後にもう一度確認が走ります）

## 休みの週にやること（振り返り → 修正）

1. **反応を見る**：日曜の朝に自動で `report.csv` が更新されます（Actions →「振り返りレポート」→ Run workflow で手動も可）
   - サイクル×要約/図解ごとの平均（表示・いいね・返信…）がログに出ます
2. **次のサイクルを直す**：`schedule.csv` の次サイクルの行だけ書き換えてアップロード
   - 文章を変える（例：3択形式にする）→ `text` 列
   - 時刻を変える → `scheduled_at` 列
   - 一部をやめる → `enabled` を `FALSE`
   - 投稿済みの行は `state.json` に記録があるので、触っても二度と出ません
3. **リズム自体を変える**（例：5日投稿・9日休み）：
   ```
   python build_schedule.py "..\3分要約・図解トレーニング Threads投稿100本.docx" --start 2026-11-15 --from-no 5 --first-cycle 2 --on-days 6 --off-days 8
   ```
   ※ `--from-no` から作り直すので、途中の作品の要約だけ済んでいる場合は、その図解の行を手で残してください

## フォルダの中身

| ファイル | 役割 |
|---|---|
| `schedule.csv` | 予定表。Excelで開いて編集できます |
| `post_threads.py` | 投稿スクリプト |
| `state.json` | 投稿済みの記録（自動更新。手で触らない） |
| `build_schedule.py` | docx から予定表を作り直すとき用 |
| `report.py` | 振り返り用に反応を集計して `report.csv` に出す |
| `github-workflows/` | 自動実行の設定（GitHub上で `.github/workflows/` に置く。②-4参照） |

### schedule.csv の使い方
- **enabled** を `FALSE` にすると、その行は出ません（一時停止に便利）
- **scheduled_at** を書き換えれば日時を変えられます（形式：`2026-11-01 18:00`）
- **text** で投稿文・返信文を直せます
- 保存は「CSV UTF-8」形式で

開始日をまとめてずらしたいとき：
```
pip install python-docx
python build_schedule.py "..\3分要約・図解トレーニング Threads投稿100本.docx" --start 2026-11-08
```

---

## 初回セットアップ（1回だけ・30〜40分）

### ① Meta（Threads API）の準備
1. https://developers.facebook.com/ にログイン →「アプリを作成」
2. ユースケースで **「Threads APIにアクセス」** を選ぶ
3. ユースケースの「カスタマイズ」→ 権限に次の3つがあることを確認
   - `threads_basic`
   - `threads_content_publish`
   - `threads_manage_replies`（返信に必要）
   - `threads_manage_insights`（振り返りレポートに必要）
4. **アプリの役割 → 役割 → 「Threadsテスター」** に自分のThreadsアカウントを追加
5. Threadsアプリ（またはWeb）の **設定 → アカウント → ウェブサイトのアクセス許可 → 招待** で承認
6. ユースケースの設定画面にある **User Token Generator** で、自分のアカウントのアクセストークンを発行してコピー
   - ※ 短期トークン（1時間）しか出ない場合は、次のURLをブラウザで開くと60日の長期トークンに変換できます
     `https://graph.threads.net/access_token?grant_type=th_exchange_token&client_secret=【アプリシークレット】&access_token=【短期トークン】`

> アプリは「開発モード」のままでOKです（自分のアカウントに投稿するだけなら審査は不要）。

### ② GitHub の準備
1. GitHubで新しいリポジトリを作成（例：`threads-autopost`）
   - **Public** にしてください。Threadsが画像を取りに来るため、画像が公開URLである必要があります
   - ※ 画像は投稿前でもURLを知っていれば見られる状態になります（作品の解答例なので実害は小さい想定）
2. このフォルダの中身を全部アップロード
3. さらに、`youyaku_kaitourei` と `zukai_kaitourei` の **2フォルダをこのフォルダにコピー** してからアップロード
   （最終的にリポジトリ直下が `youyaku_kaitourei/youyaku_02.png` という並びになればOK）
   - Webのドラッグ＆ドロップは1回100ファイルまでなので、2回に分けるか GitHub Desktop を使うと楽です
4. 自動実行の設定ファイルを置く（`github-workflows` フォルダの2ファイル）
   - リポジトリ画面で **Add file → Create new file**
   - ファイル名欄に `.github/workflows/post.yml` と入力（`/` を打つとフォルダになります）
   - `github-workflows/post.yml` の中身を貼り付けて Commit
   - `refresh-token.yml`・`report.yml` も同じように `.github/workflows/` の下に作成
5. リポジトリの **Settings → Secrets and variables → Actions → New repository secret**
   - `THREADS_ACCESS_TOKEN` … ①-6 のトークン

### ③ トークンの自動延長（おすすめ）
トークンは60日で切れるので、毎週自動で延長する設定です。
1. GitHub右上アイコン → Settings → Developer settings → **Fine-grained tokens** → Generate new token
   - Repository access：このリポジトリだけ
   - Permissions：**Secrets = Read and write**
   - 有効期限：最長（期限が来たら作り直し）
2. できたトークンを、②-5 と同じ場所に `GH_PAT` という名前で登録

設定しない場合は、50日おきに①-6 をやり直して `THREADS_ACCESS_TOKEN` を上書きしてください。

### ④ 動作テスト
1. リポジトリの **Actions → Threads 自動投稿 → Run workflow**
2. 「DRY RUN」にチェックが入ったまま実行 → ログに「今回出すものはありませんでした」などが出ればOK
3. 本番テストしたいときは、`schedule.csv` の先頭行の日時を少し前にして、チェックを外して実行
   （投稿されたら、state.json に記録されます）
4. Actions → Threads トークン更新 → Run workflow で、③が動くかも確認

---

## 困ったとき
- **止めたい**：Actions → Threads 自動投稿 → 右上「…」→ Disable workflow
- **失敗した**：Actions のログに Threads API のエラー文が出ます。トークン切れ（code 190）が多いです
- **投稿が遅れて溜まった**：1回の実行で出すのは「投稿1本＋返信1本」まで。次の実行から順番に追いつきます
- **GitHubの注意**：60日間リポジトリに更新がないと定期実行が止まることがありますが、このしくみは毎回 state.json を更新するので通常は問題ありません
