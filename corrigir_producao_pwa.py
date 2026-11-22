from pathlib import Path
import re
import struct
import zlib

API_URL = "https://sinais-trade-bot.onrender.com"
root = Path(".")
frontend = root / "frontend"
icons = frontend / "public" / "icons"
icons.mkdir(parents=True, exist_ok=True)

# Força o frontend publicado a usar sempre a API do Render.
app = frontend / "src" / "App.tsx"
texto = app.read_text(encoding="utf-8-sig")
texto, alteracoes = re.subn(
    r"const\s+API\s*=\s*[^;\r\n]+;?",
    f"const API = '{API_URL}';",
    texto,
    count=1,
)

if alteracoes != 1:
    raise SystemExit("Não encontrei a constante API em frontend/src/App.tsx.")

texto = re.sub(
    r"""new\s+WebSocket\(\s*['"]ws://127\.0\.0\.1:8000/ws['"]\s*\)""",
    f"new WebSocket('wss://sinais-trade-bot.onrender.com/ws')",
    texto,
)
app.write_text(texto, encoding="utf-8")

# Libera o GitHub Pages para consultar a API pública.
server = root / "dashboard_server.py"
server_texto = server.read_text(encoding="utf-8-sig")
server_texto, cors_alterado = re.subn(
    r"allow_origins\s*=\s*\[[^\]]*\]",
    'allow_origins=["*"]',
    server_texto,
    count=1,
    flags=re.DOTALL,
)
server_texto = re.sub(
    r"allow_credentials\s*=\s*True",
    "allow_credentials=False",
    server_texto,
)
server.write_text(server_texto, encoding="utf-8")
print(f"CORS ajustado: {bool(cors_alterado)}")

# Atualiza o cache do PWA para o navegador baixar a nova versão.
sw = frontend / "public" / "sw.js"
sw_texto = sw.read_text(encoding="utf-8-sig")
sw_texto = re.sub(r"sinaistredbot-pwa-v\d+", "sinaistredbot-pwa-v3", sw_texto)
sw.write_text(sw_texto, encoding="utf-8")

# Cria PNGs válidos com a marca SinaisTredBot.
def criar_icone(tamanho, destino):
    pixels = bytearray(tamanho * tamanho * 4)

    def pixel(x, y, cor):
        if 0 <= x < tamanho and 0 <= y < tamanho:
            p = (y * tamanho + x) * 4
            pixels[p:p + 4] = bytes(cor)

    def retangulo(x0, y0, x1, y1, cor):
        for y in range(max(0, y0), min(tamanho, y1)):
            for x in range(max(0, x0), min(tamanho, x1)):
                pixel(x, y, cor)

    for y in range(tamanho):
        for x in range(tamanho):
            azul = 35 + int((x + y) / (tamanho * 2) * 35)
            pixel(x, y, (4, 19, azul, 255))

    margem = tamanho // 12
    retangulo(margem, margem, tamanho - margem, tamanho - margem, (7, 40, 66, 255))
    retangulo(margem * 2, margem * 2, tamanho - margem * 2, tamanho - margem * 2, (5, 27, 48, 255))

    vermelho = (255, 82, 105, 255)
    verde = (18, 230, 135, 255)
    ciano = (21, 216, 235, 255)
    branco = (239, 249, 255, 255)

    # Três candles de gráfico.
    retangulo(tamanho * 22 // 100, tamanho * 30 // 100, tamanho * 34 // 100, tamanho * 58 // 100, vermelho)
    retangulo(tamanho * 27 // 100, tamanho * 20 // 100, tamanho * 29 // 100, tamanho * 70 // 100, vermelho)

    retangulo(tamanho * 44 // 100, tamanho * 24 // 100, tamanho * 56 // 100, tamanho * 50 // 100, verde)
    retangulo(tamanho * 49 // 100, tamanho * 14 // 100, tamanho * 51 // 100, tamanho * 63 // 100, verde)

    retangulo(tamanho * 66 // 100, tamanho * 16 // 100, tamanho * 78 // 100, tamanho * 42 // 100, ciano)
    retangulo(tamanho * 71 // 100, tamanho * 9 // 100, tamanho * 73 // 100, tamanho * 54 // 100, ciano)

    retangulo(tamanho * 24 // 100, tamanho * 73 // 100, tamanho * 76 // 100, tamanho * 77 // 100, branco)
    retangulo(tamanho * 33 // 100, tamanho * 82 // 100, tamanho * 67 // 100, tamanho * 86 // 100, ciano)

    dados = bytearray()
    largura_linha = tamanho * 4
    for y in range(tamanho):
        dados.append(0)
        inicio = y * largura_linha
        dados.extend(pixels[inicio:inicio + largura_linha])

    def bloco(tipo, conteudo):
        return (
            struct.pack("!I", len(conteudo))
            + tipo
            + conteudo
            + struct.pack("!I", zlib.crc32(tipo + conteudo) & 0xffffffff)
        )

    png = (
        bytes([137, 80, 78, 71, 13, 10, 26, 10])
        + bloco(b"IHDR", struct.pack("!IIBBBBB", tamanho, tamanho, 8, 6, 0, 0, 0))
        + bloco(b"IDAT", zlib.compress(bytes(dados), 9))
        + bloco(b"IEND", b"")
    )
    destino.write_bytes(png)

criar_icone(192, icons / "icon-192.png")
criar_icone(512, icons / "icon-512.png")

print("API, CORS, cache e icones corrigidos.")
