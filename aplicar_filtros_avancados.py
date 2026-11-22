from pathlib import Path

arquivo = Path("sinais_iq.py")
texto = arquivo.read_text(encoding="utf-8")

if "avaliar_reversao" in texto:
    print("Os filtros avançados já estão aplicados.")
    raise SystemExit(0)

Path("sinais_iq.antes_filtros_avancados.py").write_text(texto, encoding="utf-8")

def trocar(antes, depois):
    global texto

    if antes not in texto:
        raise RuntimeError("Não encontrei uma parte esperada. Nenhuma alteração foi concluída.")

    texto = texto.replace(antes, depois, 1)

trocar(
    "from datetime import datetime\n",
    "from datetime import datetime\nfrom filtros_avancados import avaliar_reversao\n"
)

trocar(
    '''return {"i": i, "t": k["t"], "nome": best["nome"], "lado": best["lado"], "forca": best["forca"],
            "entrada": entrada, "stop": stop, "alvo": alvo}''',
    '''return {"i": i, "t": k["t"], "nome": best["nome"], "lado": best["lado"],
            "forca": best["forca"], "alinhado": best["alinhado"],
            "entrada": entrada, "stop": stop, "alvo": alvo}'''
)

trocar(
    '    ap.add_argument("--min-forca", type=int, default=2, choices=[1, 2, 3])',
    '''    ap.add_argument("--min-forca", type=int, default=2, choices=[1, 2, 3])
    ap.add_argument("--min-confianca", type=int, default=72, choices=range(0, 101),
                    help="score mínimo 0-100 dos filtros quantitativos")'''
)

inicio = '                    if s and s["lado"] != "atencao" and s["forca"] >= args.min_forca:'
fim = '                    elif not args.so_sinais:'

pos_inicio = texto.find(inicio)
pos_fim = texto.find(fim, pos_inicio)

if pos_inicio == -1 or pos_fim == -1:
    raise RuntimeError("Não encontrei o bloco de monitoramento esperado.")

novo = '''                    if s and s["lado"] != "atencao":
                        contexto = avaliar_reversao(serie, A, len(serie) - 1, s)

                        s["confianca"] = contexto["score"]
                        s["rsi"] = contexto.get("rsi")
                        s["r2"] = contexto.get("r2")
                        s["estrategia"] = " + ".join(contexto.get("motivos", []))

                        if contexto["score"] >= 85:
                            s["forca"] = 3
                        elif contexto["score"] >= 75:
                            s["forca"] = 2
                        else:
                            s["forca"] = 1

                    if (
                        s
                        and s["lado"] != "atencao"
                        and s["forca"] >= args.min_forca
                        and s.get("confianca", 0) >= args.min_confianca
                    ):
                        e["pendente"] = s.copy()
'''

texto = texto[:pos_inicio] + novo + texto[pos_fim:]

trocar(
    '    print("\\a\\n" + "=" * 70 + "\\n" + texto + "\\n" + "=" * 70)',
    '''    if "confianca" in s:
        texto += (
            f"\\nScore matemático: {s['confianca']}/100"
            f" | RSI 14: {s.get('rsi', '—')}"
            f" | R² cúbico: {s.get('r2', '—')}"
        )

    print("\\a\\n" + "=" * 70 + "\\n" + texto + "\\n" + "=" * 70)'''
)

arquivo.write_text(texto, encoding="utf-8")
print("OK: filtros avançados aplicados.")
print("Backup criado: sinais_iq.antes_filtros_avancados.py")
