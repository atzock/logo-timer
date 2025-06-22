const timer = document.getElementById("timer");
const pausedBanner = document.getElementById("paused");

let socket;
let reconnectInterval;

function connectWebSocket() {
  try {
    socket = new WebSocket("ws://localhost:8080/ws");
    
    socket.onopen = () => {
      console.log("✅ Connected to timer server");
      clearInterval(reconnectInterval);
    };
    
    socket.onmessage = (event) => {
      const data = event.data;
      
      if (data.startsWith("PAUSED")) {
        pausedBanner.style.display = "block";
        timer.textContent = data.replace("PAUSED ", "");
      } else {
        pausedBanner.style.display = "none";
        timer.textContent = data;
      }
    };
    
    socket.onclose = () => {
      console.log("❌ Connection lost, attempting to reconnect...");
      timer.textContent = "00:00:00";
      pausedBanner.style.display = "none";
      attemptReconnect();
    };
    
    socket.onerror = (error) => {
      console.error("WebSocket error:", error);
    };
    
  } catch (error) {
    console.error("Failed to create WebSocket:", error);
    attemptReconnect();
  }
}

function attemptReconnect() {
  if (reconnectInterval) return;
  
  reconnectInterval = setInterval(() => {
    console.log("🔄 Attempting to reconnect...");
    connectWebSocket();
  }, 3000);
}

// Start connection
connectWebSocket();

// Handle page visibility changes
document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'visible' && 
      (!socket || socket.readyState === WebSocket.CLOSED)) {
    connectWebSocket();
  }
});