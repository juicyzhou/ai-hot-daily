# AI HOT 每日速递 · 自动化执行记录

## 固定流程（已验证可用）
1. 校验 API：`https://aihot.virxact.com/api/public/items?mode=selected&since=<ISO>&take=N`，需带 Chrome UA，否则可能被拦。
2. 生成：`/Users/zhou/.workbuddy/binaries/python/versions/3.13.12/bin/python3 scripts/generate.py`（默认 --since-days 31，内部自带抓取，无需先手动 curl 落盘）。
3. 推送：`git add -A && git commit && git push origin main`（gh auth setup-git 已配好，免交互）。
4. Pages 固定站点：https://juicyzhou.github.io/ai-hot-daily/ ，push 后约 1 分钟内生效。
5. 飞书：`lark-cli im +messages-send --as user --user-id ou_3fe6b2e2fd8b831ec34a97080a760580 --idempotency-key aihot-YYYYMMDD --markdown "..."`

## 关键经验
- 摘要中的 N 取「本次抓取总条数」（生成器输出 `[info] 拉到 N 条`），不是当日条数；当日条数可从 manifest.json 的 `daily.<日期>.count` 读。
- lark-cli user token 显示 `needs_refresh` 属正常，调用时会自动刷新；scope 已含 im:message.send_as_user。
- manifest.json 为跨运行累计归档，勿删。

## 运行日志
### 2026-08-03（首次运行，全流程成功）
- 抓取 94 条（近 31 天），当日 2026-08-03 有 3 条。
- 归档累计：日报 8 期 / 周报 2 期 / 月报 2 期。
- commit 7ef961e 已推送，Pages 首页与当日页均返回 200。
- 飞书私聊发送成功，message_id om_x100b683caf297ca4b048f5d6ca38c30。
