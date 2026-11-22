#!/usr/bin/env python3
"""SinaisTredBot para IQ Option: lê candles, detecta padrões de price action e avisa.

SOMENTE LEITURA. O script não envia ordens e não mexe no seu saldo.
Ferramenta educacional, não é recomendação de investimento.

Exemplos (vários ativos de uma vez, candles de 1 minuto por padrão):
  python sinais_iq.py --ativos EURUSD,GBPUSD,USDJPY --backtest
  python sinais_iq.py --ativos EURUSD-OTC,GBPUSD-OTC --tempo 1 --min-forca 3   # fim de semana
  python sinais_iq.py --ativos EURUSD,GBPUSD --so-sinais
  python sinais_iq.py --simulado            # testa sem login, com candles aleatórios

Gera um CSV por ativo (ex.: EURUSD_1m.csv) para importar no app web, que aceita vários arquivos.

Credenciais: variáveis de ambiente IQ_EMAIL e IQ_SENHA (ou o script pergunta).
Telegram (opcional): TELEGRAM_TOKEN e TELEGRAM_CHAT_ID.
"""
import argparse
import json
import csv
import getpass
import math
import os
import random
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime

# ----------------------------------------------------------------------------
# Motor de padrões (mesma lógica do app web SinaisTredBot)
# Cada candle é um dict: t (epoch em segundos), o, h, l, c
# ----------------------------------------------------------------------------


def calc_atr(C):
    tr = []
    for i, c in enumerate(C):
        p = C[i - 1]["c"] if i else c["o"]
        tr.append(max(c["h"] - c["l"], abs(c["h"] - p), abs(c["l"] - p)))
    A = []
    for i in range(len(C)):
        w = tr[max(0, i - 13): i + 1]
        A.append(sum(w) / len(w))
    return A


def trend_at(C, A, s):
    if s < 8 or not A[s] > 0:
        return 0
    d = (C[s]["c"] - C[s - 8]["c"]) / A[s]
    return -1 if d <= -2 else 1 if d >= 2 else 0


def _up(v, tk):
    return round(math.ceil(v / tk - 1e-9) * tk, 8)


def _dn(v, tk):
    return round(math.floor(v / tk + 1e-9) * tk, 8)


