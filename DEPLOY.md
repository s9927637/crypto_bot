# 部署指南 — Telegram 加密貨幣自動交易 Bot

## 📁 檔案結構

```
crypto_bot/
├── crypto_bot.py       ← 主程式（已完整）
├── init_session.py     ← 初始化登入（只跑一次）
├── requirements.txt    ← 依賴套件
├── .env.example        ← 環境變數範本
└── DEPLOY.md           ← 本文件
```

---

## 🔑 Step 1：取得 Telegram API

1. 前往 https://my.telegram.org
2. 登入 → `API development tools`
3. 填寫 App name（隨意）
4. 記下 `api_id` 和 `api_hash`

---

## 🔑 Step 2：幣安 API Key

1. 幣安 → 帳戶 → API 管理
2. 建立 API
3. 權限：只勾 **期貨交易**，不要勾提現
4. 建議限制 IP（可選）

---

## 📱 Step 3：生成 Telegram Session（本機執行一次）

```bash
pip install telethon
python init_session.py
```

依照提示輸入：
- API ID / Hash
- 手機號
- 驗證碼（Telegram 發給你）

執行完會：
1. 產生 `bot_session.session`
2. 列出你的群組 ID → 找到 VIP 群組的 ID

---

## ☁️ Step 4：部署到 Zeabur

### 4.1 上傳 GitHub
1. GitHub → New Repository → `crypto-trading-bot` (設為 **Private**)
2. 上傳所有檔案，包含 `bot_session.session`

### 4.2 Zeabur 部署
1. https://zeabur.com → New Project → Deploy from GitHub
2. 選擇 `crypto-trading-bot`
3. Runtime 會自動偵測為 Python

### 4.3 設置環境變數
在 Zeabur Variables 貼入（參考 `.env.example`）：

| 變數 | 說明 |
|------|------|
| TELEGRAM_API_ID | Telegram App ID |
| TELEGRAM_API_HASH | Telegram Hash |
| TELEGRAM_PHONE | 你的手機號 |
| TELEGRAM_CHANNEL_ID | VIP 群組 ID（負數） |
| BINANCE_API_KEY | 幣安 API Key |
| BINANCE_API_SECRET | 幣安 Secret |
| BINANCE_TESTNET | true（測試）/ false（正式） |
| MAX_POSITION_USDT | 單筆上限，建議 100 |
| MAX_DAILY_LOSS | 每日止損，建議 500 |
| MAX_LEVERAGE | 最高槓桿，建議 20 |
| POSITION_PCT | 倉位比例，建議 0.02 |
| ALERT_CHAT_ID | 你的 Telegram User ID |

---

## ✅ 測試流程

1. `BINANCE_TESTNET=true` 先上測試網
2. 在 VIP 群組複製一條歷史信號，手動貼到群組
3. 確認 Zeabur Logs 出現解析成功 + 下單成功
4. 幣安測試網確認訂單出現
5. 沒問題 → 改 `BINANCE_TESTNET=false`

---

## 🆘 常見錯誤

| 錯誤訊息 | 解決方法 |
|----------|---------|
| `TELEGRAM_API_ID` 為 0 | 環境變數未設置 |
| `SessionPasswordNeededError` | 重跑 init_session.py 輸入兩步驟密碼 |
| `BinanceAPIException -2019` | 保證金不足，降低倉位或加入資金 |
| `LOT_SIZE error` | 數量精度問題，通常自動修正 |
| 群組 ID 填錯 | 重跑 init_session.py 查看群組列表 |
