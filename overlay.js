const timer = document.getElementById("timer");
const pausedBanner = document.getElementById("paused");

const socket = new WebSocket("ws://localhost:8080/ws");

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
