from pathlib import Path
import json
import struct
import zlib

frontend = Path("frontend")
public = frontend / "public"
icons = public / "icons"
icons.mkdir(parents=True, exist_ok=True)

manifest = {
    "name": "SinaisTredBot",
    "short_name": "SinaisTredBot",
    "description": "Painel educacional de sinais em modo demonstrativo.",
    "lang": "pt-BR",
    "start_url": ".",
    "scope": ".",
    "display": "standalone",
    "background_color": "#071827",
    "theme_color": "#071827",
    "orientation": "portrait-primary",
    "icons": [
        {
            "src": "icons/icon-192.png",
            "sizes": "192x192",
            "type": "image/png",
            "purpose": "any maskable"
        },
        {
            "src": "icons/icon-512.png",
            "sizes": "512x512",
            "type": "image/png",
            "purpose": "any maskable"
        }
    ]
}

(public / "manifest.webmanifest").write_text(
    json.dumps(manifest, ensure_ascii=False, indent=2),
    encoding="utf-8"
)

(public / "sw.js").write_text(
"""const CACHE = 'sinaistredbot-pwa-v1';

self.addEventListener('install', () => self.skipWaiting());

self.addEventListener('activate', (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener('fetch', (event) => {
  const request = event.request;
  const url = new URL(request.url);

  if (request.method !== 'GET' || url.origin !== self.location.origin) return;

  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request)
        .then((response) => {
          const copy = response.clone();
          caches.open(CACHE).then((cache) => cache.put(request, copy));
          return response;
        })
        .catch(() => caches.match(request))
    );
    return;
  }

  event.respondWith(
    caches.match(request).then((cached) => {
      if (cached) return cached;

      return fetch(request).then((response) => {
        const copy = response.clone();
        caches.open(CACHE).then((cache) => cache.put(request, copy));
        return response;
      });
    })
  );
});
""",
    encoding="utf-8"
)

(frontend / "src" / "pwa.ts").write_text(
"""if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker
      .register(`${import.meta.env.BASE_URL}sw.js`)
      .catch((error) => console.warn('PWA indisponível:', error));
  });
}
""",
    encoding="utf-8"
)

main = frontend / "src" / "main.tsx"
main_text = main.read_text(encoding="utf-8-sig")
if "import './pwa'" not in main_text:
    main.write_text("import './pwa'\n" + main_text, encoding="utf-8")

index = frontend / "index.html"
index_text = index.read_text(encoding="utf-8-sig")
if "manifest.webmanifest" not in index_text:
    tags = """  <meta name=\\"theme-color\\" content=\\"#071827\\" />
  <meta name=\\"mobile-web-app-capable\\" content=\\"yes\\" />
  <meta name=\\"apple-mobile-web-app-capable\\" content=\\"yes\\" />
  <meta name=\\"apple-mobile-web-app-status-bar-style\\" content=\\"black-translucent\\" />
  <link rel=\\"manifest\\" href=\\"%BASE_URL%manifest.webmanifest\\" />
  <link rel=\\"apple-touch-icon\\" href=\\"%BASE_URL%icons/icon-192.png\\" />
"""
    index_text = index_text.replace("</head>", tags + "</head>")

if "<html lang=" in index_text:
    import re
    index_text = re.sub(r'<html lang="[^"]*">', '<html lang="pt-BR">', index_text)

index.write_text(index_text, encoding="utf-8")

def make_icon(size, output):
    pixels = bytearray(size * size * 4)

    def put(x, y, color):
        if 0 <= x < size and 0 <= y < size:
            pos = (y * size + x) * 4
            pixels[pos:pos + 4] = bytes(color)

    for y in range(size):
        shade = int(16 + (y / size) * 18)
        for x in range(size):
            put(x, y, (4, shade, 35 + int(x / size * 24), 255))

    def rect(x0, y0, x1, y1, color):
        for y in range(max(0, y0), min(size, y1)):
            for x in range(max(0, x0), min(size, x1)):
                put(x, y, color)

    def line(x, y0, y1, color, width):
        rect(x - width // 2, y0, x + (width + 1) // 2, y1, color)

    cyan = (34, 211, 238, 255)
    green = (16, 230, 137, 255)
    red = (255, 88, 103, 255)
    white = (235, 246, 255, 255)

    margin = size // 10
    rect(margin, margin, size - margin, size - margin, (7, 32, 55, 255))
    rect(margin + size // 30, margin + size // 30, size - margin - size // 30, size - margin - size // 30, (6, 25, 45, 255))

    line(size * 30 // 100, size * 24 // 100, size * 69 // 100, red, size // 42)
    rect(size * 24 // 100, size * 38 // 100, size * 36 // 100, size * 57 // 100, red)

    line(size * 50 // 100, size * 19 // 100, size * 63 // 100, green, size // 42)
    rect(size * 44 // 100, size * 27 // 100, size * 56 // 100, size * 48 // 100, green)

    line(size * 70 // 100, size * 13 // 100, size * 56 // 100, cyan, size // 42)
    rect(size * 64 // 100, size * 21 // 100, size * 76 // 100, size * 40 // 100, cyan)

    rect(size * 24 // 100, size * 70 // 100, size * 76 // 100, size * 74 // 100, white)
    rect(size * 32 // 100, size * 78 // 100, size * 68 // 100, size * 82 // 100, cyan)

    raw = b''.join(
        b'\\x00' + pixels[y * size * 4:(y + 1) * size * 4]
        for y in range(size)
    )

    def chunk(tag, data):
        return (
            struct.pack("!I", len(data))
            + tag
            + data
            + struct.pack("!I", zlib.crc32(tag + data) & 0xffffffff)
        )

    png = (
        b"\\x89PNG\\r\\n\\x1a\\n"
        + chunk(b"IHDR", struct.pack("!IIBBBBB", size, size, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )
    output.write_bytes(png)

make_icon(192, icons / "icon-192.png")
make_icon(512, icons / "icon-512.png")

print("PWA criado com sucesso.")

