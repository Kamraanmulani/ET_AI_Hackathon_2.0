import { useState } from 'react';
import { Link } from 'react-router-dom';
import {
  ArrowRight,
  Bot,
  ChevronRight,
  ClipboardCheck,
  FileSearch,
  GitBranch,
  Menu,
  Network,
  ScanSearch,
  ShieldCheck,
  X,
} from 'lucide-react';

const workflow = [
  { icon: FileSearch, title: 'Ingest', text: 'Structured and unstructured plant records enter one controlled corpus.' },
  { icon: Network, title: 'Connect', text: 'Tags, document evidence, and P&ID context connect around each asset.' },
  { icon: ClipboardCheck, title: 'Review', text: 'Engineers verify uncertain OCR and relationship proposals.' },
  { icon: Bot, title: 'Ask', text: 'The Copilot returns cited evidence or abstains when support is insufficient.' },
];

const capabilities = [
  { icon: ScanSearch, title: 'Universal document intelligence', text: 'Bring drawings, maintenance records, procedures, inspections, and handovers into one searchable layer.' },
  { icon: GitBranch, title: 'P&ID-linked Asset 360', text: 'Move from an equipment tag to connected drawing context and document evidence without losing traceability.' },
  { icon: ShieldCheck, title: 'Human-in-the-loop verification', text: 'Keep uncertain extraction separate from reviewed evidence so engineers stay in control of trust.' },
  { icon: Bot, title: 'Grounded Expert Copilot', text: 'Ask across the connected corpus and inspect the cited source behind every supported answer.' },
  { icon: Network, title: 'Knowledge graph relationships', text: 'Follow verified asset, drawing, document, and evidence relationships across functional silos.' },
  { icon: FileSearch, title: 'Field-ready evidence access', text: 'Give technicians concise, mobile-friendly paths back to the records that support a decision.' },
];

const previews = [
  { id: 'drawing', label: 'P&ID Explorer', image: '/screenshots/step1-pid.png', alt: 'Pragyan P and ID Explorer with ETP-601 context', eyebrow: 'Drawing context', title: 'Start with the asset where the process is visible.', text: 'Inspect a P&ID, select a tagged asset, and carry its context into the evidence workflow.' },
  { id: 'asset', label: 'Asset 360', image: '/screenshots/step2-asset360.png', alt: 'Pragyan Asset 360 evidence view', eyebrow: 'Connected evidence', title: 'Bring related records together around the asset.', text: 'Verified relationships, proposed evidence, and audit history remain distinct and inspectable.' },
  { id: 'review', label: 'Review Queue', image: '/screenshots/step3-review.png', alt: 'Pragyan review queue for document evidence', eyebrow: 'Engineer review', title: 'Keep the human decision inside the knowledge loop.', text: 'Review uncertain document extraction before it becomes trusted operational context.' },
];

function LandingHeader() {
  const [open, setOpen] = useState(false);
  const closeMenu = () => setOpen(false);

  return (
    <header className="landing-header">
      <Link className="landing-brand" to="/" aria-label="Pragyan Plant Intelligence home">
        <span className="landing-brand-mark" aria-hidden="true"><Network size={18} /></span>
        <span>Pragyan Plant Intelligence</span>
      </Link>
      <button type="button" className="landing-menu-button" aria-label={open ? 'Close navigation menu' : 'Open navigation menu'} aria-expanded={open} onClick={() => setOpen((current) => !current)}>
        {open ? <X size={20} /> : <Menu size={20} />}
      </button>
      <nav className={`landing-nav${open ? ' is-open' : ''}`} aria-label="Landing navigation">
        <a href="#platform" onClick={closeMenu}>Platform</a>
        <a href="#evidence" onClick={closeMenu}>Evidence Intelligence</a>
        <a href="#workflow" onClick={closeMenu}>Workflow</a>
        <Link className="landing-nav-cta" to="/overview" onClick={closeMenu}>Open Workspace <ArrowRight size={16} aria-hidden="true" /></Link>
      </nav>
    </header>
  );
}

