import asyncio
import logging
import json
import os
from datetime import datetime, timedelta
from aiohttp import web
from twitchio.ext import commands

# === CONFIGURATION ===
TOKEN = 'oauth:l9a60th0sn3boka6u2skwct73d0njs'
CHANNEL = 'real_atzock'
TIME_PER_SUB = timedelta(minutes=3)
WEB_PORT = 8080
SAVE_FILE = 'timer_data.json'  # Datei für die Persistierung

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

# === PERSISTENCE FUNCTIONS ===
def save_timer_state():
    """Speichert den aktuellen Timer-Zustand in eine JSON-Datei."""
    try:
        current_time = datetime.now()
        
        # Berechne die effektive verbleibende Zeit
        remaining = get_remaining_time()
        
        # Berechne die aktuelle Pausenzeit falls pausiert
        current_pause_duration = timedelta(0)
        if paused and pause_start_time:
            current_pause_duration = current_time - pause_start_time
        
        data = {
            'saved_at': current_time.isoformat(),
            'end_time': end_time.isoformat(),
            'paused': paused,
            'total_pause_time_seconds': total_pause_time.total_seconds(),
            'current_pause_duration_seconds': current_pause_duration.total_seconds(),
            'pause_start_time': pause_start_time.isoformat() if pause_start_time else None,
            'remaining_time_seconds': remaining.total_seconds(),
            'version': '1.1'
        }
        
        with open(SAVE_FILE, 'w') as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"💾 Timer state saved: {format_time(remaining)} remaining {'(PAUSED)' if paused else '(RUNNING)'}")
        
    except Exception as e:
        logger.error(f"Error saving timer state: {e}")

def load_timer_state():
    """Lädt den Timer-Zustand aus der JSON-Datei."""
    global end_time, paused, total_pause_time, pause_start_time
    
    try:
        if not os.path.exists(SAVE_FILE):
            logger.info("📂 No saved timer state found, starting fresh")
            return
        
        with open(SAVE_FILE, 'r') as f:
            data = json.load(f)
        
        saved_at = datetime.fromisoformat(data['saved_at'])
        current_time = datetime.now()
        offline_duration = current_time - saved_at
        
        # Lade gespeicherte Werte
        end_time = datetime.fromisoformat(data['end_time'])
        paused = data['paused']
        total_pause_time = timedelta(seconds=data['total_pause_time_seconds'])
        pause_start_time = datetime.fromisoformat(data['pause_start_time']) if data['pause_start_time'] else None
        
        # Behandle verschiedene Versionen der Datei
        version = data.get('version', '1.0')
        
        if paused:
            if version >= '1.1' and 'current_pause_duration_seconds' in data:
                # Neue Version: Verwende die gespeicherte Pausenzeit
                saved_pause_duration = timedelta(seconds=data['current_pause_duration_seconds'])
                total_pause_time += saved_pause_duration
                logger.info(f"Added saved pause duration: {format_time(saved_pause_duration)}")
            elif pause_start_time:
                # Alte Version: Berechne die Pausenzeit bis zum Speichern
                pause_duration_before_save = saved_at - pause_start_time
                total_pause_time += pause_duration_before_save
                logger.info(f"Added pause time before save: {format_time(pause_duration_before_save)}")
            
            # Füge die komplette Offline-Zeit zur Pausenzeit hinzu (da pausiert)
            total_pause_time += offline_duration
            logger.info(f"Added offline time to pause: {format_time(offline_duration)}")
            
            # Setze die neue Pause-Startzeit auf jetzt
            pause_start_time = current_time
        else:
            # Timer war nicht pausiert, die Offline-Zeit ist normale Laufzeit
            logger.info(f"Timer was running, offline time: {format_time(offline_duration)}")
        
        remaining = get_remaining_time()
        
        logger.info(f"📤 Timer state loaded from {format_time(offline_duration)} ago")
        logger.info(f"⏱️ Current timer: {format_time(remaining)} ({'PAUSED' if paused else 'RUNNING'})")
        logger.info(f"🔄 Total pause time: {format_time(total_pause_time)}")
        
        # Informiere über den Status
        if remaining <= timedelta(0) and not paused:
            logger.info("⏰ Timer was already expired")
        
    except Exception as e:
        logger.error(f"Error loading timer state: {e}")
        logger.info("🔄 Starting with fresh timer state")