def detect_at(C, A, i, exigir_tendencia, tick):
    """Retorna um sinal (dict) para o candle i, ou None."""
    if i < 10:
        return None
    k, p, pp, p3 = C[i], C[i - 1], C[i - 2], C[i - 3]
    atr = A[i]
    if not atr > 0:
        return None

    def B(x): return abs(x["c"] - x["o"])
    def R(x): return x["h"] - x["l"]
    def U(x): return x["h"] - max(x["o"], x["c"])
    def L(x): return min(x["o"], x["c"]) - x["l"]
    def bu(x): return x["c"] > x["o"]
    def be(x): return x["c"] < x["o"]

    t1, t2, t3, t4 = trend_at(C, A, i - 1), trend_at(C, A, i - 2), trend_at(C, A, i - 3), trend_at(C, A, i - 4)
    out = []

    def add(nome, lado, n, alinhado, extra, so_k=False):
        out.append({"nome": nome, "lado": lado, "n": n, "alinhado": alinhado, "extra": extra, "so_k": so_k})

    rk, bk = R(k), B(k)
    if rk >= .7 * atr and bk >= .08 * rk and L(k) >= 2 * bk and U(k) <= .25 * rk:
        if t1 < 0:
            add("Martelo", "compra", 1, True, 1 if rk >= 1.3 * atr else 0)
        elif t1 > 0:
            add("Homem enforcado", "venda", 1, True, -1)
        else:
            add("Martelo", "compra", 1, False, 0)
    if rk >= .7 * atr and bk >= .08 * rk and U(k) >= 2 * bk and L(k) <= .25 * rk:
        if t1 > 0:
            add("Estrela cadente", "venda", 1, True, 1 if rk >= 1.3 * atr else 0)
        elif t1 < 0:
            add("Martelo invertido", "compra", 1, True, -1)
        else:
            add("Estrela cadente", "venda", 1, False, 0)
    if B(p) >= .2 * atr and bk > B(p):
        if be(p) and bu(k) and k["c"] >= p["o"] and k["o"] <= p["c"]:
            add("Engolfo de alta", "compra", 2, t2 < 0, 1 if bk >= 1.2 * atr else 0, True)
        if bu(p) and be(k) and k["c"] <= p["o"] and k["o"] >= p["c"]:
            add("Engolfo de baixa", "venda", 2, t2 > 0, 1 if bk >= 1.2 * atr else 0, True)
    if B(p) >= .6 * atr:
        if be(p) and bu(k) and k["o"] <= p["c"] and k["c"] > (p["o"] + p["c"]) / 2 and k["c"] < p["o"]:
            add("Linha de perfuração", "compra", 2, t2 < 0, 0)
        if bu(p) and be(k) and k["o"] >= p["c"] and k["c"] < (p["o"] + p["c"]) / 2 and k["c"] > p["o"]:
            add("Cobertura de nuvem negra", "venda", 2, t2 > 0, 0)
    if B(pp) >= .7 * atr and B(p) <= .35 * B(pp):
        if (be(pp) and bu(k) and k["c"] > (pp["o"] + pp["c"]) / 2
                and max(p["o"], p["c"]) <= pp["c"] + .05 * atr):
            add("Estrela da manhã doji" if B(p) <= .1 * R(p) else "Estrela da manhã", "compra", 3, t3 < 0, 1)
        if (bu(pp) and be(k) and k["c"] < (pp["o"] + pp["c"]) / 2
                and min(p["o"], p["c"]) >= pp["c"] - .05 * atr):
            add("Estrela da tarde", "venda", 3, t3 > 0, 1)
    if (bu(pp) and bu(p) and bu(k) and p["c"] > pp["c"] and k["c"] > p["c"]
            and pp["o"] <= p["o"] <= pp["c"] and p["o"] <= k["o"] <= p["c"]
            and B(pp) >= .5 * R(pp) and B(p) >= .5 * R(p) and B(k) >= .5 * R(k) and bk >= .3 * atr):
        add("Três soldados brancos", "compra", 3, t3 <= 0, 1)
    if (be(pp) and be(p) and be(k) and p["c"] < pp["c"] and k["c"] < p["c"]
            and pp["c"] <= p["o"] <= pp["o"] and p["c"] <= k["o"] <= p["o"]
            and B(pp) >= .5 * R(pp) and B(p) >= .5 * R(p) and B(k) >= .5 * R(k) and bk >= .3 * atr):
        ident = abs(p["o"] - pp["c"]) <= .15 * atr and abs(k["o"] - p["c"]) <= .15 * atr
        add("Três corvos idênticos" if ident else "Três corvos negros", "venda", 3, t3 >= 0, 1)
    if (be(p3) and be(pp) and be(p) and pp["c"] < p3["c"] and p["c"] < pp["c"] and pp["l"] < p3["l"]
            and p["l"] < pp["l"] and bu(k) and k["o"] <= p["c"] + .05 * atr and k["c"] > p3["o"]):
        add("Ataque das três linhas", "compra", 4, t4 < 0, 1, True)
    if (be(pp) and be(p) and be(k) and B(pp) >= .6 * atr and L(pp) >= .5 * B(pp)
            and p["h"] <= pp["h"] and p["l"] >= pp["l"] and B(p) < B(pp) and L(p) >= .25 * B(p)
            and k["h"] <= p["h"] and k["l"] >= p["l"] and B(k) < B(p) and R(k) > 0
            and U(k) <= .1 * R(k) and L(k) <= .1 * R(k)):
        add("Três estrelas do sul", "compra", 3, t3 < 0, 1)
    if p["h"] <= pp["h"] and p["l"] >= pp["l"] and R(pp) >= .8 * atr:
        if bu(k) and k["c"] > pp["h"]:
            add("Rompimento de barra interna", "compra", 3, t3 >= 0, 0)
        if be(k) and k["c"] < pp["l"]:
            add("Rompimento de barra interna", "venda", 3, t3 <= 0, 0)

    best = None
    for c in out:
        if exigir_tendencia and not c["alinhado"]:
            continue
        c["forca"] = max(1, min(3, 1 + (1 if c["alinhado"] else 0) + c["extra"]))
        if best is None or c["forca"] > best["forca"] or (c["forca"] == best["forca"] and c["n"] > best["n"]):
            best = c
    if best is None:
        if bk <= .1 * rk and rk >= .8 * atr:
            return {"i": i, "t": k["t"], "nome": "Doji (indecisão)", "lado": "atencao", "forca": 1}
        return None

    seg = [k] if best["so_k"] else C[i - best["n"] + 1: i + 1]
    min_l, max_h = min(x["l"] for x in seg), max(x["h"] for x in seg)
    if best["lado"] == "compra":
        entrada, stop = _up(k["h"] + tick, tick), _dn(min_l - tick, tick)
        risco = entrada - stop
        if risco <= 0:
            return None
        alvo = round(entrada + 2 * risco, 8)
    else:
        entrada, stop = _dn(k["l"] - tick, tick), _up(max_h + tick, tick)
        risco = stop - entrada
        if risco <= 0:
            return None
        alvo = round(entrada - 2 * risco, 8)
    return {"i": i, "t": k["t"], "nome": best["nome"], "lado": best["lado"], "forca": best["forca"],
            "entrada": entrada, "stop": stop, "alvo": alvo}


