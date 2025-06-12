import asyncio
import logging
from aiohttp import web
from twitchio.ext import commands
from datetime import datetime, timedelta

# === CONFIGURATION ===
TOKEN = 'oauth:your_oauth_token_here'  # Get from https://twitchapps.com/tmi/
CHANNEL = 'your_channel_name_here'      # Your Twitch username (lowercase)
TIME_PER_SUB = timedelta(minutes=1)     # Time added per subscription
WEB_PORT = 8080

# === GLOBALS ===
end_time = datetime.now()
clients = []
paused = False
total_pause_time = timedelta(0)
pause_start_time = None

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_remaining_time():
    """Calculate remaining time accounting for pauses"""
    global end_time, paused, total_pause_time, pause_start_time
    
    current_time = datetime.now()
    
    if paused and pause_start_time:
        # If paused, calculate as if time stopped when pause began
        effective_current_time = pause_start_time
        remaining = end_time - effective_current_time - total_pause_time
    else:
        # Normal operation, subtract total pause time
        remaining = end_time - current_time - total_pause_time
    
    return max(remaining, timedelta(0))

def format_time(td):
    """Format timedelta as HH:MM:SS"""
    total_seconds = int(td.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

# === WebSocket for OBS Overlay ===
async def websocket_handler(request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    clients.append(ws)
    logger.info("New WebSocket client connected")

    try:
        async for msg in ws:
            if msg.type == web.WSMsgType.ERROR:
                logger.error(f'WebSocket error: {ws.exception()}')
                break
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        if ws in clients:
            clients.remove(ws)
        logger.info("WebSocket client disconnected")
    
    return ws

async def notify_clients():
    """Send timer updates to all connected WebSocket clients"""
    while True:
        try:
            remaining = get_remaining_time()
            formatted_time = format_time(remaining)
            
            if paused:
                msg = f"PAUSED {formatted_time}"
            else:
                msg = formatted_time

            # Send to all connected clients
            disconnected_clients = []
            for ws in clients[:]:  # Create a copy to iterate safely
                try:
                    await ws.send_str(msg)
                except Exception as e:
                    logger.warning(f"Failed to send to client: {e}")
                    disconnected_clients.append(ws)
            
            # Remove disconnected clients
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
        logger.info(f"✅ Connected to Twitch as {self.nick}")
        logger.info(f"📺 Monitoring channel: {CHANNEL}")
        # Start the client notification task
        asyncio.create_task(notify_clients())

    async def event_usernotice_subscription(self, metadata):
        """Handle new subscriptions"""
        global end_time
        
        try:
            subscriber = metadata.user.name if metadata.user else "Unknown"
            logger.info(f"🎉 New subscription from {subscriber}!")
            
            current_time = datetime.now()
            
            if end_time <= current_time:
                # Timer expired or not started, set new end time
                end_time = current_time + TIME_PER_SUB
                logger.info(f"Timer started: {TIME_PER_SUB} added")
            else:
                # Timer running, add time
                end_time += TIME_PER_SUB
                remaining = get_remaining_time()
                logger.info(f"Time added: {TIME_PER_SUB}, remaining: {format_time(remaining)}")
                
        except Exception as e:
            logger.error(f"Error handling subscription: {e}")

    @commands.command(name="pause")
    async def pause_cmd(self, ctx):
        """Pause the timer (mod/broadcaster only)"""
        global paused, pause_start_time
        
        # Check permissions
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
        """Resume the timer (mod/broadcaster only)"""
        global paused, total_pause_time, pause_start_time
        
        # Check permissions
        if not (ctx.author.is_mod or ctx.author.name.lower() == CHANNEL.lower()):
            await ctx.send("❌ Only moderators can resume the timer.")
            return
        
        if not paused:
            await ctx.send("▶️ Timer is not paused.")
            return
            
        if pause_start_time:
            # Add the pause duration to total pause time
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
        """Show current timer status"""
        remaining = get_remaining_time()
        status = "PAUSED" if paused else "RUNNING"
        await ctx.send(f"⏱️ Timer: {format_time(remaining)} ({status})")

    @commands.command(name="addtime")
    async def addtime_cmd(self, ctx, minutes: int = 1):
        """Add time to timer (mod/broadcaster only)"""
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

# === Error Handler ===
async def handle_errors():
    """Global error handler"""
    try:
        while True:
            await asyncio.sleep(60)  # Check every minute
            if not clients:
                logger.warning("No WebSocket clients connected")
    except Exception as e:
        logger.error(f"Error handler exception: {e}")

# === Start Web Server + Bot ===
async def main():
    try:
        # Validate configuration
        if TOKEN == 'oauth:your_oauth_token_here' or CHANNEL == 'your_channel_name_here':
            logger.error("❌ Please configure TOKEN and CHANNEL in the script!")
            return
        
        # Setup web server
        app = web.Application()
        app.router.add_get("/ws", websocket_handler)
        app.router.add_static("/", "./")
        
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, 'localhost', WEB_PORT)
        await site.start()
        
        logger.info(f"🌐 Web server started on http://localhost:{WEB_PORT}")
        logger.info("📁 Overlay available at: overlay.html")
        
        # Start error handler
        asyncio.create_task(handle_errors())
        
        # Start bot
        bot = Bot()
        logger.info("🤖 Starting Twitch bot...")
        await bot.run()
        
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        raise

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Shutting down...")
    except Exception as e:
        logger.error(f"Application error: {e}")