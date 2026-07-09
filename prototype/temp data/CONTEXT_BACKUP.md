# Fraud Detection Rule Agent — Full Context Backup

Read this first in any new session to get complete context without re-deriving it.
Last updated: 2026-07-08.

## What this project is
Synchrony (banking) **"Agentic AI Fraud Detection System Design"** project. This is
**application fraud** (new credit card / PayLater applications at origination), NOT
transaction/card-usage fraud. Source reference material (Confluence/spreadsheet/whiteboard
photos) lives in `C:\projects\udemy\Agentic_Projects\fraud_detection\` — that folder is
now reference-only; **the actual code lives here**, in
`capstone_project\fraude\`.

**Scope philosophy**: don't segment into Phase 1/Phase 2/MVP1/MVP2 buckets. Think about
the whole system across the full timeline as one connected design. Building can still be
incremental (we're currently stopped at Data Agent), but don't dismiss Detection Agent,
Deep Analysis Agent, Reasoning Agent, Analytical Execution Agent, or SageMaker/EMR as
"future, not applicable now" when discussing architecture.

**Keep this fully separate** from the unrelated RM/banker-prep narrative agent use case
that also lives somewhere under this same `capstone_project/` parent folder — different
engagement, different stakeholders, don't mix naming or architecture between them.

## Official component names — use these exactly
Per the team's real architecture diagram: "Hierarchical Supervisor + Mixture-of-Experts
(ReAct at the Leaves)". Do not use earlier guessed names ("Kafka Live Stats," "Redshift
Stats," "Compare/Anomaly," "AgentCore Runtime" as orchestrator, "Semantic Layer Fetch") —
all deprecated.

| Component | Role | Built? |
|---|---|---|
| **Hierarchical Supervisor** | Deterministic (confirmed NOT an LLM — "auditable routing, not LLM guesswork"). Given a `client_id`, retrieves the applicable fraud rule set from **Rules KB**. | Yes |
| **Rule Dispatcher** | Deterministic. Organizes the already-client-filtered rules for dispatch (currently thin pass-through/validation; room for future ordering/grouping logic). | Yes |
| **MoE Gate** | Deterministic. Per rule, decides which agents AND which specific skill/Hard Logic tool to invoke — reads off each rule's own `required_agents` + `skill_type` fields (a lookup, not a decision made up on the fly). "Invokes only the experts each rule needs" — controls cost/latency/blast radius. | Yes |
| **Data Agent** | Retrieves data from Redshift and creates the baseline matrix. Calls **Metrics/Schema KB** ("how do I build the baseline matrix for Client X using Rule Y?") → SQL template + metric definition → executes via **Hard Logic Tool layer** (RedshiftExecutor) → Redshift → Baseline Matrix. | Yes |
| **Feature Curation Agent** | Works on temporary/short-term (live) data, calculates the current/temporary matrix — the live-data counterpart to Data Agent's baseline. | No |
| **Comparison Agent** | Creates the comparison between the baseline matrix and the current matrix. | No |
| **Statistical Testing Agent** | Executes the specific Hard Logic skill a rule needs (UCL, PSI, chi-square, rate-ratio, ...). | No — registry placeholder built |
| **Real-Time Signal Agent** | Packages Comparison Agent's result into a severity-tagged, alert-ready signal. | No |
| **Rules KB / Metrics-Schema KB / Historical-Insights KB** | Three distinct Bedrock Knowledge Bases, each queried by whichever agent needs that kind of instruction — never a shared single KB call. | Rules KB + Metrics/Schema KB wired (mock + real path); Historical-Insights KB not used yet |
| **Detection Agent, Deep Analysis Agent** | ReAct-based — genuine LLM reasoning loops. **The only two components in the whole architecture confirmed to need an LLM.** For rules needing dynamic/adaptive investigation (likely 3/9/12/15, identity-clustering). | No |
| **Alert Decision, Status/Case Log, Report Agent, Notification Agent** | Decision & Output Layer. | No |

## Confirmed architecture principles
- **Entire dispatch pipeline is deterministic, no LLM**: Supervisor → Rule Dispatcher →
  MoE Gate → Data Agent → (planned) Feature Curation → Comparison → Statistical Testing →
  Real-Time Signal. Matches the diagram's own "ReAct leaves only" legend — only
  Detection/Deep Analysis are marked ReAct, everything else is "code-based hard logic
  kept outside the LLM."
- **Strands framework used only where genuine LLM reasoning is needed — not everywhere.**
  Supervisor and Data Agent are plain Python (no Strands, no BedrockModel) because
  they're confirmed deterministic and their KB responses are structured, needing no LLM
  interpretation. This doesn't contradict the general "always use Strands, never raw
  invoke_model" preference — that rule is about not hand-rolling
  `bedrock-runtime.invoke_model()` when a model call IS needed; the boto3 calls here are
  to `bedrock-agent-runtime` (KB) and `redshift-data`, not model invocation at all.
  Strands will be used once Detection Agent/Deep Analysis Agent get built.
- **Trigger cadence: EventBridge fires every 3 hours** (not 15 min as first assumed).
  Window size (how much data each check aggregates) is a separate, still-unconfirmed
  question — don't conflate cadence and window size.
- **No ML/z-score-via-model** — arithmetic only (UCL, PSI, chi-square, rate-ratio).
  SageMaker/EMR explicitly separate, called externally if ever used, never run inside
  an agent.
- **"Reliable math stays outside the LLM"** — the Hard Logic Tool layer is where
  KB-supplied instructions actually execute; the KB itself never executes anything, only
  returns instructions/definitions.

## Knowledge Base findings (confirmed 2026-07-08)
- **Rules KB** (Supervisor calls this): rule definitions, thresholds,
  **applicable_portfolios** (which `client_id`s a rule applies to — e.g. rule 5 excludes
  Amazon PL), **severity**. Content is plain CSV/text (seeded from
  `kb_seed/rules_seed.csv`), NOT JSON — the parser tries JSON first, then falls back to
  raw CSV-row parsing. Query TO the KB is natural language; the response is structured,
  no LLM interpretation step needed on the response side (explicitly confirmed).
- **Metrics/Schema KB** (Data Agent calls this): metric definitions, SQL templates,
  aggregation logic, feature definitions, table relationships. Uses **NL2SQL** — natural
  language question ("I need the SQL to build the baseline matrix for Client X using
  Rule Y") → AWS Bedrock's `generate_query` API → SQL + schema + table names + joins +
  metric definition. Backed by AWS's real "structured data retrieval"/curated-queries
  feature (confirmed via AWS docs) — likely what the team calls "the Semantic Layer
  holds pre-written SQL."
- **Historical/Insights KB**: baseline definitions, historical metric metadata, business
  documentation. Not called by anything built yet.
- **Generic pattern, every agent**: `Agent → KB lookup → retrieve config/SQL
  template/metric definition → Hard Logic Code Tool → execute against Redshift → return
  matrix/result`. KB never executes; Hard Logic Tools never define.
- **Semantic Layer ownership**: likely owned by another (unnamed) team, not the Rule
  Agent team — treat all 3 KBs as an external dependency you consume but don't maintain.

## Code state — where everything actually is
**Location**: `capstone_project\fraude\` (this file's parent's parent folder). Moved
here from `fraud_detection/rule_agent/` — that old location is now empty, ignore it.

```
interfaces/          AgentInterface, SkillInterface, KBServiceInterface (ABCs)
agent_framework/      BaseAgent (shared scaffolding, no LLM by default)
kb_service/           RulesKBService, MetricsSchemaKBService (real boto3 + mock fallback each)
moe_gate/             RuleDispatcher + MoEGate (two separate files)
skills/               EMPTY + registry.py (register_skill/get_skill by skill_type) - populate when Statistical Testing Agent is built
hard_logic_tools/     RedshiftExecutor (the execution layer)
agents/               Supervisor, DataAgent (plain Python, no Strands - see above)
kb_seed/              rules_seed.csv (ready-to-upload seed for rules 1/3/5) + README.md
main.py               entrypoint: python main.py --client-id <ID> [--rule-id <ID>]
inspect_rules_kb.py   debug helper - raw retrieve() output, use before trusting the parser
config.py, models.py  shared config/data-contracts
.env.example          config template incl. per-service mock flags
```

**Per-service mock flags** (`config.py`) — NOT one global switch, because rollout is
incremental: `RULES_KB_MOCK`, `METRICS_SCHEMA_KB_MOCK`, `REDSHIFT_MOCK` (each defaults
true; `MOCK_MODE` still works as a legacy default-for-all-three). Lets you flip Rules KB
live while Metrics/Schema KB and Redshift stay mocked, etc.

**Verified working** (mock mode): `python main.py --client-id AMAZON_PL` and
`--client-id SYF_BNPL --rule-id 5` both run correctly end-to-end, including portfolio
filtering (rule 5 excluded for Amazon PL, included for SYF_BNPL/Care Credit) and correct
errors for inapplicable rule/client combos. CSV-row parser fallback tested directly.

**Testing flow for a real Rules KB**: set `RULES_KB_ID` + `RULES_KB_MOCK=false` in
`.env`, leave the other two mocked. Run `inspect_rules_kb.py --client-id X` FIRST to see
the raw chunk text before trusting the parser — adjust `_parse_as_json`/
`_parse_as_csv_row` in `kb_service/rules_kb_service.py` if neither matches.

**User is actively provisioning AWS incrementally**: creating the real Rules KB now;
Redshift connection details next. Expect to keep flipping mock flags off one at a time.

**Not built yet, in likely order**: Feature Curation Agent → Comparison Agent →
Statistical Testing Agent (+ first real skill, e.g. UCL for rule 1, via
`skills/registry.py`) → Real-Time Signal Agent → Decision & Output layer → Detection/Deep
Analysis Agent (first real Strands usage in this project).

## The real rule catalog — 16 rules total, only 3 have real logic
- **Rule 1 (unexplained application volume spike)** — fully defined. SQL:
  `select client_id, entered_date, hour(entered_dttm) as apphour, via_code, count(*) as
  apps from application_fact where client_limit_amt>0 group by client_id, entered_date,
  apphour, via_code;`. Real backtest: "Amazon PL attack" — TNF rate <20bps baseline →
  44bps (Nov'25) → 176bps (Dec'25) → 1678bps (Jan'26), `client_id='SYF BNPL'`, merchant
  code `PSCC_MERCHANT_CODE='6097688300000018'`. Statistical mechanism: **UCL (Upper
  Control Limit)** test, `skill_type="UCL"`.
- **Rule 3 (IP/device/email/phone velocity)** — vendor risk/evidence code matching
  (iOvation `IOV_VELOCITY`/`IOV_TRUST_NETWORK`/decline codes GO3/DD98, SentiLink insight
  codes, Synchrony's own `SYNAPPS_ATTR_23`), NOT a statistical test —
  `skill_type="VENDOR_CODE_MATCH"`. Real backtests: "One Pay attack", "Floor & Décor
  attack".
- **Rule 5 (small segment becomes unusually large)** — Prove vendor fields
  (`PFT_CARRIER`, `PFT_REASON_CODE`, SIM-association `PAYF_ATTR11-12`). **NOT APPLICABLE
  FOR AMAZON PL** (encoded in `kb_seed/rules_seed.csv`); G1/G2 data only from Feb 2026.
  Likely **PSI**, `skill_type="PSI"`.
- **Rules 2, 4, 6–16**: no real logic defined by the team yet — their own gap.
- **Vendor sources**: SentiLink, iOvation, Prove, Synchrony's own `SYNAPPS_ATTR_*`.
- **Attribute list still team-owned open item** — "Maggie and David team to define."

## Outstanding open items
- Kafka on-prem→AWS connectivity (Richard/James/Rob) and Kafka≠Oracle≠Redshift naming
  mismatch (Shaoyen) — in progress, not blocking (Data Agent doesn't touch Kafka).
- Baseline Matrix bucketing shape (flat vs. day-of-week/hour) — open.
- 13 of 16 rules still need real logic from the team.
- Statistical mechanism beyond rules 1/3/5 — unresolved; UCL/PSI/chi-square/rate-ratio
  are the confirmed named techniques so far, don't assume z-score elsewhere.
- Window size for the 3-hourly trigger — separate from confirmed 3hr cadence.
- Whether Metrics/Schema KB's NL2SQL is literally AWS's native `generate_query` or a
  custom pipeline — strong hypothesis, unconfirmed.
- Which team owns the Semantic Layer/KBs day-to-day — unknown.

## How to pick this up in a brand-new session
1. Read this file in full.
2. Check `capstone_project/fraude/` directly for current code state (this doc should
   match it, but the code is the source of truth if they ever diverge).
3. Ask the user what's changed since this was last updated (new AWS resources
   provisioned, new rule logic from the team, etc.) before assuming anything is stale.