async def auto_save_timer():
    """Speichert den Timer-Zustand alle 10 Sekunden automatisch."""
    while True:
        try:
            save_timer_state()
            await asyncio.sleep(10)  # Alle 10 Sekunden speichern
        except Exception as e:
            logger.error(f"Error in auto-save: {e}")
            await asyncio.sleep(10)

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
            
            # Speichere den neuen Zustand sofort
            save_timer_state()
                
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
        save_timer_state()  # Speichere sofort

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
        save_timer_state()  # Speichere sofort

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
        save_timer_state()  # Speichere sofort

    @commands.command(name="settime")
    async def settime_cmd(self, ctx, minutes: int):
        """Setzt den Timer auf eine bestimmte Zeit (nur für Mods/Broadcaster)."""
        global end_time
        
        if not (ctx.author.is_mod or ctx.author.name.lower() == CHANNEL.lower()):
            return
            
        if minutes < 0 or minutes > 10000:
            await ctx.send("❌ Minutes must be between 0 and 10000.")
            return
            
        current_time = datetime.now()
        end_time = current_time + timedelta(minutes=minutes)
        remaining = get_remaining_time()
        await ctx.send(f"🕐 Timer set to {format_time(remaining)}")
        logger.info(f"Timer set to: {minutes} minutes")
        save_timer_state()  # Speichere sofort

    @commands.command(name="testsub")
    async def testsub_cmd(self, ctx):
        """Simuliert ein Subscription-Event (nur für Mods/Broadcaster)."""
        if not (ctx.author.is_mod or ctx.author.name.lower() == CHANNEL.lower()):
            await ctx.send("❌ Only moderators can test subscriptions.")
            return
        
        global end_time
        try:
            subscriber = ctx.author.name
            logger.info(f"🧪 TEST: Simulating subscription from {subscriber}")

            current_time = datetime.now()
            if end_time <= current_time:
                end_time = current_time + TIME_PER_SUB
                logger.info(f"Timer started: {TIME_PER_SUB} added")
            else:
                end_time += TIME_PER_SUB
                remaining = get_remaining_time()
                logger.info(f"Time added: {TIME_PER_SUB}, remaining: {format_time(remaining)}")
            
            remaining = get_remaining_time()
            await ctx.send(f"🧪 TEST SUB: Added {TIME_PER_SUB} to timer! Remaining: {format_time(remaining)}")
            save_timer_state()  # Speichere sofort
            
        except Exception as e:
            logger.error(f"Error in test subscription: {e}")
            await ctx.send("❌ Error simulating subscription.")

    @commands.command(name="savetimer")
    async def savetimer_cmd(self, ctx):
        """Speichert den Timer-Zustand manuell (nur für Mods/Broadcaster)."""
        if not (ctx.author.is_mod or ctx.author.name.lower() == CHANNEL.lower()):
            return
        
        save_timer_state()
        remaining = get_remaining_time()
        await ctx.send(f"💾 Timer state saved! Current: {format_time(remaining)}")

    async def event_message(self, message):
        """Behandelt alle Chat-Nachrichten."""
        if message.echo:
            return
        await self.handle_commands(message)

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

async def shutdown_handler():
    """Behandelt das ordnungsgemäße Herunterfahren."""
    logger.info("🛑 Shutting down, saving timer state...")
    save_timer_state()
    logger.info("💾 Timer state saved on shutdown")

async def main():
    """Hauptfunktion - startet alle Komponenten."""
    # Validiere Konfiguration
    if TOKEN == 'oauth:your_oauth_token_here' or CHANNEL == 'your_channel_name_here':
        logger.error("❌ Please configure TOKEN and CHANNEL in the script!")
        return

    # Lade gespeicherten Timer-Zustand
    load_timer_state()
    
    # Starte Web-Server
    await setup_webserver()
    
    # Starte Background-Tasks
    asyncio.create_task(notify_clients())
    asyncio.create_task(auto_save_timer())  # Auto-Save alle 10 Sekunden

    # Starte Bot
    bot = Bot()
    logger.info("🤖 Starting Twitch bot...")
    
    try:
        await bot.start()
    except Exception as e:
        logger.error(f"Bot error: {e}")
        await shutdown_handler()
        raise

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Shutting down...")
        # save_timer_state() wird durch shutdown_handler() aufgerufen
    except Exception as e:
        logger.error(f"Application error: {e}")
        save_timer_state()  # Letzte Rettung
        import traceback
        traceback.print_exc()