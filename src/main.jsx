import { StrictMode, useEffect, useState } from 'react'
import { createRoot } from 'react-dom/client'
import {
  ArrowUpRight,
  BrainCircuit,
  Check,
  ChevronDown,
  CircleDot,
  Code2,
  Database,
  Download,
  Github,
  Layers3,
  Linkedin,
  Mail,
  MapPin,
  Menu,
  Network,
  Orbit,
  Send,
  Sparkles,
  Terminal,
  X,
} from 'lucide-react'
import './styles.css'

const navItems = ['About', 'Skills', 'Experience', 'Projects', 'Contact']

const skillGroups = [
  { icon: Terminal, title: 'Languages & data', accent: 'cyan', items: ['Python', 'SQL', 'DSA', 'NumPy', 'Pandas', 'Matplotlib', 'Seaborn'] },
  { icon: BrainCircuit, title: 'AI / machine learning', accent: 'violet', items: ['Machine Learning', 'Deep Learning', 'NLP', 'LLMs', 'Embeddings', 'PyTorch', 'Transformers', 'scikit-learn'] },
  { icon: Network, title: 'GenAI & retrieval', accent: 'lime', items: ['RAG', 'Hugging Face', 'LangChain', 'LangGraph', 'FAISS', 'Multi-agent systems', 'Knowledge graphs', 'Neo4j'] },
  { icon: Layers3, title: 'Production toolkit', accent: 'orange', items: ['FastAPI', 'Docker', 'MLflow', 'DVC', 'AWS', 'CI/CD', 'Git & GitHub', 'Jupyter / VS Code'] },
]

const timeline = [
  { date: '2024 — 2027', title: 'B.Tech, Computer Science & Engineering — AI & ML', org: 'Brainware University', detail: 'Building depth across machine learning, deep learning, NLP, generative AI, databases, and statistical analysis.' },
  { date: '2021 — 2024', title: 'Diploma, Computer Science & Engineering', org: 'Brainware University', detail: 'CGPA 6.5 / 10 · Core foundation in programming, data structures, databases, and software development.' },
  { date: '2021', title: 'Higher Secondary (H.S.)', org: 'Barrackpore A. B. Model High School', detail: 'WBBSE · 67%' },
]

