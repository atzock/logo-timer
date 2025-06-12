import asyncio
from aiohttp import web
from twitchio.ext import commands
from datetime import datetime, timedelta

# === CONFIGURATION ===
TOKEN = 'oauth:your_oauth_token_here'
CHANNEL = 'your_channel_name_here'  # lowercase, no #
TIME_PER_SUB = timedelta(minutes=1)

# === GLOBALS ===
end_time = datetime.now()
clients = []

paused = False
pause_start = None
pause_duration = timedelta(0)

# === WebSocket for OBS Overlay ===
async def websocket_handler(request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    clients.append(ws)

    try:
        while True:
            await asyncio.sleep(10)
    except:
        pass
    finally:
        clients.remove(ws)
    return ws

async def notify_clients():
    global pause_duration
    while True:
        if paused:
            remaining = max(end_time - pause_start - pause_duration, timedelta(0))
            msg = "PAUSED " + str(remaining).split('.')[0]
        else:
            remaining = max(end_time - datetime.now() - pause_duration, timedelta(0))
            msg = str(remaining).split('.')[0]

        for ws in clients:
            try:
                await ws.send_str(msg)
            except:
                pass
        await asyncio.sleep(1)


# === Twitch Bot ===
class Bot(commands.Bot):
    def __init__(self):
        super().__init__(token=TOKEN, prefix="!", initial_channels=[CHANNEL])

    async def event_ready(self):
        print(f"✅ Connected as {self.nick}")
        asyncio.create_task(notify_clients())

    async def event_usernotice_subscription(self, metadata):
        global end_time
        print("🎉 New sub received!")
        if end_time < datetime.now():
            end_time = datetime.now() + TIME_PER_SUB
        else:
            end_time += TIME_PER_SUB

    @commands.command(name="pause")
    async def pause_cmd(self, ctx):
        global paused, pause_start
        if not ctx.author.is_mod and ctx.author.name.lower() != CHANNEL.lower():
            return
        if not paused:
            paused = True
            pause_start = datetime.now()
            await ctx.send("⏸️ Timer paused.")

    @commands.command(name="resume")
    async def resume_cmd(self, ctx):
        global paused, pause_duration
        if not ctx.author.is_mod and ctx.author.name.lower() != CHANNEL.lower():
            return
        if paused:
            paused = False
            pause_duration += datetime.now() - pause_start
            await ctx.send("▶️ Timer resumed.")

# === Start Web + Bot ===
async def main():
    app = web.Application()
    app.router.add_get("/ws", websocket_handler)
    app.router.add_static("/", "./")

    bot = Bot()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, 'localhost', 8080)
    await site.start()

    await bot.run()

asyncio.run(main())
