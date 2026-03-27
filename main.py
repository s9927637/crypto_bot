"""
Telegram 加密貨幣信號自動交易 Bot v2.0
功能：監聽 Telegram → 解析信號 → 風控過濾 → 幣安期貨下單
"""

import asyncio
import re
import logging
import os
import json
import time
from datetime import datetime, date
from typing import Optional, Dict, List
from decimal import Decimal, ROUND_DOWN

from telethon import TelegramClient, events
from binance.client import Client as BinanceClient
from binance.exceptions import BinanceAPIException

# =====================================================================
# 配置（全部從環境變數讀取，安全部署）
# =====================================================================
CONFIG = {
    "telegram": {
        "api_id":     int(os.environ.get("TELEGRAM_API_ID", "0")),
        "api_hash":   os.environ.get("TELEGRAM_API_HASH", ""),
        "phone":      os.environ.get("TELEGRAM_PHONE", ""),
        "channel_id": int(os.environ.get("TELEGRAM_CHANNEL_ID", "0")),
    },
    "binance": {
        "api_key":    os.environ.get("BINANCE_API_KEY", ""),
        "api_secret": os.environ.get("BINANCE_API_SECRET", ""),
        "testnet":    os.environ.get("BINANCE_TESTNET", "true").lower() == "true",
    },
    "risk": {
        "max_position_usdt":       float(os.environ.get("MAX_POSITION_USDT", "100")),
        "max_daily_loss":          float(os.environ.get("MAX_DAILY_LOSS", "500")),
        "max_leverage":            int(os.environ.get("MAX_LEVERAGE", "20")),
        "default_position_pct":    float(os.environ.get("POSITION_PCT", "0.02")),
        "max_concurrent_positions": int(os.environ.get("MAX_POSITIONS", "5")),
    },
    "safety": {
        "emergency_stop": False,
    },
    "trading": {
        "enable_multi_entry": True,
        "use_market_order":   True,   # True=市價, False=限價
        "entry_spread_pct":   0.005,  # 限價單容忍滑點 0.5%
    },
    "alert_chat_id": os.environ.get("ALERT_CHAT_ID", ""),
}

# =====================================================================
# 日誌
# =====================================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("trading_bot.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


# =====================================================================
# 信號解析器
# =====================================================================
class SignalParser:
    """
    解析格式（Crypto Space VIP 1.0 風格）：
        PAIR: #MYX/USDT
        POSITION: LONG (10X)
        ENTRY ZONE: 0.32 - 0.29
        TARGETS: 0.41 / 0.50 / 0.65 / 0.80
        STOPLOSS: 0.27
    """

    @staticmethod
    def parse(text: str) -> Optional[Dict]:
        try:
            sig = {}
            t = text.upper()

            # ── 幣對 ──────────────────────────────────────────────
            m = re.search(r"PAIR\s*[:\-]\s*[#]?([A-Z0-9]+)[/\-_]?(?:USDT|BUSD|BTC|ETH)?", t)
            if not m:
                return None
            base = m.group(1).strip()
            sig["pair"] = base + "USDT" if not base.endswith("USDT") else base

            # ── 方向 ──────────────────────────────────────────────
            if "LONG" in t:
                sig["position"] = "LONG"
            elif "SHORT" in t:
                sig["position"] = "SHORT"
            else:
                return None

            # ── 槓桿 ──────────────────────────────────────────────
            lev_m = re.search(r"(\d+)\s*[Xx×]", t)
            sig["leverage"] = min(int(lev_m.group(1)), CONFIG["risk"]["max_leverage"]) if lev_m else 10

            # ── 入場價（支援區間 / 單點 / 多點）──────────────────
            zone_m = re.search(r"ENTRY(?:\s*ZONE)?\s*[:\-]\s*([\d.,\s/\-]+)", t)
            if not zone_m:
                return None
            raw_entries = re.findall(r"[\d.]+", zone_m.group(1))
            if not raw_entries:
                return None
            sig["entries"] = [float(x) for x in raw_entries[:4]]  # 最多 4 個入場點

            # ── 止盈目標 ──────────────────────────────────────────
            tp_m = re.search(r"TARGET[S]?\s*[:\-]\s*([\d.,\s/]+)", t)
            if tp_m:
                sig["targets"] = [float(x) for x in re.findall(r"[\d.]+", tp_m.group(1))[:6]]
            else:
                sig["targets"] = []

            # ── 止損 ──────────────────────────────────────────────
            sl_m = re.search(r"STOP\s*(?:LOSS)?\s*[:\-]\s*([\d.]+)", t)
            sig["stop_loss"] = float(sl_m.group(1)) if sl_m else None

            # ── 基本驗證 ──────────────────────────────────────────
            if not sig.get("entries") or not sig.get("stop_loss"):
                return None

            logger.info(f"✅ 解析成功: {sig}")
            return sig

        except Exception as e:
            logger.error(f"解析失敗: {e}")
            return None


