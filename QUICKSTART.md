# ⚡ 5 分鐘快速部署

## Step 1：本機生成 Session（2 分鐘）

```bash
pip install telethon
python init_session.py
```

輸入：API ID → API Hash → 手機號 → 驗證碼  
完成後會產生 `bot_session.session` 並顯示群組 ID 清單。

---

## Step 2：上傳 GitHub（1 分鐘）

1. GitHub → **New repository** → `crypto-trading-bot` → **Private** → Create
2. 上傳所有檔案（含 `bot_session.session`）
3. Commit changes

---

## Step 3：部署 Zeabur（2 分鐘）

1. https://zeabur.com → New Project → Deploy from GitHub
2. 選擇 `crypto-trading-bot`
3. Variables → 貼入以下 12 個環境變數：

```
TELEGRAM_API_ID=
TELEGRAM_API_HASH=
TELEGRAM_PHONE=
TELEGRAM_CHANNEL_ID=
BINANCE_API_KEY=
BINANCE_API_SECRET=
BINANCE_TESTNET=true
MAX_POSITION_USDT=100
MAX_DAILY_LOSS=500
MAX_LEVERAGE=20
POSITION_PCT=0.02
ALERT_CHAT_ID=
```

4. Redeploy → 完成 ✅

---

## ✅ 確認運行正常

Zeabur Logs 出現以下訊息代表成功：
```
🤖 Bot 啟動成功，監聽中...
```

Telegram 會收到：
```
🤖 交易 Bot 已啟動，正在監聽信號...
```
