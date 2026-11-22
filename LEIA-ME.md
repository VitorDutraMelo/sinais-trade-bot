# SinaisTredBot com a IQ Option

Dois jeitos de receber candles e avisos ao vivo. Dá para usar os dois juntos.

| Arquivo | Para que serve |
|---|---|
| `sinais_iq.py` | Lê os candles, detecta os padrões e avisa COMPRA/VENDA com a hora de entrada no terminal e no Telegram. Gera um CSV por ativo. |
| `iq_bridge_mcp.py` | Ponte local para o app web buscar os candles ao vivo sozinho. Só funciona no app Claude do computador. |

Os dois só **leem** candles. Nenhum deles envia ordens ou mexe no saldo. A `iqoptionapi` não é oficial: a IQ Option pode bloquear a conta ou mudar algo a qualquer momento. Ferramenta educacional, não é recomendação de investimento.

## 1. Instalação (uma vez)

1. Instale o Python 3.10 ou mais novo (python.org). No Windows, marque "Add Python to PATH".
2. No terminal: `pip install mcp iqoptionapi`
3. Salve `sinais_iq.py` e `iq_bridge_mcp.py` **na mesma pasta** (a ponte usa o `sinais_iq.py`).

## 2. Testar sem login (candles aleatórios)

```
python sinais_iq.py --simulado --ativos EURUSD,GBPUSD --backtest
```

Deve aparecer o teste simples e, depois de alguns instantes, avisos com "ENTRAR ÀS HH:MM".

## 3. Avisos ao vivo no terminal e no Telegram

Defina as credenciais (não escreva a senha dentro do arquivo):

- Windows (PowerShell): `$env:IQ_EMAIL="seu@email.com"; $env:IQ_SENHA="sua_senha"`
- macOS/Linux: `export IQ_EMAIL="seu@email.com" IQ_SENHA="sua_senha"`

Rode:

```
python sinais_iq.py --ativos EURUSD,GBPUSD,USDJPY --tempo 1 --resumo
```

- `--tempo 1` usa candles de 1 minuto (padrão). `--min-forca 3` deixa só os sinais mais fortes.
- `--resumo` manda um resumo de todos os ativos a cada hora cheia (`--resumo-min 30` muda o intervalo).
- No fim de semana o mercado real fecha: use `EURUSD-OTC`, `GBPUSD-OTC`...
- Telegram (opcional): crie um bot no @BotFather e defina `TELEGRAM_TOKEN` e `TELEGRAM_CHAT_ID`.
- O script gera `EURUSD_1m.csv` etc. Você pode importar esses arquivos no app (botão "Importar CSV"; aceita vários de uma vez).

O script precisa ficar rodando no computador para avisar.

## 4. Ponte para o app (candles ao vivo dentro do app)

1. Abra o app Claude do computador > Configurações > Desenvolvedor > Editar configuração. Isso abre o `claude_desktop_config.json`.
2. Adicione (ajuste o caminho do arquivo e o nome do Python se precisar):

```json
{
  "mcpServers": {
    "iqoption": {
      "command": "python",
      "args": ["C:\\Users\\SEU_USUARIO\\sinaistredbot\\iq_bridge_mcp.py"],
      "env": { "IQ_EMAIL": "seu@email.com", "IQ_SENHA": "sua_senha" }
    }
  }
}
```

No macOS use `"command": "python3"` e um caminho como `/Users/SEU_USUARIO/sinaistredbot/iq_bridge_mcp.py`.
O nome do servidor precisa ser exatamente `iqoption`.

3. Feche e abra o app Claude de novo.
4. Abra o SinaisTredBot **dentro do app Claude do computador**, vá ao cartão "IQ Option ao vivo", escolha os ativos e o tempo gráfico e clique em **Conectar**. Permita quando o app perguntar.
5. A cada 15 segundos o app busca candles novos, enquanto estiver aberto e visível. Quando um padrão se completa, aparece o aviso com o ativo, COMPRA ou VENDA e a hora de entrada.

Para testar a ponte sem login, coloque `"IQ_SIMULADO": "1"` no `env` (candles aleatórios em tempo real) e troque depois.

## Cuidados

- A senha fica em texto no arquivo de configuração do seu computador. Use uma senha que você não repete em outros serviços e não compartilhe esse arquivo.
- Contas com verificação em duas etapas: a ponte não suporta o código; o `sinais_iq.py` pergunta o código.
- Se a conexão falhar 3 vezes seguidas, o app para de tentar, para não gerar muitos logins.
- A ponte só funciona no app Claude do computador, aberto, com o servidor `iqoption` rodando. No navegador ou no celular o cartão mostra que a ponte não foi encontrada.
- Dados de exemplo são aleatórios. Teste a estratégia com dados reais, e de preferência em conta de treinamento.

## Problemas comuns

- **"Não achei a ponte iqoption"**: o app não é o do computador, o nome no JSON não é `iqoption`, ou faltou reiniciar o app.
- **"A biblioteca iqoptionapi não está instalada"**: rode `pip install iqoptionapi` com o mesmo Python do `command`.
- **"Sem candles (ativo fechado?)"**: fim de semana ou fora do horário. Use `-OTC`.
- **"Falha na conexão com a IQ Option"**: confira e-mail e senha; a biblioteca pode precisar de uma versão atualizada (fork no GitHub).