# =====================================================================
# 幣安交易執行器
# =====================================================================
class BinanceTrader:
    MAX_RETRIES = 3
    RETRY_DELAY = 2  # 秒

    def __init__(self):
        if CONFIG["binance"]["testnet"]:
            self.client = BinanceClient(
                CONFIG["binance"]["api_key"],
                CONFIG["binance"]["api_secret"],
                testnet=True,
            )
            logger.info("🧪 幣安測試網模式")
        else:
            self.client = BinanceClient(
                CONFIG["binance"]["api_key"],
                CONFIG["binance"]["api_secret"],
            )
            logger.info("🚀 幣安正式網模式")

        self._symbol_info_cache: Dict[str, dict] = {}

    # ── 重試包裝 ─────────────────────────────────────────────────
    def _retry(self, fn, *args, **kwargs):
        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                return fn(*args, **kwargs)
            except BinanceAPIException as e:
                logger.warning(f"API 錯誤 (嘗試 {attempt}/{self.MAX_RETRIES}): {e}")
                if attempt == self.MAX_RETRIES:
                    raise
                time.sleep(self.RETRY_DELAY * attempt)
        return None

    # ── 取得交易對精度資訊 ───────────────────────────────────────
    def _get_symbol_info(self, symbol: str) -> dict:
        if symbol not in self._symbol_info_cache:
            info = self.client.futures_exchange_info()
            for s in info["symbols"]:
                if s["symbol"] == symbol:
                    self._symbol_info_cache[symbol] = s
                    break
        return self._symbol_info_cache.get(symbol, {})

    # ── 數量精度對齊 ─────────────────────────────────────────────
    def _round_quantity(self, symbol: str, qty: float) -> float:
        info = self._get_symbol_info(symbol)
        step = 1.0
        for f in info.get("filters", []):
            if f["filterType"] == "LOT_SIZE":
                step = float(f["stepSize"])
                break
        precision = len(str(step).rstrip("0").split(".")[-1]) if "." in str(step) else 0
        d = Decimal(str(qty)).quantize(Decimal(str(step)), rounding=ROUND_DOWN)
        return float(d)

    # ── 價格精度對齊 ─────────────────────────────────────────────
    def _round_price(self, symbol: str, price: float) -> float:
        info = self._get_symbol_info(symbol)
        tick = 0.001
        for f in info.get("filters", []):
            if f["filterType"] == "PRICE_FILTER":
                tick = float(f["tickSize"])
                break
        d = Decimal(str(price)).quantize(Decimal(str(tick)), rounding=ROUND_DOWN)
        return float(d)

    # ── 設定槓桿 ─────────────────────────────────────────────────
    def set_leverage(self, symbol: str, leverage: int) -> int:
        actual = min(leverage, CONFIG["risk"]["max_leverage"])
        try:
            self._retry(self.client.futures_change_leverage, symbol=symbol, leverage=actual)
            logger.info(f"⚙️  {symbol} 槓桿設為 {actual}x")
            return actual
        except Exception as e:
            logger.error(f"槓桿設置失敗: {e}")
            return 0

    # ── 取帳戶 USDT 餘額 ─────────────────────────────────────────
    def get_usdt_balance(self) -> float:
        try:
            balances = self._retry(self.client.futures_account_balance)
            for b in balances:
                if b["asset"] == "USDT":
                    return float(b["balance"])
        except Exception as e:
            logger.error(f"餘額查詢失敗: {e}")
        return 0.0

    # ── 計算開倉數量 ─────────────────────────────────────────────
    def calc_position_size(self, symbol: str, entry_price: float, leverage: int) -> float:
        balance = self.get_usdt_balance()
        pct = CONFIG["risk"]["default_position_pct"]
        max_usdt = CONFIG["risk"]["max_position_usdt"]

        notional = min(balance * pct * leverage, max_usdt * leverage)
        qty_raw = notional / entry_price
        qty = self._round_quantity(symbol, qty_raw)

        logger.info(f"💰 倉位計算: 餘額={balance:.2f}U → 名目={notional:.2f}U → 數量={qty}")
        return qty

    # ── 市價開倉 ─────────────────────────────────────────────────
    def market_open(self, symbol: str, side: str, qty: float) -> Optional[dict]:
        try:
            order = self._retry(
                self.client.futures_create_order,
                symbol=symbol,
                side=side,
                type="MARKET",
                quantity=qty,
            )
            logger.info(f"✅ 開倉成功: {symbol} {side} {qty}")
            return order
        except BinanceAPIException as e:
            logger.error(f"❌ 開倉失敗: {e}")
            return None

    # ── 限價開倉 ─────────────────────────────────────────────────
    def limit_open(self, symbol: str, side: str, qty: float, price: float) -> Optional[dict]:
        try:
            p = self._round_price(symbol, price)
            order = self._retry(
                self.client.futures_create_order,
                symbol=symbol,
                side=side,
                type="LIMIT",
                timeInForce="GTC",
                quantity=qty,
                price=str(p),
            )
            logger.info(f"✅ 限價單掛出: {symbol} {side} {qty} @ {p}")
            return order
        except BinanceAPIException as e:
            logger.error(f"❌ 限價單失敗: {e}")
            return None

    # ── 止損單 ───────────────────────────────────────────────────
    def place_stop_loss(self, symbol: str, side: str, qty: float, stop_price: float) -> Optional[dict]:
        close_side = "SELL" if side == "BUY" else "BUY"
        try:
            p = self._round_price(symbol, stop_price)
            order = self._retry(
                self.client.futures_create_order,
                symbol=symbol,
                side=close_side,
                type="STOP_MARKET",
                quantity=qty,
                stopPrice=str(p),
                reduceOnly=True,
            )
            logger.info(f"🛑 止損設置: {symbol} @ {p}")
            return order
        except BinanceAPIException as e:
            logger.error(f"❌ 止損設置失敗: {e}")
            return None

    # ── 止盈單（分批） ───────────────────────────────────────────
    def place_take_profits(
        self, symbol: str, side: str, total_qty: float, targets: List[float]
    ) -> List[dict]:
        if not targets:
            return []

        close_side = "SELL" if side == "BUY" else "BUY"
        n = len(targets)

        # 分配比例：第1個TP 40%，後面均分，最後補足
        if n == 1:
            ratios = [1.0]
        else:
            ratios = [0.4] + [0.6 / (n - 1)] * (n - 1)
            ratios[-1] = 1.0 - sum(ratios[:-1])  # 確保總和 = 1

        orders = []
        for i, (tp, ratio) in enumerate(zip(targets, ratios)):
            qty = self._round_quantity(symbol, total_qty * ratio)
            if qty <= 0:
                continue
            try:
                p = self._round_price(symbol, tp)
                order = self._retry(
                    self.client.futures_create_order,
                    symbol=symbol,
                    side=close_side,
                    type="TAKE_PROFIT_MARKET",
                    quantity=qty,
                    stopPrice=str(p),
                    reduceOnly=True,
                )
                logger.info(f"🎯 TP{i+1} 設置: {symbol} @ {p} ({ratio*100:.0f}%)")
                orders.append(order)
            except BinanceAPIException as e:
                logger.error(f"❌ TP{i+1} 失敗: {e}")

        return orders


