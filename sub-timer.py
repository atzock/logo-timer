import asyncio
import logging
from aiohttp import web
from twitchio.ext import commands
from datetime import datetime, timedelta

# === CONFIGURATION ===
TOKEN = 'oauth:l9a60th0sn3boka6u2skwct73d0njs'  # Achte darauf, dass das Prefix "oauth:" enthalten ist!
CHANNEL = 'real_atzock'  # Dein Twitch-Kanalname (klein geschrieben)
TIME_PER_SUB = timedelta(minutes=3)  # Zeit, die pro Sub hinzugefügt wird
WEB_PORT = 8080

# === GLOBALS ===
end_time = datetime.now()
clients = []
paused = False
total_pause_time = timedelta(0)
pause_start_time = None

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def get_remaining_time():
    """Berechnet die verbleibende Zeit unter Berücksichtigung von Pausen."""
    global end_time, paused, total_pause_time, pause_start_time
    current_time = datetime.now()
    
    if paused and pause_start_time:
        effective_current_time = pause_start_time
        remaining = end_time - effective_current_time - total_pause_time
    else:
        remaining = end_time - current_time - total_pause_time
    
    return max(remaining, timedelta(0))

def format_time(td):
    """Formatiert timedelta als HH:MM:SS."""
    total_seconds = int(td.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

# === WebSocket Handler ===
async def websocket_handler(request):
    """Behandelt WebSocket-Verbindungen für das Overlay."""
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    clients.append(ws)
    logger.info("New WebSocket client connected")

    try:
        async for msg in ws:
            if msg.type == web.WSMsgType.ERROR:
                logger.error(f'WebSocket error: {ws.exception()}')
                break
            elif msg.type == web.WSMsgType.TEXT:
                # Optional: Handle incoming messages from overlay
                pass
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        if ws in clients:
            clients.remove(ws)
        logger.info("WebSocket client disconnected")
    
    return ws

async def notify_clients():
    """Sendet regelmäßig Updates an alle verbundenen WebSocket-Clients."""
    while True:
        try:
            remaining = get_remaining_time()
            formatted_time = format_time(remaining)
            msg = f"PAUSED {formatted_time}" if paused else formatted_time

            # Entferne disconnected clients
            disconnected_clients = []
            for ws in clients[:]:
                try:
                    await ws.send_str(msg)
                except Exception as e:
                    logger.warning(f"Failed to send to client: {e}")
                    disconnected_clients.append(ws)

            # Cleanup disconnected clients
            for ws in disconnected_clients:
                if ws in clients:
                    clients.remove(ws)
                    
        except Exception as e:
            logger.error(f"Error in notify_clients: {e}")
        
        await asyncio.sleep(1)

# === Twitch Bot ===
class Bot(commands.Bot):
    def __init__(self):
        super().__init__(
            token=TOKEN,
            prefix="!",
            initial_channels=[CHANNEL]
        )

    async def event_ready(self):
        """Wird aufgerufen, wenn der Bot bereit ist."""
        logger.info(f"✅ Connected to Twitch as {self.nick}")
        logger.info(f"📺 Monitoring channel: {CHANNEL}")

    async def event_usernotice_subscription(self, metadata):
        """Behandelt neue Subscriptions."""
        global end_time
        try:
            subscriber = metadata.user.name if metadata.user else "Unknown"
            logger.info(f"🎉 New subscription from {subscriber}!")

            current_time = datetime.now()
            if end_time <= current_time:
                # Timer ist abgelaufen, starte neu
                end_time = current_time + TIME_PER_SUB
                logger.info(f"Timer started: {TIME_PER_SUB} added")
            else:
                # Timer läuft noch, füge Zeit hinzu
                end_time += TIME_PER_SUB
                remaining = get_remaining_time()
                logger.info(f"Time added: {TIME_PER_SUB}, remaining: {format_time(remaining)}")
                
        except Exception as e:
            logger.error(f"Error handling subscription: {e}")

    @commands.command(name="pause")
    async def pause_cmd(self, ctx):
        """Pausiert den Timer (nur für Mods/Broadcaster)."""
        global paused, pause_start_time
        
        if not (ctx.author.is_mod or ctx.author.name.lower() == CHANNEL.lower()):
            await ctx.send("❌ Only moderators can pause the timer.")
            return
            
        if paused:
            await ctx.send("⏸️ Timer is already paused.")
            return
            
        paused = True
        pause_start_time = datetime.now()
        remaining = get_remaining_time()
        await ctx.send(f"⏸️ Timer paused at {format_time(remaining)}")
        logger.info("Timer paused")

    @commands.command(name="resume")
    async def resume_cmd(self, ctx):
        """Setzt den Timer fort (nur für Mods/Broadcaster)."""
        global paused, total_pause_time, pause_start_time
        
        if not (ctx.author.is_mod or ctx.author.name.lower() == CHANNEL.lower()):
            await ctx.send("❌ Only moderators can resume the timer.")
            return
            
        if not paused:
            await ctx.send("▶️ Timer is not paused.")
            return
            
        if pause_start_time:
            pause_duration = datetime.now() - pause_start_time
            total_pause_time += pause_duration
            logger.info(f"Pause duration: {format_time(pause_duration)}")
            
        paused = False
        pause_start_time = None
        remaining = get_remaining_time()
        await ctx.send(f"▶️ Timer resumed with {format_time(remaining)} remaining")
        logger.info("Timer resumed")

    @commands.command(name="timer")
    async def timer_cmd(self, ctx):
        """Zeigt den aktuellen Timer-Status."""
        remaining = get_remaining_time()
        status = "PAUSED" if paused else "RUNNING"
        await ctx.send(f"⏱️ Timer: {format_time(remaining)} ({status})")

    @commands.command(name="addtime")
    async def addtime_cmd(self, ctx, minutes: int = 1):
        """Fügt manuell Zeit hinzu (nur für Mods/Broadcaster)."""
        global end_time
        
        if not (ctx.author.is_mod or ctx.author.name.lower() == CHANNEL.lower()):
            return
            
        if minutes < 1 or minutes > 60:
            await ctx.send("❌ Minutes must be between 1 and 60.")
            return
            
        time_to_add = timedelta(minutes=minutes)
        end_time += time_to_add
        remaining = get_remaining_time()
        await ctx.send(f"➕ Added {minutes} minute(s). Remaining: {format_time(remaining)}")
        logger.info(f"Manual time added: {minutes} minutes")

    @commands.command(name="settime")
    async def settime_cmd(self, ctx, minutes: int):
        """Setzt den Timer auf eine bestimmte Zeit (nur für Mods/Broadcaster)."""
        global end_time
        
        if not (ctx.author.is_mod or ctx.author.name.lower() == CHANNEL.lower()):
            return
            
        if minutes < 0 or minutes > 10000:  #Max 100 Stunden
            await ctx.send("❌ Minutes must be between 0 and 10000.")
            return
            
        current_time = datetime.now()
        end_time = current_time + timedelta(minutes=minutes)
        remaining = get_remaining_time()
        await ctx.send(f"🕐 Timer set to {format_time(remaining)}")
        logger.info(f"Timer set to: {minutes} minutes")

    async def event_message(self, message):
        """Behandelt alle Chat-Nachrichten."""
        # Ignoriere Bot-Nachrichten
        if message.echo:
            return
            
        # Verarbeite Commands
        await self.handle_commands(message)

# === Error Handler ===
async def handle_errors():
    """Überwacht Fehler und Verbindungsstatus."""
    try:
        while True:
            await asyncio.sleep(60)
            if not clients:
                logger.info("No WebSocket clients connected")
    except Exception as e:
        logger.error(f"Error handler exception: {e}")

# === Web Server Setup ===
async def setup_webserver():
    """Startet den Web-Server für das Overlay."""
    app = web.Application()
    app.router.add_get("/ws", websocket_handler)
    app.router.add_static("/", "./")

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, 'localhost', WEB_PORT)
    await site.start()

    logger.info(f"🌐 Web server started on http://localhost:{WEB_PORT}")
    logger.info("📁 Overlay available at: overlay.html")

async def main():
    """Hauptfunktion - startet alle Komponenten."""
    # Validiere Konfiguration
    if TOKEN == 'oauth:your_oauth_token_here' or CHANNEL == 'your_channel_name_here':
        logger.error("❌ Please configure TOKEN and CHANNEL in the script!")
        logger.info("💡 Get your token from: https://twitchtokengenerator.com/")
        return

    # Starte Web-Server
    await setup_webserver()
    
    # Starte Background-Tasks
    asyncio.create_task(notify_clients())
    asyncio.create_task(handle_errors())

    # Starte Bot
    bot = Bot()
    logger.info("🤖 Starting Twitch bot...")
    
    try:
        await bot.start()  # Verwende await für bessere Fehlerbehandlung
    except Exception as e:
        logger.error(f"Bot error: {e}")
        raise

# === Start Script ===
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Shutting down...")
    except Exception as e:
        logger.error(f"Application error: {e}")
        import traceback
        traceback.print_exc()