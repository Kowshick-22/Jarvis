import { useState } from 'react';
import {
  Activity, ArrowUpRight, Brain, Check, ChevronRight, Command,
  Cpu, Database, Globe, LockKeyhole, Mic, MicOff, Orbit, Plus,
  Search, ShieldCheck, Sparkles, Terminal, Trash2, Wifi,
} from 'lucide-react';
import './JarvisPage.css';

type Message = { role: 'you' | 'jarvis'; text: string };

const suggestions = [
  { icon: Terminal, title: 'Explain a PySpark error', detail: 'Debug code and understand the root cause' },
  { icon: Brain, title: 'Teach me BigQuery window functions', detail: 'Learn with examples and practice questions' },
  { icon: Sparkles, title: 'Build a simple expense tracker', detail: 'Plan, create files, and test an app' },
];

export function JarvisPage() {
  const [listening, setListening] = useState(false);
  const [command, setCommand] = useState('');
  const [memoryEnabled, setMemoryEnabled] = useState(true);
  const [messages, setMessages] = useState<Message[]>([
    { role: 'jarvis', text: 'Good evening. JARVIS prototype is ready. Choose a task or enter a command to explore the interface.' },
  ]);
  const [pendingWeb, setPendingWeb] = useState<string | null>(null);

  const submitCommand = (value: string) => {
    const clean = value.trim();
    if (!clean) return;
    setMessages((items) => [...items, { role: 'you', text: clean }]);
    setCommand('');
    setListening(false);
    if (/latest|documentation|search the web|online|internet/i.test(clean)) {
      setPendingWeb(clean);
      setMessages((items) => [...items, { role: 'jarvis', text: 'This request may need internet access. I will wait for your approval before any external request.' }]);
      return;
    }
    setMessages((items) => [...items, { role: 'jarvis', text: 'Prototype mode: your command has been captured. The next implementation step is to connect the local model and agent runtime so JARVIS can perform this task for real.' }]);
  };

  return (
    <main className="jarvis-page">
      <header className="jarvis-topbar">
        <div className="jarvis-brand">
          <div className="jarvis-brand-mark"><Orbit size={25} strokeWidth={1.5} /></div>
          <div><div className="jarvis-brand-name">J.A.R.V.I.S.</div><div className="jarvis-brand-subtitle">PERSONAL INTELLIGENCE SYSTEM</div></div>
        </div>
        <div className="jarvis-topbar-right"><span className="jarvis-status-dot" /> LOCAL-FIRST MODE <span className="jarvis-version">PROTOTYPE 01</span></div>
      </header>

      <div className="jarvis-layout">
        <aside className="jarvis-sidebar">
          <div className="jarvis-sidebar-label">WORKSPACE</div>
          <button className="jarvis-nav-item active"><Command size={16} /> Command center <span className="jarvis-nav-key">⌘K</span></button>
          <button className="jarvis-nav-item" onClick={() => setMessages([{ role: 'jarvis', text: 'New session started. What shall we work on?' }])}><Plus size={16} /> New session</button>
          <div className="jarvis-sidebar-label jarvis-sidebar-spaced">MEMORY</div>
          <div className="jarvis-memory-mini"><Database size={16} /><div><strong>Local memory</strong><small>{memoryEnabled ? 'Enabled · prototype only' : 'Paused'}</small></div><button type="button" className={memoryEnabled ? 'jarvis-toggle on' : 'jarvis-toggle'} onClick={() => setMemoryEnabled((enabled) => !enabled)} role="switch" aria-checked={memoryEnabled} aria-label="Toggle local memory" /></div>
          <div className="jarvis-sidebar-label jarvis-sidebar-spaced">SYSTEM</div>
          <div className="jarvis-system-row"><Cpu size={16} /><span>Local model</span><b>Not connected</b></div>
          <div className="jarvis-system-row"><Mic size={16} /><span>Microphone</span><b>{listening ? 'UI demo' : 'Off'}</b></div>
          <div className="jarvis-system-row"><Wifi size={16} /><span>Network</span><b>Approval required</b></div>
          <div className="jarvis-sidebar-footer"><ShieldCheck size={16} /><span>Privacy-first prototype.<small>Storage and network controls are not fully implemented yet.</small></span></div>
        </aside>

        <section className="jarvis-main">
          <div className="jarvis-heading-row">
            <div><div className="jarvis-eyebrow">COMMAND CENTER / OVERVIEW</div><h1>How can I help you today?</h1><p>Your personal assistant for coding, learning, and building things.</p></div>
            <div className="jarvis-clock"><Activity size={15} /> SYSTEM READY</div>
          </div>

          <section className="jarvis-core-panel">
            <div className={listening ? 'jarvis-reactor listening' : 'jarvis-reactor'} aria-label={listening ? 'Prototype listening state' : 'Assistant idle'}>
              <div className="jarvis-reactor-ring ring-one" /><div className="jarvis-reactor-ring ring-two" /><div className="jarvis-reactor-ring ring-three" />
              <div className="jarvis-reactor-core"><Orbit size={49} strokeWidth={1.1} /></div>
              <div className="jarvis-reactor-cross cross-top" /><div className="jarvis-reactor-cross cross-bottom" /><div className="jarvis-reactor-cross cross-left" /><div className="jarvis-reactor-cross cross-right" />
            </div>
            <div className="jarvis-core-copy"><div className="jarvis-eyebrow">JARVIS CORE</div><h2>{listening ? 'I’m listening.' : 'Standing by.'}</h2><p>{listening ? 'Prototype listening state. No audio is being recorded in this UI demo.' : 'Ready when you are. Start a command or choose a suggested task.'}</p>
              <button className={listening ? 'jarvis-talk-button is-active' : 'jarvis-talk-button'} onClick={() => setListening(!listening)}>{listening ? <MicOff size={17} /> : <Mic size={17} />}{listening ? 'Stop listening demo' : 'Push to talk'}<span>⌥ Space</span></button>
              <div className="jarvis-microphone-note"><LockKeyhole size={13} /> Microphone stays off until explicitly activated in the real app.</div>
            </div>
          </section>

          <div className="jarvis-section-heading"><div><h3>Quick actions</h3><p>Pick up where you left off, or start something new.</p></div><span className="jarvis-small-label">SUGGESTED</span></div>
          <div className="jarvis-suggestions">{suggestions.map((item) => { const Icon = item.icon; return <button key={item.title} className="jarvis-suggestion" onClick={() => submitCommand(item.title)}><div className="jarvis-suggestion-icon"><Icon size={19} /></div><div className="jarvis-suggestion-copy"><strong>{item.title}</strong><span>{item.detail}</span></div><ChevronRight size={17} className="jarvis-suggestion-arrow" /></button>; })}</div>

          <section className="jarvis-console">
            <div className="jarvis-console-title"><Terminal size={16} /><span>COMMAND INPUT</span><span className="jarvis-console-local">LOCAL SESSION</span></div>
            <form onSubmit={(event) => { event.preventDefault(); submitCommand(command); }} className="jarvis-command-form">
              <input value={command} onChange={(event) => setCommand(event.target.value)} placeholder="Ask JARVIS to explain, build, debug, or teach..." aria-label="Command input" />
              <button type="submit" disabled={!command.trim()}><ArrowUpRight size={18} /> Run command</button>
            </form>
            {messages.length > 1 && <div className="jarvis-session-log"><div className="jarvis-log-heading"><span>SESSION LOG</span><button onClick={() => setMessages([])}><Trash2 size={13} /> Clear</button></div>{messages.slice(-5).map((message, index) => <div className={'jarvis-message ' + message.role} key={index}><span>{message.role === 'you' ? 'YOU' : 'JARVIS'}</span><p>{message.text}</p></div>)}</div>}
            {pendingWeb && <div className="jarvis-approval"><div className="jarvis-approval-icon"><Globe size={18} /></div><div className="jarvis-approval-copy"><strong>Internet access requested</strong><p>Command: “{pendingWeb}”</p><small>This prototype does not make network requests. Approval only changes the demo state.</small></div><button onClick={() => { setPendingWeb(null); setMessages((items) => [...items, { role: 'jarvis', text: 'Approval recorded for this request in the prototype. No internet request was made.' }]); }}><Check size={15} /> Approve demo</button><button className="jarvis-deny" onClick={() => { setPendingWeb(null); setMessages((items) => [...items, { role: 'jarvis', text: 'Internet request declined. Staying offline.' }]); }}>Deny</button></div>}
          </section>

          <footer className="jarvis-footer"><span><ShieldCheck size={14} /> PRIVACY-FIRST BY DESIGN</span><span>LOCAL AI · HUMAN-APPROVED ACTIONS</span></footer>
        </section>
      </div>
    </main>
  );
}
