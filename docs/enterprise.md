# SecretZero Enterprise — Managed & Self-Hosted Plans

The open-source SecretZero you love, now with enterprise-grade scale, compliance, and zero-ops management for teams building agentic AI and non-human identities.

Built on the same trusted open-source core, SecretZero Enterprise adds the controls, reliability, and governance that platform and security teams need in production.

## Open Source vs Enterprise

| Feature                                      | Open Source                  | Enterprise Self-Hosted                  | SecretZero Cloud (SaaS)                  |
|----------------------------------------------|------------------------------|-----------------------------------------|------------------------------------------|
| Git-native Secretfile.yml + lockfile         | Yes                          | Yes                                     | Yes                                      |
| Agent sync & web-assisted seeding (Entra Agent ID, etc.) | Yes                          | Yes                                     | Yes                                      |
| Basic drift detection & rotation             | Yes                          | Yes                                     | Yes                                      |
| Local AI discovery (Ollama)                  | Yes                          | Yes                                     | Yes                                      |
| Multi-repo / fleet management                | Limited                      | Yes                                     | Yes                                      |
| SOC 2 / ISO 27001 ready audit logs & reports | No                           | Yes                                     | Yes                                      |
| SSO + SCIM + fine-grained RBAC               | No                           | Yes                                     | Yes                                      |
| Centralized secret discovery & remediation at scale | Local only                   | Yes                                     | Yes                                      |
| Zero-downtime coordinated rotation orchestration | Basic                        | Yes                                     | Yes                                      |
| SLA-backed support & onboarding              | Community                    | Yes                                     | Yes                                      |
| Hosted control plane (no self-managed infra) | No                           | No                                      | Yes                                      |
| Agent Identity Control Plane (Entra, SPIFFE, etc.) | Basic                        | Yes                                     | Yes                                      |
| Usage analytics & secret sprawl reports      | No                           | Yes                                     | Yes                                      |
| Air-gapped / on-prem deployment              | No                           | Yes                                     | No                                       |
| Custom HSM & marketplace connectors          | Limited                      | Yes                                     | Yes                                      |

## Killer Features

- Fully managed SaaS control plane with scheduled syncs, webhooks, and multi-repo dashboard
- Enterprise compliance suite (immutable audit logs, SIEM export, automated SOC 2 / ISO reports)
- Advanced identity governance, just-in-time access, and sponsorship workflows
- Fleet-wide secret discovery with auto-Secretfile.yml generation
- Coordinated enterprise rotations with canary testing and rollback
- Self-hosted High-Availability edition with license enforcement
- Dedicated Agent Identity management across multiple frameworks (Entra Agent ID and beyond)
- Usage analytics, cost optimization, and secret sprawl insights
- Premium SLA-backed support and optional professional services

## Deployment Options

### SecretZero Cloud (SaaS)

- Managed control plane, no infrastructure operations
- Fastest onboarding for multi-team environments
- Ideal when you need centralized visibility quickly

### Enterprise Self-Hosted

- Deployed in your network or private cloud
- Supports regulated, sovereign, and air-gapped requirements
- High-availability options with enterprise support

## Join the Waitlist

Join 50+ security and platform teams already exploring SecretZero Enterprise.

<form action="https://formspree.io/f/xrbkgzpa" method="POST">
  <p>
    <label for="full_name">Full Name</label><br />
    <input id="full_name" name="full_name" type="text" required />
  </p>
  <p>
    <label for="email">Email</label><br />
    <input id="email" name="email" type="email" required />
  </p>
  <p>
    <label for="company">Company</label><br />
    <input id="company" name="company" type="text" required />
  </p>
  <p>
    <label for="role_use_case">Role/Use Case</label><br />
    <textarea id="role_use_case" name="role_use_case" rows="4" placeholder="Tell us how you plan to use SecretZero Enterprise." required></textarea>
  </p>
  <p>
    <label for="preferred_deployment">Preferred Deployment</label><br />
    <select id="preferred_deployment" name="preferred_deployment" required>
      <option value="">Select one</option>
      <option value="self_hosted">Self-Hosted</option>
      <option value="saas">SaaS</option>
      <option value="not_sure">Not Sure</option>
    </select>
  </p>
  <p>
    <button type="submit">Join the Waitlist</button>
  </p>
</form>

## Community-First Promise

SecretZero Enterprise is designed to extend, not replace, open source. The open-source project remains the foundation, and enterprise capabilities build on the same transparent, Git-native workflow.