def avaliar(C, s):
    """Teste simples: entrada em até 3 candles, alvo de 2R contra stop de 1R (stop vence empate)."""
    if s["lado"] == "atencao":
        s["resultado"], s["r"] = "info", 0
        return
    compra, n = s["lado"] == "compra", len(C)
    ativ = -1
    for j in range(s["i"] + 1, min(s["i"] + 3, n - 1) + 1):
        if (C[j]["h"] >= s["entrada"]) if compra else (C[j]["l"] <= s["entrada"]):
            ativ = j
            break
    if ativ < 0:
        s["resultado"], s["r"] = ("nao_ativado" if s["i"] + 3 <= n - 1 else "pendente"), 0
        return
    for m in range(ativ, min(n, ativ + 41)):
        x = C[m]
        if compra:
            if x["l"] <= s["stop"]:
                s["resultado"], s["r"] = "stop", -1
                return
            if x["h"] >= s["alvo"]:
                s["resultado"], s["r"] = "alvo", 2
                return
        else:
            if x["h"] >= s["stop"]:
                s["resultado"], s["r"] = "stop", -1
                return
            if x["l"] <= s["alvo"]:
                s["resultado"], s["r"] = "alvo", 2
                return
    s["resultado"], s["r"] = ("sem_desfecho" if ativ + 40 < n - 1 else "aberto"), 0


def backtest(C, args, tick, nome=""):
    A = calc_atr(C)
    sinais = []
    for i in range(10, len(C)):
        s = detect_at(C, A, i, not args.sem_exigir_tendencia, tick)
        if s and s["lado"] != "atencao" and s["forca"] >= args.min_forca:
            avaliar(C, s)
            sinais.append(s)
    alvo = sum(1 for s in sinais if s["resultado"] == "alvo")
    stop = sum(1 for s in sinais if s["resultado"] == "stop")
    print(f"\nTeste simples em {nome}, últimos {len(C)} candles:")
    print(f"  sinais: {len(sinais)} | alvo: {alvo} | stop: {stop} | "
          f"alvo antes do stop: {round(100 * alvo / (alvo + stop)) if alvo + stop else '—'}% | "
          f"resultado: {2 * alvo - stop:+d}R")
    print("  (poucos sinais dizem pouco; não garante resultado futuro)\n")


# ----------------------------------------------------------------------------
# Dados: IQ Option (leitura) ou candles simulados
# ----------------------------------------------------------------------------