function App() {
  const [menuOpen, setMenuOpen] = useState(false)
  const [activeSection, setActiveSection] = useState('home')

  useEffect(() => {
    const onScroll = () => {
      const sections = [...document.querySelectorAll('main section[id]')]
      const current = sections.find((section) => window.scrollY >= section.offsetTop - 180)
      if (current) setActiveSection(current.id)
    }
    window.addEventListener('scroll', onScroll, { passive: true })
    onScroll()
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  const closeMenu = () => setMenuOpen(false)

  return (
    <div className="site-shell">
      <div className="ambient ambient-one" />
      <div className="ambient ambient-two" />
      <header className="site-header">
        <a className="brand" href="#home" onClick={closeMenu} aria-label="Rohit Paul home">
          <span className="brand-mark">RP</span>
          <span>rohit<span className="brand-dot">.</span>paul</span>
        </a>
        <button className="menu-toggle" onClick={() => setMenuOpen(!menuOpen)} aria-label={menuOpen ? 'Close menu' : 'Open menu'} aria-expanded={menuOpen}>
          {menuOpen ? <X size={21} /> : <Menu size={21} />}
        </button>
        <nav className={`main-nav ${menuOpen ? 'is-open' : ''}`} aria-label="Main navigation">
          {navItems.map((item) => {
            const id = item.toLowerCase()
            return <a key={item} href={`#${id}`} className={activeSection === id ? 'active' : ''} onClick={closeMenu}>{item}</a>
          })}
          <a className="nav-resume" href="/rohit-paul-cv.txt" download>Resume <Download size={14} /></a>
        </nav>
      </header>

      <main>
        <section className="hero section-wrap" id="home">
          <div className="hero-copy">
            <div className="eyebrow"><span className="eyebrow-line" /> AI / ML ENGINEER <span className="status-dot" /> OPEN TO OPPORTUNITIES</div>
            <h1>Turning <em>intelligence</em><br />into <span className="outlined">impact.</span></h1>
            <p className="hero-lede">I’m Rohit — a fresher AI/ML engineer exploring the space where <strong>language, knowledge, and systems</strong> meet.</p>
            <div className="hero-actions">
              <a className="button button-primary" href="#projects">See my work <ArrowUpRight size={17} /></a>
              <a className="button button-ghost" href="mailto:rohgaming01@gmail.com">Let’s connect <Mail size={16} /></a>
            </div>
            <div className="hero-meta">
              <span><MapPin size={15} /> India</span>
              <span className="meta-divider" />
              <span>Generative AI · NLP · Retrieval</span>
            </div>
          </div>
          <div className="hero-art" aria-hidden="true">
            <div className="orbital orbital-outer"><span className="orbit-node node-a" /><span className="orbit-node node-b" /></div>
            <div className="orbital orbital-middle"><span className="orbit-node node-c" /></div>
            <div className="core"><BrainCircuit size={54} strokeWidth={1.25} /></div>
            <div className="signal-card card-top"><span className="signal-icon"><Sparkles size={15} /></span><span>reasoning engine</span><strong>99.2%</strong></div>
            <div className="signal-card card-bottom"><CircleDot size={13} /><span>retrieval layer</span><span className="live-pill">LIVE</span></div>
            <span className="art-label label-one">01 / THINK</span><span className="art-label label-two">02 / RETRIEVE</span>
          </div>
          <a className="scroll-cue" href="#about"><span>Scroll to explore</span><ChevronDown size={16} /></a>
        </section>

        <section className="about section-wrap" id="about">
          <div className="section-kicker">01 — THE HUMAN BEHIND THE MODELS</div>
          <div className="about-grid">
            <div><h2>Curious by default.<br /><span>Rigorous by design.</span></h2></div>
            <div className="about-copy">
              <p>I’m an AI/ML Engineer with a foundation across <strong>Python, machine learning, deep learning, NLP, and LLMs</strong>. I enjoy taking an ambiguous problem, finding the signal inside it, and shaping a system that can be trusted.</p>
              <p>Right now, I’m focused on reliable retrieval systems, knowledge graphs, and agentic workflows — making AI outputs more grounded, traceable, and useful in the real world.</p>
              <div className="about-facts"><div><span className="fact-number">04+</span><span>AI domains explored</span></div><div><span className="fact-number">01</span><span>flagship system in progress</span></div><div><span className="fact-number">∞</span><span>questions to investigate</span></div></div>
            </div>
          </div>
        </section>

        <section className="skills section-wrap" id="skills">
          <div className="section-heading"><div><div className="section-kicker">02 — MY TOOLBOX</div><h2>Built to go from <span>notebook to north star.</span></h2></div><p>Tools are only useful when they help ideas travel further. This is the stack I use to get there.</p></div>
          <div className="skill-grid">{skillGroups.map(({ icon: Icon, title, accent, items }) => <article className={`skill-card ${accent}`} key={title}><div className="skill-icon"><Icon size={21} /></div><h3>{title}</h3><div className="tag-list">{items.map((item) => <span key={item}>{item}</span>)}</div></article>)}</div>
        </section>

        <section className="experience section-wrap" id="experience">
          <div className="section-kicker">03 — THE ROAD SO FAR</div>
          <div className="experience-heading"><h2>Learning in <span>layers.</span></h2><p>Every chapter adds a new way to frame the problem.</p></div>
          <div className="timeline">{timeline.map((item, index) => <article className="timeline-item" key={item.title}><div className="timeline-marker"><span>0{index + 1}</span></div><div className="timeline-date">{item.date}</div><div className="timeline-content"><h3>{item.title}</h3><p className="timeline-org">{item.org}</p><p>{item.detail}</p></div></article>)}</div>
        </section>

        <section className="projects section-wrap" id="projects">
          <div className="section-kicker">04 — SELECTED PROJECT</div>
          <article className="project-feature">
            <div className="project-visual"><div className="visual-grid" /><div className="graph-line line-one" /><div className="graph-line line-two" /><div className="graph-node graph-main"><Database size={22} /><span>GraphMind</span></div><div className="graph-node graph-small small-one">PDF</div><div className="graph-node graph-small small-two">FAISS</div><div className="graph-node graph-small small-three">Neo4j</div><div className="visual-caption">EVIDENCE / RETRIEVAL / REASONING</div></div>
            <div className="project-copy"><div className="project-type"><Sparkles size={15} /> FLAGSHIP BUILD</div><h2>GraphMind<span>.</span></h2><h3>Scientific Literature QA System</h3><p>A research assistant in progress — combining RAG, vector search, knowledge graphs, and multi-agent systems to turn dense scientific PDFs into answers that show their work.</p><div className="project-points"><span><Check size={14} /> PDF processing & chunking</span><span><Check size={14} /> Evidence-grounded verification</span><span><Check size={14} /> Citation tracking & graph reasoning</span></div><div className="project-stack">{['Python', 'RAG', 'FAISS', 'Neo4j', 'LangGraph'].map((item) => <span key={item}>{item}</span>)}</div><span className="project-status"><span /> Currently developing</span></div>
          </article>
        </section>

        <section className="education section-wrap">
          <div className="education-card"><div><div className="section-kicker">05 — LEARNING NEVER STOPS</div><h2>Certified curiosity.</h2></div><div className="cert-detail"><div className="cert-seal"><Orbit size={22} /></div><div><h3>Elements of AI</h3><p>University of Helsinki · September 2026</p><small>Credential ID: 6tfcqp4lrry</small></div></div><div className="coursework"><span>Coursework</span><p>ML · DL · NLP · GenAI · LLMs · DSA · DBMS · Python · Statistics / Data Analysis</p></div></div>
        </section>

        <section className="contact section-wrap" id="contact">
          <div className="contact-card"><div className="contact-copy"><div className="section-kicker">06 — HAVE A QUESTION?</div><h2>Let’s make<br /><span>something meaningful.</span></h2><p>Whether you want to talk about an AI idea, a collaboration, or the future of intelligent systems — my inbox is open.</p><a className="email-link" href="mailto:rohgaming01@gmail.com">rohgaming01@gmail.com <ArrowUpRight size={17} /></a></div><div className="contact-aside"><div className="contact-orb"><Send size={28} /></div><span>Available for meaningful<br />conversations.</span><div className="socials"><a href="mailto:rohgaming01@gmail.com" aria-label="Email Rohit"><Mail size={18} /></a><a href="https://github.com/" target="_blank" rel="noreferrer" aria-label="GitHub placeholder"><Github size={18} /></a><a href="https://www.linkedin.com/" target="_blank" rel="noreferrer" aria-label="LinkedIn placeholder"><Linkedin size={18} /></a></div></div></div>
        </section>
      </main>
      <footer><span>© 2026 Rohit Paul</span><span>Designed & built with intention <span className="footer-heart">✦</span></span><a href="#home">Back to top ↑</a></footer>
    </div>
  )
}

createRoot(document.getElementById('root')).render(<StrictMode><App /></StrictMode>)
