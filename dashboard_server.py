from __future__ import annotations
import csv, os, time, uuid
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

BASE = Path(__file__).resolve().parent
CSV_DIR = Path(os.getenv("CSV_DIR", BASE / "data"))
signals: deque[dict[str, Any]] = deque(maxlen=200)
clients: set[WebSocket] = set()
monitor = {"last_seen": None, "modo": "simulado", "ativos": [], "timeframe_min": 1}

class Signal(BaseModel):
    ativo: str
    direcao: str = Field(pattern="^(COMPRA|VENDA)$")
    padrao: str
    forca: int = Field(ge=1, le=3)
    timeframe_min: int
    signal_at: str
    entry_at: str
    valid_until: str
    entrada: float
    stop: float
    alvo: float
    modo: str = Field(pattern="^(simulado|iq_option_demo)$")
    resultado: str = "pendente"
    r: Optional[float] = None

class Monitor(BaseModel):
    modo: str = Field(pattern="^(simulado|iq_option_demo)$")
    ativos: list[str] = []
    timeframe_min: int = 1

app = FastAPI(title="SinaisTredBot Local")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

def conectado():
    return bool(monitor["last_seen"] and time.time() - monitor["last_seen"] < 35)

def status():
    hoje = datetime.now().date().isoformat()
    itens = list(signals)
    return {
        "connected": conectado(),
        "mode": monitor["modo"],
        "assets": monitor["ativos"],
        "timeframe_min": monitor["timeframe_min"],
        "signals_today": sum(1 for x in itens if x["received_at"].startswith(hoje)),
        "last_signal": itens[0] if itens else None,
    }

async def avisar_clientes(mensagem):
    for ws in clients.copy():
        try:
            await ws.send_json(mensagem)
        except Exception:
            clients.discard(ws)

@app.get("/health")
async def health():
    return {"ok": True, "service": "SinaisTredBot"}

@app.get("/api/status")
async def get_status():
    return status()

@app.post("/api/monitor")
async def heartbeat(payload: Monitor):
    monitor.update({
        "last_seen": time.time(),
        "modo": payload.modo,
        "ativos": payload.ativos,
        "timeframe_min": payload.timeframe_min,
    })
    await avisar_clientes({"type": "status", "data": status()})
    return {"ok": True}

@app.post("/api/signals")
async def receber_sinal(payload: Signal):
    item = payload.model_dump()
    item["id"] = str(uuid.uuid4())
    item["received_at"] = datetime.now(timezone.utc).isoformat()
    signals.appendleft(item)
    monitor["last_seen"] = time.time()
    await avisar_clientes({"type": "signal", "data": item})
    await avisar_clientes({"type": "status", "data": status()})
    return {"ok": True, "id": item["id"]}

@app.get("/api/signals")
async def listar_sinais():
    return {"items": list(signals), "total": len(signals)}

@app.get("/api/backtest")
async def backtest():
    itens = list(signals)
    alvo = sum(x["resultado"] == "alvo" for x in itens)
    stop = sum(x["resultado"] == "stop" for x in itens)
    resolvidos = alvo + stop
    return {
        "signals": len(itens),
        "targets": alvo,
        "stops": stop,
        "pending": len(itens) - resolvidos,
        "win_rate": round(alvo * 100 / resolvidos, 1) if resolvidos else None,
        "result_r": sum(float(x.get("r") or 0) for x in itens),
    }

@app.get("/api/candles/{asset}")
async def candles(asset: str):
    nome = "".join(x for x in asset.upper() if x.isalnum() or x in "_-")
    arquivos = sorted(CSV_DIR.glob(f"{nome}_*m.csv"))
    if not arquivos:
        raise HTTPException(404, "CSV não encontrado.")
    itens = []
    with arquivos[0].open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            itens.append({
                "time": row["time"],
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
            })
    return {"asset": nome, "items": itens[-200:]}

@app.websocket("/ws")
async def websocket(ws: WebSocket):
    await ws.accept()
    clients.add(ws)
    await ws.send_json({"type": "status", "data": status()})
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        clients.discard(ws)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("dashboard_server:app", host="127.0.0.1", port=8000)