# =====================================================================
# 風控管理器
# =====================================================================
class RiskManager:
    def __init__(self):
        self.daily_loss = 0.0
        self.active_positions: Dict[str, dict] = {}  # symbol → order info
        self.last_reset = date.today()
        self.is_paused = False

    def reset_daily_if_needed(self):
        if date.today() > self.last_reset:
            self.daily_loss = 0.0
            self.last_reset = date.today()
            logger.info("📅 每日風控已重置")

    def can_trade(self) -> tuple[bool, str]:
        """返回 (允許, 原因)"""
        self.reset_daily_if_needed()

        if CONFIG["safety"]["emergency_stop"]:
            return False, "🚨 緊急停止已啟動"

        if self.is_paused:
            return False, "⏸️ 交易已暫停"

        if self.daily_loss >= CONFIG["risk"]["max_daily_loss"]:
            return False, f"🛑 每日虧損上限 {CONFIG['risk']['max_daily_loss']} USDT 已到達"

        max_pos = CONFIG["risk"]["max_concurrent_positions"]
        if len(self.active_positions) >= max_pos:
            return False, f"⚠️ 已達最大同時持倉數 {max_pos}"

        return True, ""

    def register_position(self, symbol: str, info: dict):
        self.active_positions[symbol] = info

    def remove_position(self, symbol: str):
        self.active_positions.pop(symbol, None)

    def record_pnl(self, pnl: float):
        if pnl < 0:
            self.daily_loss += abs(pnl)

    @property
    def daily_loss_pct(self) -> float:
        return self.daily_loss / CONFIG["risk"]["max_daily_loss"] * 100


