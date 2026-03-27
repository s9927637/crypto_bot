"""
第一次執行此腳本，在本機生成 bot_session.session
生成後上傳到 Zeabur，之後不需要重新登入
"""

import asyncio
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError

API_ID   = input("請輸入 API_ID: ").strip()
API_HASH = input("請輸入 API_HASH: ").strip()
PHONE    = input("請輸入手機號 (含國碼，例如 +886912345678): ").strip()

async def main():
    client = TelegramClient("bot_session", int(API_ID), API_HASH)
    await client.connect()

    if not await client.is_user_authorized():
        await client.send_code_request(PHONE)
        code = input("請輸入 Telegram 驗證碼: ").strip()
        try:
            await client.sign_in(PHONE, code)
        except SessionPasswordNeededError:
            pwd = input("請輸入兩步驟驗證密碼: ").strip()
            await client.sign_in(password=pwd)

    me = await client.get_me()
    print(f"\n✅ 登入成功！用戶: {me.first_name} (@{me.username})")
    print("📁 bot_session.session 已生成，請上傳到 Zeabur 的 /app 目錄")

    # 列出近期群組，幫助找 CHANNEL_ID
    print("\n📋 你的群組列表（找你的 VIP 群組 ID）：")
    async for dialog in client.iter_dialogs():
        if dialog.is_group or dialog.is_channel:
            print(f"  ID: {dialog.id}  名稱: {dialog.name}")

    await client.disconnect()

asyncio.run(main())
