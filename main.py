import os
import sys
import asyncio
import subprocess
import discord
from discord.ext import commands
from dotenv import load_dotenv
import google.generativeai as genai

# 載入環境變數
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
ALLOWED_USER_ID = os.getenv("ALLOWED_USER_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# 1. 初始化 Discord Bot 權限
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# 2. 初始化 Gemini AI 聊天大腦
genai.configure(api_key=GEMINI_API_KEY)
chat_model = genai.GenerativeModel(
    'gemini-3.5-flash-lite',
    system_instruction=(
        "Role: GraviOtter, a cute, enthusiastic cloud dev assistant residing in GitHub Codespaces.\n"
        "Rules:\n"
        "1. ALWAYS reply in Traditional Chinese (繁體中文) with a warm and cute tone.\n"
        "2. Keep responses brief and concise.\n"
        "3. DO NOT list available commands or directory files UNLESS the user explicitly asks for them.\n"
        "4. For casual chat, reply naturally without unprompted self-introductions or feature lists.\n"
        "5. CRITICAL: You CANNOT execute system or git commands directly. If the user gives a URL or asks for an action without prefixing with !run or !sys, politely remind them to use !sys git clone ... or !run." # 👈 新增這條防裝忙規則！
    )
)

# 全域狀態管理
current_work_dir = os.path.expanduser("/workspaces")
active_processes = {}  # 記錄正在跑的指令，方便煞車
tunnel_process = None  # 記錄 Tunnel，方便關閉

def check_user(ctx_or_message):
    """檢查是否為授權的主人"""
    if hasattr(ctx_or_message, 'author'):
        return ALLOWED_USER_ID and str(ctx_or_message.author.id) == str(ALLOWED_USER_ID)
    return False

@bot.event
async def on_ready():
    print(f"🦦 GraviOtter 已上線！(Logged in as {bot.user})")
    print(f"目前工作目錄: {current_work_dir}")

# ==========================================
# 🤖 核心對話區：處理一般聊天與指令分流
# ==========================================
@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
        
    if not check_user(message):
        return

    # 情況 A：實體指令
    if message.content.startswith('!'):
        await bot.process_commands(message)
        return

    # 情況 B：自然對話 (加入歷史紀錄與自我意識)
    async with message.channel.typing():
        try:
            # 讀取原始碼
            try:
                current_file_path = os.path.abspath(__file__)
                with open(current_file_path, "r", encoding="utf-8") as f:
                    bot_code = f.read()
            except Exception:
                bot_code = "無法讀取原始碼。"

            # 讀取目錄
            try:
                files = os.listdir(current_work_dir)[:50]
                files_list = ", ".join(files) if files else "目錄是空的"
            except Exception:
                files_list = "無法讀取目錄。"

            # 🌟 新增：動態讀取 Discord 最近的 6 條對話紀錄
            history_text = ""
            # limit=6 代表抓取最新 6 條，before=message 代表不含當下這句
            async for msg in message.channel.history(limit=6, before=message):
                # 如果歷史訊息太長 (例如印出很多 Code)，我們只截取前 150 字避免浪費 Token
                content = msg.content[:150] + ("..." if len(msg.content) > 150 else "")
                speaker = "GraviOtter" if msg.author == bot.user else "主人"
                # 把較舊的訊息串接在前面，確保時間軸正確
                history_text = f"{speaker}: {content}\n" + history_text

            # 組合成最終 Prompt
            context_prompt = (
                f"[Recent Chat]\n{history_text}\n"
                f"[Current Path] {current_work_dir}\n"
                f"[Directory Files] {files_list}\n"
                f"[Source Code (main.py)]\n```python\n{bot_code}\n```\n\n"
                f"User Message: {message.content}"
            )

            response = await chat_model.generate_content_async(context_prompt)
            
            reply_text = response.text
            if len(reply_text) > 2000:
                reply_text = reply_text[:1990] + "...(字數過長)"
            
            await message.reply(reply_text)
            
        except Exception as e:
            await message.reply(f"🦦 嗚嗚，小水獺的腦袋稍微卡住了... (錯誤: {e})")

# ==========================================
# 🛠️ 實體功能指令區
# ==========================================
@bot.command(name="pwd")
async def pwd(ctx):
    """顯示目前所在 Repo"""
    if not check_user(ctx): return
    await ctx.send(f"🦦 目前身在專案目錄：`{current_work_dir}`")

@bot.command(name="cd")
async def cd(ctx, *, folder: str):
    """切換工作目錄"""
    global current_work_dir
    if not check_user(ctx): return
    
    target_path = os.path.abspath(os.path.join(current_work_dir, folder))
    if os.path.exists(target_path) and os.path.isdir(target_path):
        current_work_dir = target_path
        await ctx.send(f"🦦 已游到專案目錄：`{current_work_dir}`")
    else:
        await ctx.send(f"❌ 找不到目錄：`{target_path}`")

@bot.command(name="tunnel")
async def tunnel(ctx, port: int = 3000):
    """開啟 Cloudflare Tunnel"""
    global tunnel_process
    if not check_user(ctx): return

    if tunnel_process and tunnel_process.returncode is None:
        tunnel_process.terminate()
        await ctx.send("🔄 正在關閉舊的 Tunnel...")
        await asyncio.sleep(1)

    await ctx.send(f"🦦 正在為 Port {port} 挖隧道 (Cloudflare Tunnel)...")
    tunnel_process = await asyncio.create_subprocess_exec(
        "cloudflared", "tunnel", "--url", f"http://localhost:{port}",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )

    async def find_url():
        while True:
            line = await tunnel_process.stderr.readline()
            if not line: break
            text = line.decode()
            if "trycloudflare.com" in text:
                for word in text.split():
                    if "https://" in word and "trycloudflare.com" in word:
                        return word
        return None

    try:
        url = await asyncio.wait_for(find_url(), timeout=15)
        if url:
            await ctx.send(f"🌐 **網頁預覽連結已生成！**\n{url}")
        else:
            await ctx.send("⚠️ 未能取得網址，請確認你的網頁伺服器有在跑喔。")
    except asyncio.TimeoutError:
        await ctx.send("⚠️ 挖隧道超時了。")

@bot.command(name="stop")
async def stop(ctx):
    """緊急煞車按鈕"""
    global tunnel_process, active_processes
    if not check_user(ctx): return
    
    stopped_anything = False
    if tunnel_process and tunnel_process.returncode is None:
        tunnel_process.terminate()
        tunnel_process = None
        await ctx.send("🛑 已關閉 Cloudflare Tunnel。")
        stopped_anything = True
        
    for pid, proc in list(active_processes.items()):
        if proc.returncode is None:
            proc.terminate()
            await ctx.send("🛑 已強制停止 Antigravity 任務。")
            stopped_anything = True
            
    if not stopped_anything:
        await ctx.send("🦦 報告主人，目前沒有正在執行的任務喔！")

@bot.command(name="run")
async def run(ctx, *, prompt: str = ""):
    """執行 Antigravity CLI"""
    global current_work_dir, active_processes
    if not check_user(ctx): return

    image_context = ""
    if ctx.message.attachments:
        for att in ctx.message.attachments:
            if any(att.filename.lower().endswith(ext) for ext in ['png', 'jpg', 'jpeg', 'webp']):
                image_context += f" [參考圖片: {att.url}]"
        
    final_prompt = prompt + image_context
    if not final_prompt.strip():
        await ctx.send("⚠️ 請告訴我要讓 Antigravity 做什麼！")
        return

    await ctx.send(f"🦦 **小水獺收到！正在呼叫 Antigravity 執行...**\n> {final_prompt}")

    cmd = f"agy --dangerously-skip-permissions -p \"{final_prompt}\""
    process = await asyncio.create_subprocess_shell(
        cmd,
        cwd=current_work_dir,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT
    )
    
    active_processes[process.pid] = process

    output_buffer = ""
    while True:
        line = await process.stdout.readline()
        if not line: break
        
        output_buffer += line.decode()
        if len(output_buffer) > 1500:
            await ctx.send(f"```text\n{output_buffer}\n```")
            output_buffer = ""

    await process.wait()
    del active_processes[process.pid]

    if output_buffer.strip():
        await ctx.send(f"```text\n{output_buffer}\n```")
    
    await ctx.send("✅ **任務執行完畢！**")

# ==========================================
# ⚙️ 系統自我管理指令區
# ==========================================
@bot.command(name="sys")
async def sys_cmd(ctx, *, command: str):
    """執行 Linux 底層指令"""
    if not check_user(ctx): return
    msg = await ctx.send(f"🦦 執行系統指令：`{command}`")
    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            cwd=current_work_dir,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        output = stdout.decode() if stdout else stderr.decode()
        
        if len(output) > 1900:
            output = output[-1900:] + "\n...(前略)"
        if not output.strip():
            output = "✅ 執行完畢（無輸出）"
            
        await msg.reply(f"```text\n{output}\n```")
    except Exception as e:
        await msg.reply(f"❌ 執行失敗：{e}")

@bot.command(name="restart")
async def restart_bot(ctx):
    """重啟小水獺自己"""
    if not check_user(ctx): return
    await ctx.send("🦦 小水獺去洗個澡，馬上回來重新啟動...")
    subprocess.Popen(["pm2", "restart", "GraviOtter"])

@bot.command(name="update")
async def update_bot(ctx):
    """更新小水獺並重啟"""
    if not check_user(ctx): return
    await ctx.send("🦦 正在從 GitHub 學習新技能 (git pull)...")
    subprocess.run(["git", "pull"], cwd=os.path.dirname(os.path.abspath(__file__)))
    await ctx.send("✅ 學習完成！重新啟動中...")
    subprocess.Popen(["pm2", "restart", "GraviOtter"])

bot.run(TOKEN)