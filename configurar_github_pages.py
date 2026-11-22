from pathlib import Path
import re

root = Path(".")
app = root / "frontend" / "src" / "App.tsx"
text = app.read_text(encoding="utf-8-sig")

novo_api = "const API = (import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000').replace(/\\/$/, '');"
text, total = re.subn(
    r"const\s+API\s*=\s*[^;\r\n]+;?",
    novo_api,
    text,
    count=1,
)

if total != 1:
    raise SystemExit("Não encontrei a linha const API em frontend/src/App.tsx. Não alterei o arquivo.")

text = re.sub(
    r"""new\s+WebSocket\(\s*['"]ws://127\.0\.0\.1:8000/ws['"]\s*\)""",
    "new WebSocket(`${API.replace(/^http/, 'ws')}/ws`)",
    text,
)

app.write_text(text, encoding="utf-8")

(root / "frontend" / ".env.production").write_text(
    "VITE_API_URL=https://sinais-trade-bot.onrender.com\n",
    encoding="utf-8",
)

(root / "frontend" / "vite.config.ts").write_text(
"""import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(({ command }) => ({
  base: command == 'build' ? '/sinais-trade-bot/' : '/',
  plugins: [react()],
}))
""",
    encoding="utf-8",
)

workflow = root / ".github" / "workflows" / "deploy-pages.yml"
workflow.parent.mkdir(parents=True, exist_ok=True)
workflow.write_text(
"""name: Publicar painel no GitHub Pages

on:
  push:
    branches: [main]
  workflow_dispatch:

permissions:
  contents: read
  pages: write
  id-token: write

concurrency:
  group: github-pages
  cancel-in-progress: false

jobs:
  deploy:
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    runs-on: ubuntu-latest
    steps:
      - name: Baixar codigo
        uses: actions/checkout@v6

      - name: Configurar Node
        uses: actions/setup-node@v6
        with:
          node-version: 22
          cache: npm
          cache-dependency-path: frontend/package-lock.json

      - name: Instalar frontend
        working-directory: frontend
        run: npm ci

      - name: Gerar painel
        working-directory: frontend
        run: npm run build

      - name: Preparar GitHub Pages
        uses: actions/configure-pages@v5

      - name: Enviar painel
        uses: actions/upload-pages-artifact@v4
        with:
          path: frontend/dist

      - name: Publicar painel
        id: deployment
        uses: actions/deploy-pages@v4
""",
    encoding="utf-8",
)

print("Configuracao de producao criada.")