def conectar():
    try:
        from iqoptionapi.stable_api import IQ_Option
    except ImportError:
        sys.exit("Instale a biblioteca primeiro: pip install iqoptionapi")
    email = os.environ.get("IQ_EMAIL") or input("E-mail da IQ Option: ").strip()
    senha = os.environ.get("IQ_SENHA") or getpass.getpass("Senha (não aparece na tela): ")
    api = IQ_Option(email, senha)
    ok, motivo = api.connect()
    if not ok and "2FA" in str(motivo) and hasattr(api, "connect_2fa"):
        ok, motivo = api.connect_2fa(input("Código 2FA: ").strip())
    if not ok:
        sys.exit(f"Falha na conexão: {motivo}")
    print("Conectado (modo somente leitura).")
    return api


def buscar_candles(api, ativo, tamanho, quantidade):
    """Candles FECHADOS, do mais antigo para o mais novo."""
    bruto = api.get_candles(ativo, tamanho, quantidade, time.time()) or []
    agora = time.time()
    C = []
    for r in sorted(bruto, key=lambda r: r["from"]):
        if r["from"] + tamanho > agora:  # candle ainda em formação
            continue
        C.append({"t": r["from"], "o": r["open"], "h": r["max"], "l": r["min"], "c": r["close"]})
    return C


