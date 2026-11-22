import { useEffect, useMemo, useState } from "react";
import { Activity, Bell, Clock3, FlaskConical, History, Settings, Wifi } from "lucide-react";

type Signal = {
  id: string; ativo: string; direcao: "COMPRA" | "VENDA"; padrao: string;
  forca: number; entrada: number; stop: number; alvo: number;
  entry_at: string; valid_until: string; resultado: string;
};
type Status = {
  connected: boolean; mode: string; assets: string[];
  timeframe_min: number; signals_today: number; last_signal: Signal | null;
};

const API = "http://127.0.0.1:8000";
const hora = (v?: string) => v ? new Date(v).toLocaleTimeString("pt-BR", {hour:"2-digit",minute:"2-digit"}) : "—";
const preco = (v: number) => v.toFixed(v > 100 ? 3 : 5);

export default function App() {
  const [signals, setSignals] = useState<Signal[]>([]);
  const [status, setStatus] = useState<Status | null>(null);
  const [erro, setErro] = useState("");
  const [tab, setTab] = useState("live");
  const [ativo, setAtivo] = useState("todos");
  const [direcao, setDirecao] = useState("todos");
  const [forca, setForca] = useState(1);
  const [som, setSom] = useState(false);
  const [agora, setAgora] = useState(new Date());
  const [backtest, setBacktest] = useState<any>(null);

  async function carregar() {
    try {
      const [a, b, c] = await Promise.all([
        fetch(API + "/api/signals"),
        fetch(API + "/api/status"),
        fetch(API + "/api/backtest")
      ]);
      if (!a.ok || !b.ok) throw new Error();
      setSignals((await a.json()).items);
      setStatus(await b.json());
      setBacktest(await c.json());
      setErro("");
    } catch {
      setErro("Monitor desconectado. Rode: python dashboard_server.py");
    }
  }

  useEffect(() => {
    carregar();
    const timer = setInterval(() => { carregar(); setAgora(new Date()); }, 10000);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    const ws = new WebSocket("ws://127.0.0.1:8000/ws");
    ws.onmessage = (evento) => {
      const mensagem = JSON.parse(evento.data);
      if (mensagem.type === "signal") {
        setSignals((antigos) => [mensagem.data, ...antigos].slice(0, 200));
        if (som) {
          const audio = new AudioContext();
          const oscilador = audio.createOscillator();
          oscilador.connect(audio.destination);
          oscilador.start();
          oscilador.stop(audio.currentTime + 0.12);
        }
      }
      if (mensagem.type === "status") setStatus(mensagem.data);
    };
    ws.onerror = () => setErro("Monitor desconectado. Rode: python dashboard_server.py");
    return () => ws.close();
  }, [som]);

  const filtrados = useMemo(() => signals.filter((s) =>
    (ativo === "todos" || s.ativo === ativo) &&
    (direcao === "todos" || s.direcao === direcao) &&
    s.forca >= forca
  ), [signals, ativo, direcao, forca]);

  const ultimo = filtrados[0] || status?.last_signal;

  return <div className="app">
    <aside>
      <h1>▮▮ Sinais<span>TredBot</span></h1>
      <button className={tab==="live"?"active":""} onClick={()=>setTab("live")}><Activity/> Sinais ao vivo</button>
      <button className={tab==="history"?"active":""} onClick={()=>setTab("history")}><History/> Histórico</button>
      <button className={tab==="backtest"?"active":""} onClick={()=>setTab("backtest")}><Activity/> Backtest</button>
      <button className={tab==="settings"?"active":""} onClick={()=>setTab("settings")}><Settings/> Configurações</button>
    </aside>

    <main>
      <header>
        <b className={status?.connected ? "online" : "offline"}>
          <i/> {status?.connected ? "MONITOR CONECTADO" : "MONITOR DESCONECTADO"}
        </b>
        <span><Clock3/> {agora.toLocaleTimeString("pt-BR")}</span>
      </header>

      {erro && <div className="erro">{erro}</div>}

      <section className="cards">
        <Card icon={<Wifi/>} title="Monitor" value={status?.connected ? "Conectado" : "Desconectado"} />
        <Card icon={<FlaskConical/>} title="Modo" value={status?.mode === "iq_option_demo" ? "IQ Option DEMO" : "Simulado"} />
        <Card icon={<Activity/>} title="Ativos" value={status?.assets.join(", ") || "—"} />
        <Card icon={<Bell/>} title="Sinais hoje" value={String(status?.signals_today || 0)} />
      </section>

      {tab === "live" && <>
        <section className={"hero " + (ultimo?.direcao === "VENDA" ? "venda" : "")}>
          <div>
            <small>SINAL MAIS RECENTE</small>
            <h2>{ultimo ? `${ultimo.direcao} · ${ultimo.ativo}` : "Aguardando sinais"}</h2>
            <p>{ultimo?.padrao || "O próximo padrão detectado aparecerá aqui."}</p>
            <strong>{"★".repeat(ultimo?.forca || 0)}{"☆".repeat(3 - (ultimo?.forca || 0))}</strong>
          </div>
          {ultimo && <div className="niveis">
            <div>Entrada <b>{preco(ultimo.entrada)}</b></div>
            <div>Stop <b className="red">{preco(ultimo.stop)}</b></div>
            <div>Alvo <b className="green">{preco(ultimo.alvo)}</b></div>
            <div>Entrar às <b>{hora(ultimo.entry_at)}</b></div>
          </div>}
        </section>

        <section className="filtros">
          <select value={ativo} onChange={e=>setAtivo(e.target.value)}>
            <option value="todos">Todos os ativos</option>
            {(status?.assets || []).map(x=><option key={x}>{x}</option>)}
          </select>
          <select value={direcao} onChange={e=>setDirecao(e.target.value)}>
            <option value="todos">Compra e venda</option>
            <option value="COMPRA">Somente compra</option>
            <option value="VENDA">Somente venda</option>
          </select>
          <select value={forca} onChange={e=>setForca(Number(e.target.value))}>
            <option value="1">Força mínima: 1</option>
            <option value="2">Força mínima: 2</option>
            <option value="3">Força mínima: 3</option>
          </select>
        </section>

        <Tabela sinais={filtrados}/>
      </>}

      {tab === "history" && <section className="painel">
        <h2>Histórico</h2>
        <p>Os CSVs gerados por <code>sinais_iq.py</code> ficam na pasta <code>data</code>.</p>
        <p>Ativos disponíveis: {status?.assets.join(", ") || "inicie o monitor"}</p>
      </section>}

      {tab === "backtest" && <section className="painel">
        <h2>Backtest</h2>
        <div className="resultado">
          <b>Sinais: {backtest?.signals || 0}</b>
          <b>Alvos: {backtest?.targets || 0}</b>
          <b>Stops: {backtest?.stops || 0}</b>
          <b>Taxa: {backtest?.win_rate == null ? "—" : backtest.win_rate + "%"}</b>
          <b>Resultado: {backtest?.result_r || 0}R</b>
        </div>
        <p>Resultados históricos não garantem resultados futuros.</p>
      </section>}

      {tab === "settings" && <section className="painel">
        <h2>Configurações</h2>
        <label><input type="checkbox" checked={som} onChange={e=>setSom(e.target.checked)}/> Tocar som ao receber novo sinal</label>
        <p>O painel não salva senhas e não envia ordens.</p>
      </section>}

      <footer>Ferramenta educacional. Não é recomendação financeira. Sinais não são garantia de lucro.</footer>
    </main>
  </div>;
}

function Card({icon,title,value}:{icon:any,title:string,value:string}) {
  return <article className="card"><span>{icon}</span><div><small>{title}</small><h3>{value}</h3></div></article>;
}

function Tabela({sinais}:{sinais:Signal[]}) {
  return <section className="painel tabela"><h2>Sinais ao vivo</h2><div className="rolagem">
    <table><thead><tr><th>Hora</th><th>Ativo</th><th>Direção</th><th>Padrão</th><th>Força</th><th>Entrada</th><th>Stop</th><th>Alvo</th><th>Resultado</th></tr></thead>
    <tbody>{sinais.length ? sinais.map(s=><tr key={s.id}>
      <td>{hora(s.entry_at)}</td><td>{s.ativo}</td>
      <td><b className={s.direcao==="COMPRA"?"compra":"venda-pill"}>{s.direcao}</b></td>
      <td>{s.padrao}</td><td className="stars">{"★".repeat(s.forca)}</td>
      <td>{preco(s.entrada)}</td><td className="red">{preco(s.stop)}</td>
      <td className="green">{preco(s.alvo)}</td><td>{s.resultado}</td>
    </tr>) : <tr><td colSpan={9}>Aguardando o primeiro sinal.</td></tr>}</tbody></table>
  </div></section>;
}
