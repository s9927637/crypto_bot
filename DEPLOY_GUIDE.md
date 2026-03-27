# 完整部署指南

## 📁 檔案清單

| 檔案 | 說明 |
|------|------|
| `crypto_bot.py` | 主程式 |
| `init_session.py` | 初始化 Telegram Session（本機跑一次） |
| `requirements.txt` | Python 依賴套件 |
| `.gitignore` | Git 忽略規則 |
| `.env.example` | 環境變數範本 |
| `QUICKSTART.md` | 快速部署（5 分鐘） |
| `DEPLOY_GUIDE.md` | 本文件 |
| `PROJECT_COMPLETE.md` | 專案完整說明 |

---

## 🔑 取得所有憑證

### Telegram API
1. 前往 https://my.telegram.org
2. 登入 → `API development tools`
3. 建立 App（名稱隨意）
4. 記下 `api_id` 和 `api_hash`

### Telegram 群組 ID
執行 `init_session.py` 後會自動列出所有群組 ID。  
VIP 群組的 ID 通常是負數（例如 `-1001234567890`）。

### 你的 Telegram User ID
私訊 `@userinfobot`，它會回覆你的 User ID。

### 幣安測試網 API（先測試用）
1. https://testnet.binancefuture.com
2. 用 GitHub 登入
3. 右上角 → API Key → 生成並複製

### 幣安正式 API（測試通過後）
1. 幣安 → 帳戶 → API 管理
2. 建立 API Key
3. 權限：只勾 **期貨交易**，不勾提現
4. 建議限制 IP（可選，更安全）

---

## 📱 生成 Telegram Session

**只需在本機執行一次：**

```bash
pip install telethon
python init_session.py
```

按照提示輸入：
- API ID / Hash
- 手機號（含國碼，例如 +886912345678）
- Telegram 驗證碼

執行完成後：
- 產生 `bot_session.session` 檔案
- 顯示所有群組 ID 清單

---

## 🐙 上傳到 GitHub

### 方法 A：網頁上傳（最簡單）
1. GitHub → New repository
2. 名稱：`crypto-trading-bot`
3. 設為 **Private**（重要！）
4. Create repository
5. 點擊 `uploading an existing file`
6. 拖入所有檔案（含 `bot_session.session`）
7. Commit changes

### 方法 B：命令列
```bash
cd crypto_bot
git init
git add .
git commit -m "init"
git branch -M main
git remote add origin https://github.com/你的帳號/crypto-trading-bot.git
git push -u origin main
# 輸入密碼時使用 Personal Access Token
```

---

## ☁️ 部署到 Zeabur

1. 前往 https://zeabur.com → 登入
2. New Project → Deploy from GitHub
3. 選擇 `crypto-trading-bot`
4. Zeabur 會自動偵測 Python 環境
5. 進入 Variables 頁面，逐一新增環境變數（見下方清單）
6. 點擊 Redeploy

### 環境變數完整清單

| 變數名稱 | 說明 | 範例 |
|---------|------|------|
| `TELEGRAM_API_ID` | Telegram App ID | `12345678` |
| `TELEGRAM_API_HASH` | Telegram Hash | `abcdef...` |
| `TELEGRAM_PHONE` | 手機號（含國碼） | `+886912345678` |
| `TELEGRAM_CHANNEL_ID` | VIP 群組 ID（負數） | `-1001234567890` |
| `BINANCE_API_KEY` | 幣安 API Key | `abc...` |
| `BINANCE_API_SECRET` | 幣安 Secret | `xyz...` |
| `BINANCE_TESTNET` | 測試網模式 | `true` |
| `MAX_POSITION_USDT` | 單筆最大倉位 | `100` |
| `MAX_DAILY_LOSS` | 每日最大虧損 | `500` |
| `MAX_LEVERAGE` | 最高槓桿倍數 | `20` |
| `POSITION_PCT` | 帳戶倉位比例 | `0.02` |
| `ALERT_CHAT_ID` | 你的 Telegram User ID | `123456789` |

---

## ✅ 驗證部署成功

### Zeabur Logs 應出現：
```
🧪 幣安測試網模式
🤖 Bot 啟動成功，監聽中...
```

### Telegram 應收到：
```
🤖 交易 Bot 已啟動，正在監聽信號...
```

### 測試信號解析：
在 VIP 群組（或自己的測試群組）發送：
```
PAIR: #BTC/USDT
POSITION: LONG (10X)
ENTRY ZONE: 80000 - 78000
TARGETS: 85000 / 90000 / 95000
STOPLOSS: 75000
```

Bot 應該會解析並嘗試下單，並發通知給你。

---

## 🔄 切換到正式交易

確認測試網一切正常後：

1. 幣安申請正式 Futures API Key
2. Zeabur Variables 修改：
   - `BINANCE_TESTNET` → `false`
   - `BINANCE_API_KEY` → 正式 Key
   - `BINANCE_API_SECRET` → 正式 Secret
3. Redeploy

---

## 🆘 常見問題排查

| 問題 | 原因 | 解決方法 |
|------|------|---------|
| Bot 無法啟動 | 環境變數缺少 | 確認 12 個都填了 |
| Telegram 連接失敗 | Session 未上傳 | 確認 `bot_session.session` 在 GitHub |
| 信號沒被解析 | 格式不符 | 檢查信號是否含 PAIR / POSITION / ENTRY |
| 幣安下單失敗 | API 錯誤 | 確認 API 有期貨交易權限 |
| 群組 ID 錯誤 | ID 填錯 | 重跑 `init_session.py` 查看清單 |

---

## 💰 Zeabur 費用

| 方案 | 費用 | 適合 |
|------|------|------|
| 免費 | $0（每月 $5 額度） | 測試階段 |
| Developer | $5/月 | 正式運行（推薦） |

---

## 🔒 安全提醒

**必須做：**
- ✅ GitHub Repo 設為 **Private**
- ✅ 先在測試網跑至少一週
- ✅ 幣安 API 不開提現權限

**絕對不要：**
- ❌ Repo 設為 Public
- ❌ 把 API Key 寫死在程式碼裡
- ❌ 跳過測試網直接正式下單