class Simulador:
    """Candles aleatórios para testar o script sem login."""

    def __init__(self, tamanho, tick, seed=42, base=1.0850):
        self.r = random.Random(seed)
        self.p = base
        self.atr = base * 0.00037 * (0.45 if tamanho <= 60 else 1)
        self.t = int(time.time() // tamanho * tamanho) - 300 * tamanho
        self.tam, self.tick, self.drift, self.rest = tamanho, tick, 0.0, 0

    def proximo(self):
        r, atr = self.r, self.atr
        if self.rest <= 0:
            self.rest, u = 8 + int(r.random() * 18), r.random()
            self.drift = .32 * atr if u < .35 else -.32 * atr if u < .7 else 0
        self.rest -= 1
        o = self.p + r.gauss(0, .08 * atr)
        c = o + self.drift + r.gauss(0, .5 * atr)
        h = max(o, c) + abs(r.gauss(0, .3 * atr))
        l = min(o, c) - abs(r.gauss(0, .3 * atr))
        q = r.random()
        if q < .09:
            l -= (.9 + r.random() * .9) * atr
        elif q < .17:
            h += (.9 + r.random() * .9) * atr
        rt = lambda v: round(round(v / self.tick) * self.tick, 8)
        o, c = rt(o), rt(c)
        cd = {"t": self.t, "o": o, "h": max(rt(h), o, c), "l": min(rt(l), o, c), "c": c}
        self.p, self.t = c, self.t + self.tam
        return cd


# ----------------------------------------------------------------------------
# Avisos e arquivos
# ----------------------------------------------------------------------------


def hora(t):
    return datetime.fromtimestamp(t).strftime("%d/%m %H:%M")


def telegram(texto):
    tok, chat = os.environ.get("TELEGRAM_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if not tok or not chat:
        return
    dados = urllib.parse.urlencode({"chat_id": chat, "text": texto}).encode()
    try:
        urllib.request.urlopen(urllib.request.Request(f"https://api.telegram.org/bot{tok}/sendMessage", data=dados), timeout=10)
    except Exception as e:  # aviso extra: nunca derruba o monitor
        print("Telegram falhou:", e)



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


def salvar_csv(caminho, hist):
    with open(caminho, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["time", "open", "high", "low", "close"])
        for t in sorted(hist):
            c = hist[t]
            w.writerow([datetime.fromtimestamp(t).strftime("%Y-%m-%d %H:%M:%S"), c["o"], c["h"], c["l"], c["c"]])


def resumo(estado, tempo, desde):
    """Texto com a situação de cada ativo e os sinais desde `desde` (epoch)."""
    hm = lambda t: datetime.fromtimestamp(t).strftime("%H:%M")
    linhas = [f"RESUMO {datetime.now().strftime('%d/%m %H:%M')} | candles de {tempo} min"]
    for nome, e in estado.items():
        ult = e["hist"][max(e["hist"])]["c"]
        rec = [r for r in e["recentes"] if r["quando"] >= desde]
        if rec:
            r = rec[-1]
            linhas.append(f"{nome} {ult:.{e['dec']}f} | {len(rec)} sinal(is); último: {r['lado'].upper()} {r['nome']} "
                          f"(entrada às {hm(r['abre'])})")
        else:
            linhas.append(f"{nome} {ult:.{e['dec']}f} | sem sinais no período")
    return "\n".join(linhas)


def avisar(s, ativo, tempo, dec):
    f = lambda v: f"{v:.{dec}f}"
    hm = lambda t: datetime.fromtimestamp(t).strftime("%H:%M")
    abre = s["t"] + tempo * 60  # o candle do sinal acabou de fechar: o próximo abre agora
    texto = (f"{s['lado'].upper()} {ativo} {tempo}min | {s['nome']} (força {s['forca']}/3)\n"
             f"ENTRAR ÀS {hm(abre)} (abertura do próximo candle), válido até {hm(abre + 3 * tempo * 60)}\n"
             f"Se for opção binária: expiração às {hm(abre + tempo * 60)} (1 candle)\n"
             f"Referência: entrada {f(s['entrada'])} stop {f(s['stop'])} alvo {f(s['alvo'])} | candle do sinal {hora(s['t'])}")
    print("\a\n" + "=" * 70 + "\n" + texto + "\n" + "=" * 70)
    telegram(texto)


# ----------------------------------------------------------------------------


def tick_do_ativo(nome):
    n = nome.upper()
    if "JPY" in n:
        return 0.001
    if n.startswith(("BTC", "ETH", "LTC", "XRP", "BNB")):
        return 0.01
    return 0.00001


def base_simulada(nome):
    n = nome.upper()
    return 150.2 if "JPY" in n else 95000.0 if n.startswith("BTC") else 1.0850


def main():
    ap = argparse.ArgumentParser(description="Avisos de price action em vários ativos da IQ Option (somente leitura).")
    ap.add_argument("--ativos", "--ativo", dest="ativos", default="EURUSD,GBPUSD,USDJPY",
                    help="lista separada por vírgula (no fim de semana o mercado real fecha: use -OTC)")
    ap.add_argument("--tempo", type=int, default=1, help="tempo gráfico em minutos (padrão 1; também 5, 15...)")
    ap.add_argument("--min-forca", type=int, default=2, choices=[1, 2, 3])
    ap.add_argument("--sem-exigir-tendencia", action="store_true")
    ap.add_argument("--tick", type=float, default=None, help="menor variação de preço para todos (padrão automático por ativo)")
    ap.add_argument("--historico", type=int, default=300, help="candles iniciais por ativo")
    ap.add_argument("--intervalo", type=float, default=3.0, help="segundos entre rodadas de consulta")
    ap.add_argument("--pasta", default=".", help="pasta dos CSVs (um por ativo)")
    ap.add_argument("--backtest", action="store_true", help="mostra o teste simples no histórico ao iniciar")
    ap.add_argument("--so-sinais", action="store_true", help="não mostra as linhas 'sem sinal'")
    ap.add_argument("--resumo", action="store_true", help="envia um resumo de todos os ativos (terminal e Telegram)")
    ap.add_argument("--resumo-min", type=float, default=60.0, help="intervalo do resumo em minutos (padrão 60, na hora cheia)")
    ap.add_argument("--simulado", action="store_true", help="usa candles aleatórios, sem login")
    ap.add_argument("--dashboard-url", default="http://127.0.0.1:8000",
                    help="URL local do painel")
    args = ap.parse_args()
    nomes = []
    for a in args.ativos.split(","):
        a = a.strip().upper()
        if a and a not in nomes:
            nomes.append(a)
    if not nomes:
        sys.exit("Informe ao menos um ativo em --ativos.")
    tam = args.tempo * 60
    os.makedirs(args.pasta, exist_ok=True)
    api = None if args.simulado else conectar()

    estado = {}
    for idx, nome in enumerate(nomes):
        tick = args.tick or tick_do_ativo(nome)
        dec = max(0, round(-math.log10(tick)))
        sim = None
        if args.simulado:
            sim = Simulador(tam, tick, seed=42 + idx, base=base_simulada(nome))
            C = [sim.proximo() for _ in range(args.historico)]
        else:
            C = buscar_candles(api, nome, tam, args.historico)
            if len(C) < 30:
                print(f"{nome}: poucos candles (ativo fechado?). Tente {nome}-OTC. Ignorado.")
                continue
        hist = {c["t"]: c for c in C}
        arquivo = os.path.join(args.pasta, f"{nome}_{args.tempo}m.csv")
        salvar_csv(arquivo, hist)
        estado[nome] = {"tick": tick, "dec": dec, "hist": hist, "ultimo": max(hist), "sim": sim, "arquivo": arquivo, "recentes": [], "pendente": None, "janela_enviada": 0}
        print(f"{nome} {args.tempo}min | {len(hist)} candles | CSV: {arquivo}")
        if args.backtest:
            backtest(C, args, tick, nome)
    if not estado:
        sys.exit("Nenhum ativo com dados.")

    iv = args.resumo_min * 60
    prox_resumo = (int(time.time() // iv) + 1) * iv  # alinhado: de 60 em 60 min cai na hora cheia
    if args.resumo:
        print(f"Resumo a cada {args.resumo_min:g} min, próximo às {datetime.fromtimestamp(prox_resumo).strftime('%H:%M')}.")
    print(f"\nMonitorando {len(estado)} ativo(s) em {args.tempo} min. Ctrl+C para parar.\n")
    publicar_heartbeat(args.dashboard_url.rstrip("/"), "simulado" if args.simulado else "iq_option_demo", list(estado), args.tempo)
    while True:
        try:
            time.sleep(args.intervalo)
            if api is not None and hasattr(api, "check_connect") and not api.check_connect():
                print("Conexão caiu, reconectando...")
                api = conectar()
            for nome, e in estado.items():
                if e["sim"]:
                    novos = [e["sim"].proximo()]
                else:
                    if time.time() < e["ultimo"] + 2 * tam + 1:
                        continue  # o candle seguinte ainda não fechou
                    novos = [c for c in buscar_candles(api, nome, tam, 60) if c["t"] > e["ultimo"]]
                for c in novos:
                    e["hist"][c["t"]] = c
                    e["ultimo"] = c["t"]
                    serie = [e["hist"][t] for t in sorted(e["hist"])][-400:]
                    A = calc_atr(serie)
                    s = detect_at(serie, A, len(serie) - 1, not args.sem_exigir_tendencia, e["tick"])
                    if s and s["lado"] != "atencao" and s["forca"] >= args.min_forca:
                        # Guarda o melhor sinal e espera a janela de 30 segundos.
                        # Não envia imediatamente para não gerar vários alertas seguidos.
                        e["pendente"] = s.copy()
                    elif not args.so_sinais:
                        print(f"{hora(c['t'])}  {nome:<12} {c['c']:.{e['dec']}f}  sem sinal")
                # Janela organizada: avisa aproximadamente 30 segundos
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
                    for t in sorted(e["hist"])[:-2000]:
                        del e["hist"][t]
                    salvar_csv(e["arquivo"], e["hist"])
            publicar_heartbeat(args.dashboard_url.rstrip("/"), "simulado" if args.simulado else "iq_option_demo", list(estado), args.tempo)
            if args.resumo and time.time() >= prox_resumo:
                texto = resumo(estado, args.tempo, time.time() - iv)
                print("\n" + texto + "\n")
                telegram(texto)
                prox_resumo += iv
                for e in estado.values():
                    e["recentes"] = [r for r in e["recentes"] if r["quando"] >= time.time() - iv]
        except KeyboardInterrupt:
            print("\nEncerrado.")
            return
        except Exception as ex:
            print("Erro:", ex, "- tentando de novo em 10 s")
            time.sleep(10)


if __name__ == "__main__":
    main()


