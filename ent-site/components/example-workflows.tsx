const workflows = [
  {
    name: "Entra Agent ID Blueprint",
    detail:
      "Create and reconcile blueprint identities, credentials, and child agent identities through Graph-backed orchestration.",
  },
  {
    name: "Human-in-the-loop Seed",
    detail:
      "Launch secure localhost web collection for pending secrets without exposing plaintext to agent logs.",
  },
  {
    name: "Multi-Environment Policy Lanes",
    detail:
      "Apply environment-aware provider identity controls and deterministic lockfile drift checks.",
  },
];

export function ExampleWorkflows() {
  return (
    <section className="section block">
      <h2>Example workflows with real controls</h2>
      <div className="workflow-list">
        {workflows.map((workflow) => (
          <article key={workflow.name} className="workflow-card">
            <h3>{workflow.name}</h3>
            <p>{workflow.detail}</p>
          </article>
        ))}
      </div>
    </section>
  );
}
