import { HeroScene } from "../components/hero-scene";
import { WorkflowDiagrams } from "../components/workflow-diagrams";
import { ExampleWorkflows } from "../components/example-workflows";
import { WaitlistForm } from "../components/waitlist-form";

export default function Page() {
  return (
    <main className="page">
      <header className="top-nav">
        <a href="/" className="brand">
          SecretZero Enterprise
        </a>
        <a href="#waitlist" className="btn primary">
          Join waitlist
        </a>
      </header>

      <section className="hero">
        <div className="hero-text">
          <p className="eyebrow">Enterprise AI Agent Security</p>
          <h1>From secret-zero chaos to governed, auditable delivery.</h1>
          <p className="sub">
            Deploy secure agent identity and secret lifecycle workflows with human-safe seeding paths
            and policy-backed automation.
          </p>
          <div className="hero-actions">
            <a className="btn primary" href="#waitlist">
              Get launch updates
            </a>
            <a className="btn secondary" href="https://github.com/zloeber/SecretZero">
              Explore OSS core
            </a>
          </div>
        </div>
        <HeroScene />
      </section>

      <WorkflowDiagrams />
      <ExampleWorkflows />
      <WaitlistForm />
    </main>
  );
}
