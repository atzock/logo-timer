# Logo Timer

A Twitch subscription timer with OBS overlay integration. Adds time to a countdown timer whenever someone subscribes to your channel.

## Features

- ⏱️ **Automatic Timer**: Adds configurable time for each new subscription
- ⏸️ **Pause/Resume**: Mods and broadcaster can pause/resume the timer
- 🖥️ **OBS Overlay**: Real-time display for your stream
- 🔄 **Auto-Reconnect**: Overlay automatically reconnects if connection drops
- 📊 **Multiple Commands**: Timer status, manual time addition, and more
- 🛡️ **Permission System**: Only mods/broadcaster can control timer

## Commands

- `!pause` - Pause the timer (mods/broadcaster only)
- `!resume` - Resume the timer (mods/broadcaster only) 
- `!timer` - Show current timer status (anyone)
- `!addtime [minutes]` - Add time manually (mods/broadcaster only)

## Setup

### 1. Install Dependencies
```bash
pip install aiohttp twitchio
```

### 2. Get Twitch OAuth Token
1. Visit https://twitchtokengenerator.com/
2. Click "Connect" and authorize the application
3. Copy the OAuth token (starts with `oauth:`)

### 3. Configure Settings
Edit `sub-timer.py` and update these lines:
```python
TOKEN = 'oauth:your_token_here'      # Your OAuth token
CHANNEL = 'your_username'            # Your Twitch username (lowercase)
TIME_PER_SUB = timedelta(minutes=1)  # Time added per sub
```

### 4. Run the Timer
```bash
python sub-timer.py
```

### 5. Add OBS Overlay
1. In OBS, add a new **Browser Source**
2. Set URL to: `http://localhost:8080/overlay.html`
3. Set Width: 800, Height: 200
4. Check "Refresh browser when scene becomes active"

## Customization

### Timer Display
Edit `overlay.css` to customize:
- Font size, color, and family
- Text shadows and effects
- Pause indicator styling
- Animation timing

### Time Per Subscription
Change `TIME_PER_SUB` in `sub-timer.py`:
```python
TIME_PER_SUB = timedelta(minutes=2)  # 2 minutes per sub
TIME_PER_SUB = timedelta(seconds=30) # 30 seconds per sub
```

### Web Server Port
Change `WEB_PORT` if port 8080 is in use:
```python
WEB_PORT = 8081  # Use different port
```

## Troubleshooting

### "Connection Lost" in Overlay
- Make sure `sub-timer.py` is running
- Check if port 8080 is available
- Try refreshing the browser source in OBS

### Bot Not Responding to Commands
- Verify your OAuth token is correct
- Check that the channel name matches your Twitch username
- Ensure the bot account has necessary permissions

### No Subscription Events
- Make sure you're testing with actual subscriptions
- Check the console output for connection status
- Verify the channel name is spelled correctly

## File Structure
```
ogol-timer/
├── sub-timer.py     # Main application
├── overlay.html     # OBS overlay page
├── overlay.css      # Overlay styling
├── overlay.js       # Overlay JavaScript
├── README.md        # This file
└── LICENSE          # MIT License
```

## License

MIT License - see LICENSE file for details.