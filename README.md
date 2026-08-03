# AI HOT 每日速递

每天自动整理的 AI 圈精选动态，按 **年 / 月 / 日** 归档。数据来自 [aihot.virxact.com](https://aihot.virxact.com)。

## 版块

模型发布 / 产品发布 / 行业动态 / 论文研究 / 技巧与观点

## 目录结构

```
ai-hot-daily/
├── index.html                  # 首页：最新一期 + 按年/月/日归档
├── daily/
│   └── <年>/<月>/
│       ├── <YYYY-MM-DD>.html   # 当日网页版（卡片式）
│       └── <YYYY-MM-DD>.md     # 当日 Markdown 版（可贴飞书/Notion）
└── scripts/
    └── generate.py             # 生成器（零依赖，仅用 Python 标准库）
```

## 本地生成

```bash
# 拉取最近 3 天精选并生成（默认）
python3 scripts/generate.py

# 自定义回看天数
python3 scripts/generate.py --since-days 7
```

## 本地预览

```bash
# 在仓库根目录启动静态服务器
python3 -m http.server 8137
# 浏览器打开 http://localhost:8137/
```

## 部署到 GitHub Pages

将本仓库推送到 GitHub，在仓库 Settings → Pages 选择 `main` 分支（根目录）即可。
每日运行 `scripts/generate.py` 后提交，Pages 会自动更新。
