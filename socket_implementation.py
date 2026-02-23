import platform

from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse

app = FastAPI()

# Simple HTML client for testing, containing basic JavaScript to connect and send messages
html = """
<!DOCTYPE html>
<html>
    <!-- HTML/JS client omitted for brevity; see documentation -->
</html>
"""

@app.get("/")
async def get():
    return HTMLResponse(html)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept() # Must accept the connection
    while True:
        data = await websocket.receive_text() # Receive
        print(f'Received: {data}')
        await websocket.send_text(f"Message received: {data}\n on {platform.system()}") # Send