from pathlib import Path

arquivo = Path("frontend/src/App.tsx")
texto = arquivo.read_text(encoding="utf-8")

texto = texto.replace(
    "const API='http://127.0.0.1:8000'",
    "const API=''"
)

texto = texto.replace(
    "new WebSocket('ws://127.0.0.1:8000/ws')",
    "new WebSocket(`${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}/ws`)"
)

arquivo.write_text(texto, encoding="utf-8")
print("OK: frontend preparado para acesso remoto.")
