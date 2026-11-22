from __future__ import annotations

PADROES_PRIORITARIOS = {
    "Estrela da tarde",
    "Estrela da manhã",
    "Estrela da manhã doji",
    "Três corvos negros",
    "Engolfo de baixa",
    "Três corvos idênticos",
    "Três soldados brancos",
    "Ataque das três linhas",
    "Três estrelas do sul",
}

def rsi_14(candles, i, periodo=14):
    if i < periodo:
        return 50.0

    ganhos = 0.0
    perdas = 0.0

    for j in range(i - periodo + 1, i + 1):
        variacao = candles[j]["c"] - candles[j - 1]["c"]
        ganhos += max(variacao, 0.0)
        perdas += max(-variacao, 0.0)

    if perdas == 0:
        return 100.0

    rs = ganhos / perdas
    return 100.0 - 100.0 / (1.0 + rs)


def resolver_sistema(matriz, vetor):
    tamanho = len(vetor)
    a = [linha[:] + [vetor[i]] for i, linha in enumerate(matriz)]

    for coluna in range(tamanho):
        pivo = max(range(coluna, tamanho), key=lambda linha: abs(a[linha][coluna]))

        if abs(a[pivo][coluna]) < 1e-12:
            return None

        a[coluna], a[pivo] = a[pivo], a[coluna]

        divisor = a[coluna][coluna]
        a[coluna] = [valor / divisor for valor in a[coluna]]

        for linha in range(tamanho):
            if linha == coluna:
                continue

            fator = a[linha][coluna]
            a[linha] = [
                a[linha][k] - fator * a[coluna][k]
                for k in range(tamanho + 1)
            ]

    return [a[i][tamanho] for i in range(tamanho)]


def regressao_cubica(candles, atr, i, janela=20):
    """
    Regressão de terceiro grau nos fechamentos.
    Serve para medir inclinação, curvatura e qualidade do ajuste.
    Não prevê preço futuro nem garante resultado.
    """
    inicio = max(0, i - janela + 1)
    serie = candles[inicio:i + 1]

    if len(serie) < 8 or atr <= 0:
        return {"slope": 0.0, "curvature": 0.0, "r2": 0.0}

    preco_base = serie[0]["c"]
    n = len(serie)

    xs = [-1.0 + 2.0 * indice / (n - 1) for indice in range(n)]
    ys = [(candle["c"] - preco_base) / atr for candle in serie]

    matriz = [[0.0] * 4 for _ in range(4)]
    vetor = [0.0] * 4

    for x, y in zip(xs, ys):
        potencias = [1.0, x, x * x, x * x * x]

        for linha in range(4):
            vetor[linha] += potencias[linha] * y

            for coluna in range(4):
                matriz[linha][coluna] += potencias[linha] * potencias[coluna]

    coeficientes = resolver_sistema(matriz, vetor)

    if coeficientes is None:
        return {"slope": 0.0, "curvature": 0.0, "r2": 0.0}

    media = sum(ys) / len(ys)

    erro_total = sum((y - media) ** 2 for y in ys)

    erro_modelo = sum(
        (
            y - sum(coeficientes[k] * (x ** k) for k in range(4))
        ) ** 2
        for x, y in zip(xs, ys)
    )

    r2 = 0.0 if erro_total <= 1e-12 else max(0.0, 1.0 - erro_modelo / erro_total)

    slope = coeficientes[1] + 2 * coeficientes[2] + 3 * coeficientes[3]
    curvature = 2 * coeficientes[2] + 6 * coeficientes[3]

    return {
        "slope": slope,
        "curvature": curvature,
        "r2": r2,
    }


def buscar_pivos(candles, i, distancia=2, janela=24):
    inicio = max(distancia, i - janela)
    fim = i - distancia

    altos = []
    baixos = []

    for j in range(inicio, fim + 1):
        vizinhos = candles[j - distancia:j + distancia + 1]

        if candles[j]["h"] >= max(x["h"] for x in vizinhos):
            altos.append(candles[j]["h"])

        if candles[j]["l"] <= min(x["l"] for x in vizinhos):
            baixos.append(candles[j]["l"])

    return altos[-2:], baixos[-2:]


def avaliar_reversao(candles, atrs, i, sinal):
    """
    Score quantitativo 0–100.
    Os percentuais de vídeos não são tratados como probabilidade real.
    """
    nome = sinal["nome"]
    lado = sinal["lado"]

    if nome not in PADROES_PRIORITARIOS:
        return {
            "aceito": False,
            "score": 0,
            "motivos": ["Padrão fora da lista prioritária"],
        }

    atr = atrs[i]

    if atr <= 0:
        return {
            "aceito": False,
            "score": 0,
            "motivos": ["ATR inválido"],
        }

    candle = candles[i]
    corpo = abs(candle["c"] - candle["o"])
    amplitude = max(candle["h"] - candle["l"], 1e-12)

    rsi = rsi_14(candles, i)
    curva = regressao_cubica(candles, atr, i)
    altos, baixos = buscar_pivos(candles, i)

    compra = lado == "compra"
    score = 35
    motivos = ["Formação prioritária reconhecida"]

    if corpo / amplitude >= 0.45 and amplitude >= 0.70 * atr:
        score += 15
        motivos.append("Corpo e amplitude do candle confirmados")

    if sinal.get("alinhado"):
        score += 15
        motivos.append("Tendência anterior coerente com o padrão")

    if (compra and rsi <= 45) or ((not compra) and rsi >= 55):
        score += 12
        motivos.append("RSI 14 indica exaustão")

    if curva["r2"] >= 0.25:
        score += 8
        motivos.append("Regressão cúbica tem ajuste suficiente")

    if (compra and curva["curvature"] > 0) or ((not compra) and curva["curvature"] < 0):
        score += 8
        motivos.append("Curvatura favorece possível reversão")

    if (compra and len(baixos) == 2 and baixos[-1] <= baixos[-2]) or (
        (not compra) and len(altos) == 2 and altos[-1] >= altos[-2]
    ):
        score += 7
        motivos.append("Estrutura de pivô/correção identificada")

    score = min(100, score)

    return {
        "aceito": True,
        "score": score,
        "rsi": round(rsi, 1),
        "r2": round(curva["r2"], 3),
        "motivos": motivos,
    }