# =====================================================================
# 通知器
# =====================================================================
class Notifier:
    def __init__(self, tg_client: TelegramClient):
        self.client = tg_client
        self.chat_id = CONFIG["alert_chat_id"]

    async def send(self, text: str):
        if not self.chat_id:
            return
        try:
            await self.client.send_message(int(self.chat_id), text, parse_mode="markdown")
        except Exception as e:
            logger.error(f"通知發送失敗: {e}")


# =====================================================================
# 主交易 Bot
# =====================================================================
class TradingBot:
    def __init__(self):
        self.tg = TelegramClient(
            "bot_session",
            CONFIG["telegram"]["api_id"],
            CONFIG["telegram"]["api_hash"],
        )
        self.parser = SignalParser()
        self.trader = BinanceTrader()
        self.risk = RiskManager()
        self.notifier: Optional[Notifier] = None

    # ── 執行信號完整流程 ─────────────────────────────────────────
    async def execute_signal(self, signal: Dict):
        symbol   = signal["pair"]
        direction = signal["position"]
        leverage  = signal["leverage"]
        entries   = signal["entries"]
        targets   = signal["targets"]
        stop_loss = signal["stop_loss"]
        side      = "BUY" if direction == "LONG" else "SELL"

        # 1️⃣ 已有持倉 → 跳過
        if symbol in self.risk.active_positions:
            logger.warning(f"⚠️ {symbol} 已有持倉，跳過")
            return

        # 2️⃣ 風控檢查
        ok, reason = self.risk.can_trade()
        if not ok:
            logger.warning(reason)
            await self.notifier.send(f"⛔ 跳過信號: {reason}\n幣對: {symbol}")
            return

        # 3️⃣ 設槓桿
        actual_lev = self.trader.set_leverage(symbol, leverage)
        if actual_lev == 0:
            return

        # 4️⃣ 計算數量（以第一個入場價為基準）
        base_price = entries[0]
        qty = self.trader.calc_position_size(symbol, base_price, actual_lev)
        if qty <= 0:
            logger.error("數量計算結果為 0，跳過")
            return

        # 5️⃣ 下單（市價 or 限價）
        order = None
        if CONFIG["trading"]["use_market_order"]:
            order = self.trader.market_open(symbol, side, qty)
        else:
            order = self.trader.limit_open(symbol, side, qty, base_price)

        if not order:
            await self.notifier.send(f"❌ {symbol} 開倉失敗，請檢查日誌")
            return

        # 6️⃣ 設置止損
        if stop_loss:
            self.trader.place_stop_loss(symbol, side, qty, stop_loss)

        # 7️⃣ 設置止盈（分批）
        if targets:
            self.trader.place_take_profits(symbol, side, qty, targets)

        # 8️⃣ 記錄持倉
        self.risk.register_position(symbol, {
            "signal": signal,
            "qty": qty,
            "leverage": actual_lev,
            "open_time": datetime.now().isoformat(),
            "order_id": order.get("orderId"),
        })

        # 9️⃣ 發送成功通知
        tp_text = " / ".join([str(t) for t in targets]) if targets else "無"
        msg = (
            f"✅ *下單成功*\n"
            f"幣對: `{symbol}`\n"
            f"方向: {direction} {actual_lev}x\n"
            f"入場: {base_price}\n"
            f"止損: {stop_loss}\n"
            f"止盈: {tp_text}\n"
            f"數量: {qty}\n"
            f"時間: {datetime.now().strftime('%H:%M:%S')}"
        )
        await self.notifier.send(msg)
        logger.info(f"✅ 完整執行完畢: {symbol}")

    # ── 啟動 ─────────────────────────────────────────────────────
    async def run(self):
        await self.tg.start(phone=CONFIG["telegram"]["phone"])
        self.notifier = Notifier(self.tg)

        logger.info("🤖 Bot 啟動成功，監聽中...")
        await self.notifier.send("🤖 交易 Bot 已啟動，正在監聽信號...")

        channel_id = CONFIG["telegram"]["channel_id"]

        @self.tg.on(events.NewMessage(chats=channel_id))
        async def on_message(event):
            text = event.message.message or ""
            logger.debug(f"收到訊息: {text[:80]}")

            # 過濾：只處理含交易關鍵字的訊息
            keywords = ["PAIR", "POSITION", "ENTRY", "STOPLOSS", "STOP LOSS"]
            if not any(kw in text.upper() for kw in keywords):
                return

            signal = self.parser.parse(text)
            if not signal:
                logger.info("解析失敗，非標準信號格式")
                return

            await self.execute_signal(signal)

        await self.tg.run_until_disconnected()


# =====================================================================
# 入口
# =====================================================================
if __name__ == "__main__":
    bot = TradingBot()
    asyncio.run(bot.run())
