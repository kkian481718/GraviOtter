import os
import sys
import asyncio
import discord
from discord.ext import commands
from dotenv import load_dotenv
from google import genai
import re
import json
import datetime
import shutil
from keep_alive import keep_alive

# 載入環境變數
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
ALLOWED_USER_ID = os.getenv("ALLOWED_USER_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# 1. 初始化 Discord Bot 權限
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# 2. 初始化 Gemini AI 聊天大腦 (使用最新 google-genai)
try:
    genai_client = genai.Client(api_key=GEMINI_API_KEY)
except Exception as e:
    print(f"⚠️ SDK 初始化警告: {e}")

MODEL_NAME = "gemini-3.5-flash-lite"
SYSTEM_INSTRUCTION = (
    "Role: GraviOtter, a cute, enthusiastic cloud dev assistant residing in GitHub Codespaces.\n"
    "Rules:\n"
    "1. ALWAYS reply in Traditional Chinese (繁體中文) with a warm and cute tone.\n"
    "2. Keep responses brief and concise.\n"
    "3. DO NOT list available commands or directory files UNLESS the user explicitly asks for them.\n"
    "4. For casual chat, reply naturally without unprompted self-introductions or feature lists.\n"
    "5. CRITICAL: 你的主要工作是日常對話。如果主人提出需要看程式碼、修改程式碼、除錯 (debug)、建立檔案等任務，請直接拒絕猜測，並用這句話提醒主人：『Miffy，這需要出動小水獺的超級大腦！請輸入 `!agent` 來喚醒我的工作模式哦！』\n"
    "6. If the user provides an action instead of chat while in an active agent session, remind them the agent will see it automatically.\n"
    "7. CRITICAL: 你的主人名字叫 Miffy，請稱呼對方為 Miffy，不要再叫「主人」，那樣太油了！"
)

# 3. 用量管理
USAGE_FILE = "bot_usage.json"
DAILY_TOKEN_LIMIT = 1000000  # 100萬 Tokens 警報門檻
usage_lock = asyncio.Lock()  # 新增 Lock 防止寫入衝突

async def record_token_usage(tokens):
    today_str = datetime.date.today().isoformat()
    data = {}
    async with usage_lock:
        if os.path.exists(USAGE_FILE):
            try:
                with open(USAGE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                pass
                
        # Reset for a new day
        if "date" not in data or data.get("date") != today_str:
            data = {"date": today_str, "tokens": 0, "warned": False}
            
        data["tokens"] += tokens
        with open(USAGE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f)
    return data

# 全域狀態管理
current_work_dir = os.path.abspath(os.path.dirname(__file__))
active_processes = {}  # 記錄正在跑的指令 (包含 run / sys / agent)，方便煞車
tunnel_process = None
active_agent_mode = False          # 是否處於 Interactive Agent Session 模式
agent_session_first_turn = True    # 當前 Agent Session 是否為第一輪 (第一輪用 -p，續集用 -c -p)
agent_lock = asyncio.Lock()         # 防止並發執行多個 agent 對話

def resolve_agent_cli_command():
    """解析可用的 Antigravity CLI 指令名稱"""
    candidates = []
    env_cmd = os.getenv("AGENT_CLI_COMMAND")
    if env_cmd:
        candidates.append(env_cmd)
    candidates.extend(["ag", "agy"])
    for cmd in candidates:
        if shutil.which(cmd):
            return cmd
    return None

async def run_agent_turn(channel, prompt: str):
    """執行單輪 Agent 對話，自動處理 -c 繼續模式與 Discord 串流訊息編輯"""
    global current_work_dir, active_agent_mode, agent_session_first_turn, active_processes
    
    if not active_agent_mode:
        return
        
    async with agent_lock:
        if not active_agent_mode:
            return
            
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        env["FORCE_COLOR"] = "1"

        agent_cmd = resolve_agent_cli_command()
        if not agent_cmd:
            await channel.send("⚠️ 找不到 Antigravity CLI 指令（預設嘗試 `ag` / `agy`），請先安裝或設定 `AGENT_CLI_COMMAND`。")
            return

        cmd = [agent_cmd, "--dangerously-skip-permissions"]
        if not agent_session_first_turn:
            cmd.append("-c")
        cmd.extend(["-p", prompt])

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=current_work_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                env=env
            )
            
            active_processes[process.pid] = process
            agent_session_first_turn = False
            
            await stream_to_discord(process.stdout, channel, prefix="🧠 **Agent:**")
            await process.wait()
        except Exception as e:
            await channel.send(f"⚠️ Agent 執行發生錯誤: {e}")
        finally:
            if 'process' in locals() and process.pid in active_processes:
                del active_processes[process.pid]

def check_user(ctx_or_message):
    """檢查是否為授權的主人"""
    if hasattr(ctx_or_message, 'author'):
        return ALLOWED_USER_ID and str(ctx_or_message.author.id) == str(ALLOWED_USER_ID)
    return False

# 過濾命令列 ANSI 彩色控制碼正則，避免 Discord 顯示亂碼
ANSI_ESCAPE = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')

async def stream_to_discord(process_stdout, destination, prefix=""):
    """每隔一段時間將 stdout 同步編輯至 Discord 訊息，並加入防 Rate Limit 機制。"""
    msg = await destination.send(f"{prefix}\n```text\n(等待輸出...)\n```")
    current_msg_content = ""
    last_edit_time = asyncio.get_event_loop().time()
    edit_interval = 1.5  # 初始更新間隔
    
    while True:
        try:
            chunk = await process_stdout.read(128)
        except Exception:
            break
            
        if not chunk:
            break
            
        text = chunk.decode(errors='replace')
        clean_text = ANSI_ESCAPE.sub('', text)
        current_msg_content += clean_text
        
        # 字數限制處理，若過長則分段
        if len(current_msg_content) > 1800:
            try:
                await msg.edit(content=f"{prefix}\n```text\n{current_msg_content}\n```")
            except Exception: pass
            
            # 建立發送新訊息繼續承接文字
            msg = await destination.send(f"```text\n(接續輸出...)\n```")
            current_msg_content = ""
            last_edit_time = asyncio.get_event_loop().time()
            edit_interval = 1.5  # 換新訊息後重置間隔
            continue
            
        now = asyncio.get_event_loop().time()
        # 每隔 edit_interval 秒更新一次畫面
        if now - last_edit_time > edit_interval and current_msg_content:
            try:
                await msg.edit(content=f"{prefix}\n```text\n{current_msg_content}\n```")
                last_edit_time = now
                if edit_interval < 3.5:
                    edit_interval += 0.5  # 漸進拉長間距，避免 Edit 太頻繁觸發 429
            except Exception as e:
                if "429" in str(e):
                    edit_interval = 4.0  # 碰壁了直接大幅降速
                pass

    # 最後結算一次確保畫面同步
    if current_msg_content:
        try:
            await msg.edit(content=f"{prefix}\n```text\n{current_msg_content}\n```\n✅ **輸出完畢**")
        except Exception:
            pass
    else:
        try:
            await msg.edit(content=f"{prefix}\n```text\n(無輸出內容，進程已默默結束)\n```")
        except Exception:
            pass
            
    return current_msg_content

@bot.event
async def on_ready():
    print(f"🦦 GraviOtter 已上線！(Logged in as {bot.user})")
    print(f"目前工作目錄: {current_work_dir}")
    
    # 檢查是否有重啟紀錄，有的話回報給指定頻道
    restart_file = "restart_channel.txt"
    if os.path.exists(restart_file):
        try:
            with open(restart_file, "r") as f:
                channel_id = int(f.read().strip())
            channel = bot.get_channel(channel_id)
            if channel:
                await channel.send("🦦 ✨ 報告 Miffy，我洗完澡帶著新技能回來啦！(重新啟動完成，一切正常運作中)")
            os.remove(restart_file)
        except Exception as e:
            print(f"無法發送重啟通知: {e}")

# ==========================================
# 🤖 核心對話區：處理一般聊天與指令分流
# ==========================================
@bot.event
async def on_message(message):
    global active_agent_mode
    
    if message.author == bot.user:
        return
        
    if not check_user(message):
        return

    # 情況 A：實體指令
    if message.content.startswith('!'):
        await bot.process_commands(message)
        return

    # 情況 B：若開啟 Agent Session 模式，轉送給 Antigravity CLI
    if active_agent_mode:
        await message.add_reaction("🧠")
        bot.loop.create_task(run_agent_turn(message.channel, message.content))
        return

    # 情況 C：無 Agent 時，與自然對話模型 (Flash) 互動
    async with message.channel.typing():
        try:
            # 讀取目錄 (優化為非阻塞讀取)
            try:
                files = await asyncio.to_thread(os.listdir, current_work_dir)
                files_list = ", ".join(files[:50]) if files else "目錄是空的"
            except Exception:
                files_list = "無法讀取目錄。"

            # 歷史對話
            history_text = ""
            async for msg in message.channel.history(limit=6, before=message):
                content = msg.content[:150] + ("..." if len(msg.content) > 150 else "")
                speaker = "GraviOtter" if msg.author == bot.user else "主人"
                history_text = f"{speaker}: {content}\n" + history_text

            context_prompt = (
                f"[Recent Chat]\n{history_text}\n"
                f"[Current Path] {current_work_dir}\n"
                f"[Directory Files] {files_list}\n"
                f"User Message: {message.content}"
            )

            # 新版 genai SDK 呼叫方式 (支援 asyncio 與執行緒備援)
            try:
                response = await genai_client.aio.models.generate_content(
                    model=MODEL_NAME, 
                    contents=context_prompt,
                    config={"system_instruction": SYSTEM_INSTRUCTION}
                )
            except AttributeError:
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(
                    None,
                    lambda: genai_client.models.generate_content(
                        model=MODEL_NAME,
                        contents=context_prompt,
                        config={"system_instruction": SYSTEM_INSTRUCTION}
                    )
                )

            reply_text = response.text
            if len(reply_text) > 2000:
                reply_text = reply_text[:1990] + "...(字數過長)"
                
            # Token 追蹤 (加上 await 並以 Lock 保護 Json 修改)
            if hasattr(response, "usage_metadata") and response.usage_metadata:
                total_tokens = response.usage_metadata.total_token_count
                usage_data = await record_token_usage(total_tokens)
                
                # 警告推播 (發送到 DM)
                if usage_data["tokens"] >= DAILY_TOKEN_LIMIT and not usage_data.get("warned"):
                    usage_data["warned"] = True
                    async with usage_lock:
                        with open(USAGE_FILE, "w", encoding="utf-8") as f:
                            json.dump(usage_data, f)
                    try:
                        await message.author.send(f"🦦 Miffy 注意！今天的 API 額度快滿啦 (已達 {usage_data['tokens']} Tokens)，我的體力快被榨乾了...")
                    except Exception: pass
            
            await message.reply(reply_text)
            
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            await message.reply(f"🦦 嗚嗚，小水獺的腦袋卡住了... (錯誤: {e})\n{tb}")

@bot.event
async def on_command_error(ctx, error):
    """捕捉並顯示指令錯誤，避免默默失敗"""
    await ctx.send(f"⚠️ 指令錯誤: {error}")

# ==========================================
# 🛠️ 實體功能指令區
# ==========================================
VERSION = "v1.1.0 (Render 搬家紀念版)"

@bot.command(name="v", aliases=["version"])
async def show_version(ctx):
    """顯示小水獺的目前版本號"""
    if not check_user(ctx): return
    await ctx.send(f"🦦 報告！小水獺目前的版本是：`{VERSION}`")

@bot.command(name="pwd")
async def pwd(ctx):
    """查看小水獺目前所在的資料夾路徑"""
    if not check_user(ctx): return
    await ctx.send(f"🦦 目前身在專案目錄：`{current_work_dir}`")

@bot.command(name="cd")
async def cd(ctx, *, folder: str):
    """切換小水獺的目前工作目錄"""
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
            await ctx.send("⚠️ 未能取得網址，請確認伺服器有在跑。")
    except asyncio.TimeoutError:
        await ctx.send("⚠️ 挖隧道超時了。")

@bot.command(name="stop")
async def stop(ctx):
    """緊急煞車按鈕，兼任關閉 Session"""
    global tunnel_process, active_processes, active_agent_mode
    if not check_user(ctx): return
    
    stopped_anything = False
    if tunnel_process and tunnel_process.returncode is None:
        tunnel_process.terminate()
        tunnel_process = None
        await ctx.send("🛑 已關閉 Cloudflare Tunnel。")
        stopped_anything = True
        
    for pid, proc in list(active_processes.items()):
        if proc.returncode is None:
            try:
                proc.terminate()
            except Exception: pass
            stopped_anything = True
    active_processes.clear()
            
    if active_agent_mode:
        active_agent_mode = False
        await ctx.send("🛑 已關閉長期 Agent Session (對話轉回 Flash)。")
        stopped_anything = True
            
    if not stopped_anything:
        await ctx.send("🦦 報告 Miffy，目前沒有正在執行的任務喔！")

@bot.command(name="run")
async def run(ctx, *, prompt: str = ""):
    """執行單次目標 (一次性的 Antigravity)"""
    global current_work_dir, active_processes
    if not check_user(ctx): return

    if not prompt.strip():
        await ctx.send("⚠️ 請告訴我要讓 Antigravity 做什麼！")
        return

    # 傳遞環境變數強制 Python 不使用緩衝 (避免卡在 "等待輸出...")
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    env["FORCE_COLOR"] = "1"

    # 改用 create_subprocess_exec 陣列傳遞參數，完美解決遇到換行爆掉的問題
    agent_cmd = resolve_agent_cli_command()
    if not agent_cmd:
        await ctx.send("⚠️ 找不到 Antigravity CLI 指令（預設嘗試 `ag` / `agy`），請先安裝或設定 `AGENT_CLI_COMMAND`。")
        return

    process = await asyncio.create_subprocess_exec(
        agent_cmd, "--dangerously-skip-permissions", "-p", prompt,
        cwd=current_work_dir,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        env=env
    )
    
    active_processes[process.pid] = process
    
    # 呼叫 Streaming UI 助手
    await stream_to_discord(process.stdout, ctx.channel, prefix="🦦 **[任務執行中]**")
    
    await process.wait()
    if process.pid in active_processes:
        del active_processes[process.pid]

@bot.command(name="agent")
async def agent_session(ctx, *, prompt: str = ""):
    """啟動多輪互動 Session"""
    global active_agent_mode, agent_session_first_turn
    if not check_user(ctx): return

    if active_agent_mode:
        await ctx.send("🦦 Miffy，你已經有一個正在運行的 Agent Session 了哦！(要退出請輸入 `!stop`) ")
        return

    active_agent_mode = True
    agent_session_first_turn = True

    await ctx.send(
        "🦦 🧠 **[Interactive Agent Session 已啟動]** \n"
        "接下來您的任何聊天文字都會直接轉送給大腦（包含它問您的問題）！\n"
        "*(要退出請輸入 `!stop`)*"
    )
    
    # 如果一開始就有附帶訊息，直接執行第一輪
    if prompt.strip():
        bot.loop.create_task(run_agent_turn(ctx.channel, prompt))

# ==========================================
# ⚙️ 系統自我管理指令區
# ==========================================
@bot.command(name="sys")
async def sys_cmd(ctx, *, command: str):
    """強制小水獺在背景直接執行終端機系統指令"""
    if not check_user(ctx): return
    
    # 改為串流即時輸出
    proc = await asyncio.create_subprocess_shell(
        command,
        cwd=current_work_dir,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT
    )
    await stream_to_discord(proc.stdout, ctx.channel, prefix=f"🦦 `[執行]: {command}`")
    await proc.wait()

@bot.command(name="restart")
async def restart_bot(ctx):
    """幫小水獺洗澡 (重新啟動機器人)"""
    if not check_user(ctx): return
    await ctx.send("🦦 小水獺去洗個澡，馬上回來重新啟動...")
    with open("restart_channel.txt", "w") as f:
        f.write(str(ctx.channel.id))
        
    # 在 Codespaces 我們用 bash 迴圈來保護，退出就會自動重啟
    sys.exit(0)

@bot.command(name="update")
async def update_bot(ctx):
    """從 GitHub 讀取最新進度，並且自動重啟更新"""
    if not check_user(ctx): return
    await ctx.send("🦦 正在從 GitHub 學習新技能 (git pull)...")
    import subprocess
    subprocess.run(["git", "pull"], cwd=os.path.dirname(os.path.abspath(__file__)))
    await ctx.send("✅ 學習完成！重新啟動中...")
    with open("restart_channel.txt", "w") as f:
        f.write(str(ctx.channel.id))
        
    sys.exit(0)

# 啟動保持喚醒的微型伺服器
keep_alive()
bot.run(TOKEN)