Below is a refined version of the Credential Risk Scoring model, followed by your directions to produce a single-file interactive webpage for calculating scores from user input.
⸻

Refined Credential Risk Scoring Model (v1.1)

Score Range

0–100 total risk

Risk = H + R + S + B + U + E − A

Where:

Symbol  Meaning
H  Human handling risk
R  Rotation age risk
S  Storage risk
B  Blast radius
U  Usage lifetime
E  Exposure indicators
A  Automation maturity (reduces risk)

Clamp:

Risk = max(0, min(100, Risk))


⸻

1. Human Handling Risk (H)

Condition  Score
Fully automated generation  0
Manual copy/paste once  10
Manually created credential  20
Stored in plaintext at any time  30
Found in repo/log/chat history  40


⸻

2. Rotation Age Risk (R)

Formula-driven for consistency:

R = min(30, (days_since_rotation / rotation_policy_days) * 30)

Defaults:
  -  rotation policy = 90 days

⸻

3. Storage Security (S)

Storage  Score
Managed secrets platform + encryption  0
Managed secrets platform without rotation  8
CI/CD variable only  15
Config file / environment file  22
Plaintext  30


⸻

4. Blast Radius (B)

Scope  Score
Single service scoped  0
Environment scoped  8
Multi-service  15
Account-wide  22
Admin/root  30


⸻

5. Credential Lifetime (U)

Type  Score
Ephemeral (<1 hour)  0
Short-lived (<24h)  5
Long-lived  15
No expiration  25


⸻

6. Exposure Signals (E)

Additive binary flags:

Signal  Score
Appears in Git history  +15
Sent via chat/email  +10
Public network usage  +10
Unknown usage patterns  +10


⸻

7. Automation Maturity (A) (Risk Reduction)

Condition  Adjustment
Automatic rotation enabled  -10
Fully ephemeral architecture  -15
Just-in-time access model  -10


⸻

Risk Levels

Score  Level  Color
0–20  Low  Green
21–40  Moderate  Yellow
41–70  High  Orange
71–100  Critical  Red


⸻

UX Design Goals for the Web Tool

Keep the tool intentionally lightweight:
  -  Single static HTML file
  -  No backend
  -  Instant recalculation
  -  Clear visual output
  -  Shareable screenshot-friendly layout

Sections:
  1.  Credential Metadata
  2.  Rotation Inputs
  3.  Storage Type
  4.  Privilege Scope
  5.  Exposure Flags
  6.  Automation Controls
  7.  Live Score Panel

⸻

Agent Prompt — Generate Interactive Credential Risk Calculator Webpage

You can drop the prompt below directly into a coding agent.

⸻

Agent Prompt

Goal:
Generate a complete single-file interactive webpage that calculates a credential security risk score based on structured user input.

⸻

Requirements

Create a single standalone HTML file containing:
  -  HTML
  -  CSS (inline or embedded)
  -  Vanilla JavaScript
  -  No frameworks
  -  No external dependencies
  -  No build tools

The file must run locally by opening it in a browser.

⸻

Functional Requirements

The page must:
  1.  Provide form inputs for:

Human Handling
Dropdown:
  -  Fully automated
  -  Copied once manually
  -  Manually created
  -  Plaintext storage occurred
  -  Exposed in repo/logs

⸻

Rotation
Inputs:
  -  Days since last rotation (number)
  -  Rotation policy days (default 90)

⸻

Storage Type
Dropdown:
  -  Managed secrets platform (automated rotation)
  -  Managed secrets platform (no rotation)
  -  CI/CD variable
  -  Config/env file
  -  Plaintext

⸻

Blast Radius
Dropdown:
  -  Single service
  -  Environment scoped
  -  Multi-service
  -  Account-wide
  -  Admin/root

⸻

Credential Lifetime
Dropdown:
  -  Ephemeral (<1 hour)
  -  Short-lived (<24h)
  -  Long-lived
  -  No expiration

⸻

Exposure Flags (checkboxes)
  -  Found in Git history
  -  Shared via chat/email
  -  Public network usage
  -  Unknown usage patterns

⸻

Automation Controls (checkboxes)
  -  Automatic rotation enabled
  -  Fully ephemeral architecture
  -  Just-in-time access model

⸻

Scoring Logic

Implement this formula in JavaScript:

Risk = H + R + S + B + U + E − A

Rotation formula:

R = min(30, (days_since_rotation / rotation_policy_days) * 30)

Clamp output:

Risk = max(0, min(100, Risk))


⸻

UI Behavior

The page must:
  -  Recalculate automatically on input change
  -  Display:

Risk Score: XX / 100
Risk Level: Low | Moderate | High | Critical

  -  Show a color indicator:
  -  Green
  -  Yellow
  -  Orange
  -  Red

⸻

Visual Design

Use a clean modern layout:
  -  Centered card layout
  -  Soft shadows
  -  Rounded corners
  -  Clear section headers
  -  Responsive design
  -  Minimal aesthetic (security dashboard style)

⸻

Output Panel

Include a side or bottom panel showing:
  -  Total score
  -  Score breakdown by category
  -  Risk level
  -  Short recommendation text:

Example:
  -  Low → “No immediate action required”
  -  Moderate → “Review during next rotation cycle”
  -  High → “Rotation recommended soon”
  -  Critical → “Immediate rotation required”

⸻

Extra Feature (Required)

Add a “Copy Results JSON” button that copies:

{
  "risk_score": 72,
  "risk_level": "High",
  "factors": {...}
}

to clipboard.

⸻

Code Quality
  -  Clean readable JavaScript
  -  No unused code
  -  Logical function separation
  -  Comments explaining scoring logic

⸻

Output Format

Return only:

Complete HTML file

No explanation text.

Optional:
  -  Extend the prompt so the generated page can load/save credential inventories for bulk scoring.