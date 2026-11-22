#!/usr/bin/env python3
"""Ponte do SinaisTredBot com a IQ Option (servidor MCP local, SOMENTE LEITURA).

O app web não consegue chamar a iqoptionapi direto. Este servidor roda no seu
computador, lê os candles da IQ Option e entrega ao app, que está aberto no app
Claude do computador. Ele NÃO envia ordens e não mexe no saldo: só existem as
ferramentas `get_candles` e `status`.

Requisitos:  pip install mcp iqoptionapi
Credenciais: variáveis IQ_EMAIL e IQ_SENHA (veja o LEIA-ME.md).
Teste sem login: IQ_SIMULADO=1 (candles aleatórios em tempo real).

Ferramenta educacional, não é recomendação de investimento.
"""
import os
import sys
import threading
import time

try:  # mcp 2.x
    from mcp.server.mcpserver import MCPServer as _Servidor
except ImportError:  # mcp 1.x
    from mcp.server.fastmcp import FastMCP as _Servidor
from mcp.types import ToolAnnotations

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sinais_iq import Simulador, base_simulada, tick_do_ativo  # noqa: E402

SIMULADO = os.environ.get("IQ_SIMULADO") == "1"
_trava = threading.Lock()
_api = None
_sims = {}


def _log(*a):
    print(*a, file=sys.stderr, flush=True)  # stdout é reservado ao protocolo MCP


def _somente_leitura():
    try:
        return ToolAnnotations(readOnlyHint=True)
    except Exception:
        return ToolAnnotations(read_only_hint=True)


mcp = _Servidor("iqoption")


def _conectar():
    global _api
    if _api is not None:
        try:
            if _api.check_connect():
                return _api
        except Exception:
            pass
        _api = None
    try:
        from iqoptionapi.stable_api import IQ_Option
    except ImportError:
        raise RuntimeError("A biblioteca iqoptionapi não está instalada (pip install iqoptionapi).")
    email, senha = os.environ.get("IQ_EMAIL"), os.environ.get("IQ_SENHA")
    if not email or not senha:
        raise RuntimeError("Defina IQ_EMAIL e IQ_SENHA no 'env' da configuração do servidor.")
    api = IQ_Option(email, senha)
    ok, motivo = api.connect()
    if not ok:
        raise RuntimeError(f"Falha na conexão com a IQ Option: {motivo}")
    _log("Conectado à IQ Option (somente leitura).")
    _api = api
    return api


def _candles_reais(api, nome, tempo_s, quantidade, agora):
    bruto = api.get_candles(nome, tempo_s, quantidade, agora) or []
    C = [{"t": int(r["from"]), "o": r["open"], "h": r["max"], "l": r["min"], "c": r["close"]}
         for r in sorted(bruto, key=lambda r: r["from"]) if r["from"] + tempo_s <= agora]  # só candles fechados
    if not C:
        raise RuntimeError("sem candles (ativo fechado? no fim de semana tente o -OTC)")
    return C


def _candles_simulados(nome, tempo_s, quantidade, agora):
    chave = (nome, tempo_s)
    if chave not in _sims:
        tick = tick_do_ativo(nome)
        semente = sum(ord(c) * (i + 1) for i, c in enumerate(nome))
        sim = Simulador(tempo_s, tick, seed=semente, base=base_simulada(nome))
        _sims[chave] = {"sim": sim, "hist": [sim.proximo() for _ in range(300)]}
    st = _sims[chave]
    while st["sim"].t + tempo_s <= agora:
        st["hist"].append(st["sim"].proximo())
    del st["hist"][:-1500]
    return st["hist"][-quantidade:]


@mcp.tool(annotations=_somente_leitura())
def get_candles(ativos: list[str], tempo_s: int = 60, quantidade: int = 120) -> dict:
    """Devolve os candles FECHADOS de cada ativo (mais antigos primeiro).

    ativos: códigos da IQ Option, ex.: ["EURUSD", "GBPUSD-OTC"] (no máximo 12).
    tempo_s: tamanho do candle em segundos (60 = 1 minuto, 300 = 5 minutos).
    quantidade: quantos candles por ativo (5 a 1000).
    Retorno: {"agora": epoch, "tempo_s": n, "ativos": {"EURUSD": [{"t","o","h","l","c"}]}, "erros": {...}}
    ou {"erro": "mensagem"} se não deu para conectar.
    O campo t é o início do candle em segundos desde 1970.
    """
    tempo_s = max(1, min(int(tempo_s), 86400))
    quantidade = max(5, min(int(quantidade), 1000))
    nomes = []
    for a in ativos or []:
        a = str(a).strip().upper()[:20]
        if a and a not in nomes:
            nomes.append(a)
    nomes = nomes[:12]
    if not nomes:
        return {"erro": "Informe ao menos um ativo."}
    agora = time.time()
    saida, erros = {}, {}
    with _trava:
        try:
            api = None if SIMULADO else _conectar()
        except Exception as e:  # devolvido como dado, para o app mostrar a mensagem
            return {"erro": str(e)[:300]}
        for nome in nomes:
            try:
                saida[nome] = (_candles_simulados(nome, tempo_s, quantidade, agora) if SIMULADO
                               else _candles_reais(api, nome, tempo_s, quantidade, agora))
            except Exception as e:  # um ativo ruim não derruba os outros
                erros[nome] = str(e)[:200]
    return {"agora": int(agora), "tempo_s": tempo_s, "ativos": saida, "erros": erros}


@mcp.tool(annotations=_somente_leitura())
def status() -> dict:
    """Diz se a ponte está no modo real ou simulado e se já há conexão com a IQ Option."""
    conectado = False
    if _api is not None:
        try:
            conectado = bool(_api.check_connect())
        except Exception:
            conectado = False
    return {"modo": "simulado" if SIMULADO else "real", "conectado": conectado or SIMULADO}


if __name__ == "__main__":
    mcp.run()
