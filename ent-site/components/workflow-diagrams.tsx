export function WorkflowDiagrams() {
  return (
    <section className="section block">
      <h2>Built-in workflow diagrams</h2>
      <p className="sub">
        Architecture and control loops are visible by default for platform and security reviewers.
      </p>
      <div className="diagram-grid">
        <article className="panel">
          <h3>Agent Sync Paths</h3>
          <svg viewBox="0 0 500 220" role="img" aria-label="Agent sync flow diagram">
            <defs>
              <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                <path d="M 0 0 L 10 5 L 0 10 z" fill="#38bdf8" />
              </marker>
            </defs>
            <rect x="20" y="28" width="140" height="46" rx="10" />
            <rect x="180" y="28" width="140" height="46" rx="10" />
            <rect x="340" y="28" width="140" height="46" rx="10" />
            <rect x="100" y="136" width="140" height="46" rx="10" />
            <rect x="260" y="136" width="140" height="46" rx="10" />
            <text x="90" y="55">Secretfile.yml</text>
            <text x="228" y="55">Agent Sync</text>
            <text x="378" y="55">Providers</text>
            <text x="132" y="163">Human Loop</text>
            <text x="295" y="163">Targets + Lock</text>
            <path d="M160 52 L180 52" markerEnd="url(#arrow)" />
            <path d="M320 52 L340 52" markerEnd="url(#arrow)" />
            <path d="M250 74 L250 128" markerEnd="url(#arrow)" />
            <path d="M200 160 L260 160" markerEnd="url(#arrow)" />
          </svg>
        </article>
        <article className="panel">
          <h3>Governance Loop</h3>
          <svg viewBox="0 0 500 220" role="img" aria-label="Governance loop diagram">
            <circle cx="250" cy="110" r="74" />
            <text x="212" y="115">Policy Core</text>
            <rect x="50" y="95" width="118" height="34" rx="9" />
            <text x="85" y="117">Author</text>
            <rect x="332" y="95" width="118" height="34" rx="9" />
            <text x="367" y="117">Deploy</text>
            <rect x="192" y="18" width="118" height="34" rx="9" />
            <text x="220" y="40">Drift</text>
            <rect x="192" y="168" width="118" height="34" rx="9" />
            <text x="213" y="190">Rotate</text>
            <path d="M167 112 C190 112 190 90 208 85" markerEnd="url(#arrow2)" />
            <path d="M292 85 C312 90 314 112 332 112" markerEnd="url(#arrow2)" />
            <path d="M250 52 L250 76" markerEnd="url(#arrow2)" />
            <path d="M250 144 L250 168" markerEnd="url(#arrow2)" />
            <defs>
              <marker id="arrow2" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto">
                <path d="M 0 0 L 10 5 L 0 10 z" fill="#f97316" />
              </marker>
            </defs>
          </svg>
        </article>
      </div>
    </section>
  );
}