export default function LandingPage() {
  const [activePreview, setActivePreview] = useState(previews[0].id);
  const preview = previews.find((item) => item.id === activePreview) || previews[0];

  return (
    <div className="landing-page">
      <LandingHeader />
      <main>
        <section className="landing-hero" aria-labelledby="landing-title">
          <img className="landing-hero-image" src="/landing/effluent-treatment-plant.png" alt="Effluent treatment plant P and ID drawing" />
          <div className="landing-hero-wash" aria-hidden="true" />
          <div className="landing-shell landing-hero-content">
            <p className="landing-kicker">Industrial Knowledge Intelligence</p>
            <h1 id="landing-title">Pragyan Plant Intelligence</h1>
            <p className="landing-hero-copy">Connect drawings, maintenance history, inspections, procedures, and handovers into evidence engineers can use at the point of need.</p>
            <div className="landing-actions">
              <Link className="landing-button landing-button-primary" to="/overview">Open Workspace <ArrowRight size={18} aria-hidden="true" /></Link>
              <Link className="landing-button landing-button-secondary" to="/assets/ETP-601">Explore Asset Intelligence <ChevronRight size={18} aria-hidden="true" /></Link>
            </div>
          </div>
        </section>

        <section className="landing-signal" aria-label="Plant information sources">
          <div className="landing-shell">
            <p className="landing-kicker">From fragmentation to context</p>
            <div className="landing-signal-layout">
              <div><h2>Plant knowledge is scattered. Decisions should not be.</h2><p>Pragyan turns disconnected operational records into a connected asset knowledge layer without obscuring the source behind an answer.</p></div>
              <div className="landing-source-flow" aria-label="Document sources connected to one asset knowledge layer">
                <div className="landing-source-list">{['Drawings', 'Work orders', 'Inspections', 'Procedures', 'Incidents', 'Handovers'].map((source) => <span key={source}>{source}</span>)}</div>
                <div className="landing-connection-line" aria-hidden="true" />
                <div className="landing-knowledge-node"><Network size={24} aria-hidden="true" /><strong>Connected asset knowledge</strong><small>Evidence stays linked to its source.</small></div>
              </div>
            </div>
          </div>
        </section>

        <section id="workflow" className="landing-section landing-workflow" aria-labelledby="workflow-title">
          <div className="landing-shell">
            <div className="landing-section-heading"><div><p className="landing-kicker">Operational workflow</p><h2 id="workflow-title">From document intake to an evidence-backed answer.</h2></div><p>Designed to keep source context, review state, and asset relationships visible at every handoff.</p></div>
            <ol className="landing-workflow-list">{workflow.map(({ icon: Icon, title, text }, index) => <li key={title} className="landing-workflow-step"><div className="landing-step-number">0{index + 1}</div><Icon size={22} aria-hidden="true" /><h3>{title}</h3><p>{text}</p></li>)}</ol>
          </div>
        </section>

        <section id="evidence" className="landing-section landing-evidence" aria-labelledby="evidence-title">
          <div className="landing-shell">
            <div className="landing-section-heading"><div><p className="landing-kicker">Evidence-first workspace</p><h2 id="evidence-title">Follow the answer back to the plant record.</h2></div><p>Each product surface moves from a question or asset tag to evidence an engineer can inspect.</p></div>
            <div className="landing-preview-tabs" role="tablist" aria-label="Product previews">{previews.map((item) => <button key={item.id} type="button" role="tab" aria-selected={activePreview === item.id} className={activePreview === item.id ? 'is-active' : ''} onClick={() => setActivePreview(item.id)}>{item.label}</button>)}</div>
            <div className="landing-preview-stage">
              <div className="landing-preview-copy"><p className="landing-kicker">{preview.eyebrow}</p><h3>{preview.title}</h3><p>{preview.text}</p><Link to="/assets/ETP-601" className="landing-inline-link">View ETP-601 Asset 360 <ArrowRight size={16} aria-hidden="true" /></Link></div>
              <div className="landing-preview-image-wrap"><img src={preview.image} alt={preview.alt} className="landing-preview-image" /></div>
            </div>
            <p className="landing-evidence-path">Question <span aria-hidden="true">to</span> linked asset <span aria-hidden="true">to</span> source evidence <span aria-hidden="true">to</span> reviewable result</p>
          </div>
        </section>

        <section id="platform" className="landing-section landing-capabilities" aria-labelledby="capabilities-title">
          <div className="landing-shell">
            <div className="landing-section-heading"><div><p className="landing-kicker">The Pragyan platform</p><h2 id="capabilities-title">Built for industrial knowledge that has to stand up to review.</h2></div><p>One operational layer for document intelligence, linked asset context, and source-backed discovery.</p></div>
            <div className="landing-capability-grid">{capabilities.map(({ icon: Icon, title, text }) => <article className="landing-capability" key={title}><Icon size={22} aria-hidden="true" /><h3>{title}</h3><p>{text}</p></article>)}</div>
          </div>
        </section>

        <section className="landing-field-band" aria-labelledby="field-title"><div className="landing-shell landing-field-layout"><div><p className="landing-kicker">Built for the point of need</p><h2 id="field-title">A single evidence path, from engineer desk to field task.</h2><div className="landing-field-list"><div><strong>Engineer desk</strong><span>Explore P&IDs and connected asset evidence.</span></div><div><strong>Maintenance review</strong><span>Validate uncertain extraction before it becomes trusted context.</span></div><div><strong>Field access</strong><span>Open concise citations and source evidence on a mobile workflow.</span></div></div></div><div className="landing-field-screen"><img src="/screenshots/step2-asset360.png" alt="Asset 360 view for evidence inspection" /></div></div></section>

        <section className="landing-closing" aria-labelledby="closing-title"><div className="landing-shell"><p className="landing-kicker">Pragyan Plant Intelligence</p><h2 id="closing-title">Make plant knowledge usable when it matters.</h2><p>Explore evidence, assets, drawings, and grounded answers in the live workspace.</p><Link className="landing-button landing-button-primary" to="/overview">Enter Pragyan Workspace <ArrowRight size={18} aria-hidden="true" /></Link></div></section>
      </main>
      <footer className="landing-footer"><div className="landing-shell"><div><strong>Pragyan Plant Intelligence</strong><span>Industrial Knowledge Intelligence</span></div><Link to="/overview">Open Workspace <ArrowRight size={15} aria-hidden="true" /></Link></div></footer>
    </div>
  );
}
