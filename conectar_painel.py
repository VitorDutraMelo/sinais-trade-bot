from pathlib import Path

arquivo = Path("sinais_iq.py")
texto = arquivo.read_text(encoding="utf-8")

def trocar(antes, depois):
    global texto
    if antes not in texto:
        raise RuntimeError("Não encontrei um trecho esperado. Não alterei o arquivo.")
    texto = texto.replace(antes, depois, 1)

if "def publicar_sinal(" not in texto:
    trocar("import argparse\n", "import argparse\nimport json\n")

    bloco = r'''

def enviar_painel(url, dados):
    """Envia evento ao painel local; falhas não param o monitor."""
    if not url:
        return
    try:
        corpo = json.dumps(dados).encode("utf-8")
        req = urllib.request.Request(
            url, data=corpo, method="POST",
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=1.5):
            pass
    except Exception:
        pass

def publicar_heartbeat(base_url, modo, ativos, tempo):
    enviar_painel(
        f"{base_url}/api/monitor",
        {"modo": modo, "ativos": ativos, "timeframe_min": tempo}
    )

def publicar_sinal(base_url, sinal, ativo, tempo):
    entrada_em = sinal["t"] + tempo * 60
    enviar_painel(f"{base_url}/api/signals", {
        "ativo": ativo,
        "direcao": "COMPRA" if sinal["lado"] == "compra" else "VENDA",
        "padrao": sinal["nome"],
        "forca": sinal["forca"],
        "timeframe_min": tempo,
        "signal_at": datetime.fromtimestamp(sinal["t"]).astimezone().isoformat(),
        "entry_at": datetime.fromtimestamp(entrada_em).astimezone().isoformat(),
        "valid_until": datetime.fromtimestamp(entrada_em + 3 * tempo * 60).astimezone().isoformat(),
        "entrada": sinal["entrada"],
        "stop": sinal["stop"],
        "alvo": sinal["alvo"],
        "modo": "simulado" if sinal.get("simulado") else "iq_option_demo",
        "resultado": "pendente",
        "r": None,
    })

'''
    trocar(
        "\ndef salvar_csv(caminho, hist):",
        bloco + "\ndef salvar_csv(caminho, hist):"
    )

    trocar(
        '    ap.add_argument("--simulado", action="store_true", help="usa candles aleatórios, sem login")',
        '''    ap.add_argument("--simulado", action="store_true", help="usa candles aleatórios, sem login")
    ap.add_argument("--dashboard-url", default="http://127.0.0.1:8000",
                    help="URL local do painel")'''
    )

    trocar(
        '    print(f"\\nMonitorando {len(estado)} ativo(s) em {args.tempo} min. Ctrl+C para parar.\\n")',
        '''    print(f"\\nMonitorando {len(estado)} ativo(s) em {args.tempo} min. Ctrl+C para parar.\\n")
    publicar_heartbeat(args.dashboard_url.rstrip("/"), "simulado" if args.simulado else "iq_option_demo", list(estado), args.tempo)'''
    )

    trocar(
        '                        avisar(s, nome, args.tempo, e["dec"])',
        '''                        s["simulado"] = bool(args.simulado)
                        avisar(s, nome, args.tempo, e["dec"])
                        publicar_sinal(args.dashboard_url.rstrip("/"), s, nome, args.tempo)'''
    )

    trocar(
        '            if args.resumo and time.time() >= prox_resumo:',
        '''            publicar_heartbeat(args.dashboard_url.rstrip("/"), "simulado" if args.simulado else "iq_option_demo", list(estado), args.tempo)
            if args.resumo and time.time() >= prox_resumo:'''
    )

    arquivo.write_text(texto, encoding="utf-8")
    print("OK: sinais_iq.py conectado ao painel.")
else:
    print("O sinais_iq.py já estava conectado.")
