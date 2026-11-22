from pathlib import Path

arquivo = Path("sinais_iq.py")
texto = arquivo.read_text(encoding="utf-8")

if "janela_enviada" in texto:
    print("A regra de janela de 30 segundos já foi aplicada.")
    raise SystemExit(0)

Path("sinais_iq.antes_janela.py").write_text(texto, encoding="utf-8")

estado_antigo = '"arquivo": arquivo, "recentes": []}'
estado_novo = '"arquivo": arquivo, "recentes": [], "pendente": None, "janela_enviada": 0}'

if estado_antigo not in texto:
    raise RuntimeError("Não encontrei a estrutura de estado esperada.")

texto = texto.replace(estado_antigo, estado_novo, 1)

inicio = '                    if s and s["lado"] != "atencao" and s["forca"] >= args.min_forca:'
fim = '                    elif not args.so_sinais:'

pos_inicio = texto.find(inicio)
pos_fim = texto.find(fim, pos_inicio)

if pos_inicio == -1 or pos_fim == -1:
    raise RuntimeError("Não encontrei o bloco de sinais esperado.")

novo_bloco = '''                    if s and s["lado"] != "atencao" and s["forca"] >= args.min_forca:
                        # Guarda o melhor sinal e espera a janela de 30 segundos.
                        # Não envia imediatamente para não gerar vários alertas seguidos.
                        e["pendente"] = s.copy()
'''

texto = texto[:pos_inicio] + novo_bloco + texto[pos_fim:]

marcador = '''                if novos:
                    for t in sorted(e["hist"])[:-2000]:'''

janela = '''                # Janela organizada: avisa aproximadamente 30 segundos
                # antes da próxima abertura de candle M1.
                agora_real = time.time()
                proxima_abertura = (int(agora_real // tam) + 1) * tam
                faltam_segundos = proxima_abertura - agora_real

                if (
                    25 <= faltam_segundos <= 35
                    and e["pendente"] is not None
                    and e["janela_enviada"] != proxima_abertura
                ):
                    sinal_confirmado = e["pendente"].copy()

                    # Horário exibido é o relógio real, não o relógio acelerado
                    # do simulador. Entrada = próxima abertura exata.
                    sinal_confirmado["t"] = int(proxima_abertura - tam)
                    sinal_confirmado["simulado"] = bool(args.simulado)

                    avisar(sinal_confirmado, nome, args.tempo, e["dec"])
                    publicar_sinal(
                        args.dashboard_url.rstrip("/"),
                        sinal_confirmado,
                        nome,
                        args.tempo,
                    )

                    e["recentes"].append({
                        "quando": time.time(),
                        "lado": sinal_confirmado["lado"],
                        "nome": sinal_confirmado["nome"],
                        "abre": proxima_abertura,
                    })

                    e["pendente"] = None
                    e["janela_enviada"] = proxima_abertura

                if novos:
                    for t in sorted(e["hist"])[:-2000]:'''

if marcador not in texto:
    raise RuntimeError("Não encontrei o ponto para inserir a janela de tempo.")

texto = texto.replace(marcador, janela, 1)

arquivo.write_text(texto, encoding="utf-8")
print("OK: janela de 30 segundos aplicada.")
print("Backup criado: sinais_iq.antes_janela.py")
