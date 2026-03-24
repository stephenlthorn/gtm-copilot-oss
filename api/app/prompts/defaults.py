from __future__ import annotations

import json

from app.prompts.personas import PERSONA_DEFAULT_PROMPTS
from app.prompts.source_profiles import PRE_CALL_SOURCES, POST_CALL_SOURCES, POC_TECHNICAL_SOURCES
from app.prompts.templates import (
    SYSTEM_ORACLE,
    SYSTEM_PRE_CALL_INTEL,
    SYSTEM_POST_CALL_ANALYSIS,
    SYSTEM_SE_ANALYSIS,
    SYSTEM_CALL_COACH,
    SYSTEM_MESSAGING_GUARDRAIL,
    SYSTEM_MARKET_RESEARCH,
    SYSTEM_REP_EXECUTION,
    SYSTEM_SE_EXECUTION,
    SYSTEM_MARKETING_EXECUTION,
    TIDB_EXPERT_CONTEXT,
)

ALL_DEFAULTS: dict[str, dict] = {
    # System prompts
    "system_oracle": {
        "category": "system_prompt",
        "name": "Oracle",
        "description": "Base system prompt for general chat and oracle queries",
        "content": SYSTEM_ORACLE,
        "variables": "[]",
    },
    "system_pre_call_intel": {
        "category": "system_prompt",
        "name": "Pre-Call Intel",
        "description": "System prompt for pre-call research briefs with accuracy rules and deep research protocol",
        "content": SYSTEM_PRE_CALL_INTEL,
        "variables": "[]",
    },
    "system_post_call_analysis": {
        "category": "system_prompt",
        "name": "Post-Call Analysis",
        "description": "System prompt for MEDDPICC post-call coaching briefs",
        "content": SYSTEM_POST_CALL_ANALYSIS,
        "variables": "[]",
    },
    "system_se_analysis": {
        "category": "system_prompt",
        "name": "SE Analysis",
        "description": "System prompt for SE technical evaluations, POC plans, and competitor coaching",
        "content": SYSTEM_SE_ANALYSIS,
        "variables": "[]",
    },
    "system_call_coach": {
        "category": "system_prompt",
        "name": "Call Coach",
        "description": "System prompt for call coaching recommendations",
        "content": SYSTEM_CALL_COACH,
        "variables": "[]",
    },
    "system_messaging_guardrail": {
        "category": "system_prompt",
        "name": "Messaging Guardrail",
        "description": "Policy enforcement for outbound email send/draft",
        "content": SYSTEM_MESSAGING_GUARDRAIL,
        "variables": "[]",
    },
    "system_market_research": {
        "category": "system_prompt",
        "name": "Market Research",
        "description": "System prompt for territory-specific strategic account planning",
        "content": SYSTEM_MARKET_RESEARCH,
        "variables": "[]",
    },
    "system_rep_execution": {
        "category": "system_prompt",
        "name": "Rep Execution",
        "description": "System prompt for sales rep account briefs, discovery questions, deal risk, follow-up drafts",
        "content": SYSTEM_REP_EXECUTION,
        "variables": "[]",
    },
    "system_se_execution": {
        "category": "system_prompt",
        "name": "SE Execution",
        "description": "System prompt for SE POC readiness, architecture fit, and competitor coaching",
        "content": SYSTEM_SE_EXECUTION,
        "variables": "[]",
    },
    "system_marketing_execution": {
        "category": "system_prompt",
        "name": "Marketing Execution",
        "description": "System prompt for marketing intelligence and campaign analysis",
        "content": SYSTEM_MARKETING_EXECUTION,
        "variables": "[]",
    },
    "tidb_expert": {
        "category": "system_prompt",
        "name": "TiDB Expert Skill",
        "description": "Complete TiDB knowledge base — injected when TiDB Expert toggle is on (Claude skill pattern)",
        "content": TIDB_EXPERT_CONTEXT,
        "variables": "[]",
    },
    # Section templates
    "tpl_pre_call": {
        "category": "template",
        "name": "Pre-Call Intel",
        "description": "User-facing template for pre-call research prompts",
        "content": (
            "I'm preparing for a sales call with {prospect_name} at {account} ({website}). Please research this prospect and company thoroughly and complete each section below.\n\n"
            "**Section 1 — Prospect Information**\n"
            "Research {prospect_name} ({prospect_linkedin}) and document:\n"
            "• Name: {prospect_name}\n"
            "• Role / Title:\n"
            "• Time at current company:\n"
            "• Relevant previous company or role:\n\n"
            "Example:\n"
            "Prospect: John Smith\n"
            "Role: Director of Platform Engineering\n"
            "Time at company: 3 years\n"
            "Previous company: Stripe – Senior Infrastructure Engineer\n\n"
            "**Section 2 — Company Context**\n"
            "Research {account} ({website}) and document:\n"
            "• # of employees or revenue range:\n"
            "• Industry:\n"
            "• Product or service they provide:\n"
            "• Key competitors:\n\n"
            "**Section 3 — Current Architecture Hypothesis**\n"
            "Based on job postings, GitHub, BuiltWith, Stackshare, and news — hypothesize:\n"
            "• Databases they likely use:\n"
            "• Applications or microservices:\n"
            "• Cloud provider / infrastructure:\n\n"
            "Example:\n"
            "Databases: Aurora, Redis\n"
            "Cloud: AWS\n"
            "Architecture: microservices-based platform\n\n"
            "**Section 4 — Pain Hypothesis**\n"
            "Document at least two potential pains the prospect may have.\n"
            "Examples: scaling database clusters, operational complexity, cost of infrastructure, analytics latency, MySQL sharding limits\n\n"
            "1. Pain:\n"
            "   Signal / evidence:\n"
            "2. Pain:\n"
            "   Signal / evidence:\n\n"
            "**Section 5 — Relevant TiDB Value Propositions**\n"
            "Match each pain to a specific TiDB capability:\n\n"
            "Pain: [Pain 1]\n"
            "Value Prop:\n\n"
            "Pain: [Pain 2]\n"
            "Value Prop:\n\n"
            "Example:\n"
            "Pain: operational complexity\n"
            "Value Prop: No manual sharding; automatic recovery after failure; one system for OLTP and OLAP\n\n"
            "**Section 6 — Meeting Goal**\n"
            "Define the desired outcome of this meeting. Suggest one:\n"
            "• Schedule architecture deep dive\n"
            "• Obtain data for sizing exercise\n"
            "• Introduce platform team stakeholders\n"
            "• Confirm champion and access to economic buyer\n\n"
            "Suggested goal based on research:\n\n"
            "**Section 7 — Meeting Flow Agreement**\n"
            "Document how the meeting will run:\n"
            "• Who does introductions:\n"
            "• Who leads discovery:\n"
            "• Who handles technical questions:\n"
            "• Time allocation (e.g. 5 min intro / 20 min discovery / 10 min TiDB overview / 5 min next steps):\n"
            "• Who asks for next steps:"
        ),
        "variables": '["{account}", "{website}", "{prospect_name}", "{prospect_linkedin}"]',
    },
    "tpl_post_call": {
        "category": "template",
        "name": "Post-Call Analysis",
        "description": "User-facing template for post-call analysis prompts",
        "content": (
            "I just completed a sales call with {account}. Here are the call details:\n\n"
            "{call_context}\n\n"
            "Please analyze the call and produce a complete post-call brief:\n\n"
            "**Call Summary**\n"
            "Summarize the key topics discussed, decisions made, and overall tone of the call.\n\n"
            "**Next Steps**\n"
            "List all agreed-upon next steps with owners and target dates.\n\n"
            "**Action Items by Person**\n\n"
            "Rep:\n"
            "•\n\n"
            "SE:\n"
            "•\n\n"
            "{account} Contact:\n"
            "•\n\n"
            "**MEDDPICC Analysis**\n"
            "For each element, note what was established on this call and what is still missing:\n\n"
            "Metrics (quantifiable impact / value):\n"
            "Economic Buyer (who controls budget):\n"
            "Decision Criteria (what they will evaluate):\n"
            "Decision Process (how they make the decision):\n"
            "Paper Process (legal / procurement / security steps):\n"
            "Implicate Pain (is the pain urgent enough to act?):\n"
            "Champion (who is selling internally for us?):\n"
            "Competition (what else are they evaluating?):\n\n"
            "**Qualification Assessment**\n"
            "• Is this deal actually qualified? (Yes / No / Conditional)\n"
            "• Top 3 qualification gaps to close:\n"
            "  1.\n"
            "  2.\n"
            "  3.\n"
            "• Recommended next action to advance:"
        ),
        "variables": '["{account}", "{call_context}"]',
    },
    "tpl_follow_up": {
        "category": "template",
        "name": "Follow-Up Email",
        "description": "User-facing template for follow-up email drafting",
        "content": (
            "FOLLOW-UP EMAIL REQUEST\n\n"
            "Account: {account}\n"
            "To: {email_to}\n"
            "CC: {email_cc}\n"
            "Tone: {email_tone}\n\n"
            "--- CALL RECORD ---\n"
            "{call_context}\n\n"
            "--- ADDITIONAL NOTES ---\n"
            "{call_notes}\n\n"
            "--- TASK ---\n"
            "Write a specific, deal-advancing follow-up email using the call record, "
            "additional notes, and any retrieved call evidence below. "
            "Do not write a generic email — every sentence should be specific to this account and this call."
        ),
        "variables": '["{account}", "{call_context}", "{call_notes}", "{email_to}", "{email_cc}", "{email_tone}"]',
    },
    "tpl_tal": {
        "category": "template",
        "name": "Market Research / TAL",
        "description": "User-facing template for target account list generation",
        "content": (
            "TARGET ACCOUNT LIST REQUEST\n\n"
            "ICP: {icp_description}\n"
            "Territory / Regions: {regions}\n"
            "Industry vertical: {industry}\n"
            "Revenue range: ${revenue_min}M – ${revenue_max}M\n"
            "Top N requested: {top_n}\n"
            "Constraints / Priorities: {context}\n\n"
            "Return the top {top_n} accounts. For each: account name, ICP score rationale, "
            "top signal (with source), recommended entry point (role + angle), and suggested first action."
        ),
        "variables": '["{icp_description}", "{regions}", "{industry}", "{revenue_min}", "{revenue_max}", "{context}", "{top_n}"]',
    },
    "tpl_se_poc_plan": {
        "category": "template",
        "name": "SE: POC Plan",
        "description": "User-facing template for SE POC planning",
        "content": (
            "Create a detailed technical POC evaluation roadmap for {account}.\n\n"
            "Offering: {target_offering}\n"
            "Call context: {call_context}\n\n"
            "Produce a complete POC plan including:\n\n"
            "**POC Objectives**\n"
            "What success looks like for the customer and for us.\n\n"
            "**Success Criteria**\n"
            "Specific, measurable criteria the customer will use to evaluate TiDB. Include at least 3.\n\n"
            "**Technical Requirements**\n"
            "What we need from the customer to run the POC (access, data, team members, environments).\n\n"
            "**4-Week Milestone Plan**\n"
            "Week 1: Setup and baseline\n"
            "Week 2: Core workload migration / test\n"
            "Week 3: Performance and scale testing\n"
            "Week 4: Results review and business case\n\n"
            "**Resources Required**\n"
            "From TiDB side and from customer side.\n\n"
            "**Risk Factors & Mitigations**\n"
            "Top 3 risks and how to address them.\n\n"
            "**Recommended POC Kit**\n"
            "Suggest relevant TiDB documentation, benchmarks, or migration tools."
        ),
        "variables": '["{account}", "{target_offering}", "{call_context}"]',
    },
    "tpl_se_arch_fit": {
        "category": "template",
        "name": "SE: Architecture Fit",
        "description": "User-facing template for SE architecture fit analysis",
        "content": (
            "Analyze TiDB architecture fit for {account}.\n\n"
            "Call context: {call_context}\n\n"
            "Produce a complete architecture fit analysis:\n\n"
            "**Current State Assessment**\n"
            "Based on call context and research — what database and infrastructure does {account} likely use today?\n\n"
            "**Scalability Pain Signals**\n"
            "What evidence suggests they are hitting scale limits with their current stack?\n\n"
            "**MySQL / PostgreSQL / Oracle Compatibility**\n"
            "How compatible is their existing workload with TiDB's MySQL compatibility layer?\n\n"
            "**HTAP Opportunity**\n"
            "Is there a real-time analytics or HTAP use case? Describe it if present.\n\n"
            "**Migration Complexity Assessment**\n"
            "Rate migration complexity (Low / Medium / High) and explain why.\n\n"
            "**TiDB Placement Recommendation**\n"
            "Where does TiDB fit in their architecture?\n"
            "(Replace primary DB / Add as analytics layer / Modernize sharded MySQL / Greenfield new service)\n\n"
            "**Target State Architecture**\n"
            "Describe what the architecture would look like with TiDB in place."
        ),
        "variables": '["{account}", "{call_context}"]',
    },
    "tpl_se_competitor": {
        "category": "template",
        "name": "SE: Competitor Coach",
        "description": "User-facing template for SE competitive coaching briefs",
        "content": (
            "Competitor coaching for {account} — primary competitor in this deal: {competitor}.\n\n"
            "Call context: {call_context}\n\n"
            "Produce a complete competitive coaching brief:\n\n"
            "**Competitive Positioning vs {competitor}**\n"
            "Where TiDB wins, where to be careful, and where it is a draw.\n\n"
            "**Top 5 Objections & TiDB Responses**\n"
            "1. Objection: | Response:\n"
            "2. Objection: | Response:\n"
            "3. Objection: | Response:\n"
            "4. Objection: | Response:\n"
            "5. Objection: | Response:\n\n"
            "**{competitor} Weaknesses to Probe**\n"
            "Key questions to ask the customer that expose {competitor} limitations.\n\n"
            "**TiDB Proof Points**\n"
            "Specific benchmarks, case studies, or technical references that counter {competitor}'s strengths.\n\n"
            "**Recommended Demo or POC Focus**\n"
            "What to show in a demo or POC that {competitor} cannot match.\n\n"
            "**Deal Strategy Recommendation**\n"
            "Given what we know about {account} and {competitor}, what is the recommended win strategy?"
        ),
        "variables": '["{account}", "{competitor}", "{call_context}"]',
    },
    # Personas
    "persona_sales": {
        "category": "persona",
        "name": "Sales",
        "description": "Persona prompt for sales representatives — deal progression, MEDDPICC, next-action bias",
        "content": PERSONA_DEFAULT_PROMPTS.get("sales_representative", ""),
        "variables": "[]",
    },
    "persona_se": {
        "category": "persona",
        "name": "SE",
        "description": "Persona prompt for sales engineers — technical validation, migration risk, POC patterns",
        "content": PERSONA_DEFAULT_PROMPTS.get("se", ""),
        "variables": "[]",
    },
    "persona_marketing": {
        "category": "persona",
        "name": "Marketing",
        "description": "Persona prompt for marketing — positioning, pipeline generation, campaign angles",
        "content": PERSONA_DEFAULT_PROMPTS.get("marketing_specialist", ""),
        "variables": "[]",
    },
    # Source profiles
    "sources_pre_call": {
        "category": "source_profile",
        "name": "Pre-Call Sources",
        "description": "Search source instructions for pre-call research (13 sources)",
        "content": json.dumps(PRE_CALL_SOURCES),
        "variables": "[]",
    },
    "sources_post_call": {
        "category": "source_profile",
        "name": "Post-Call Sources",
        "description": "Search source instructions for post-call analysis",
        "content": json.dumps(POST_CALL_SOURCES),
        "variables": "[]",
    },
    "sources_poc_technical": {
        "category": "source_profile",
        "name": "POC Technical Sources",
        "description": "Search source instructions for POC technical validation",
        "content": json.dumps(POC_TECHNICAL_SOURCES),
        "variables": "[]",
    },
}
