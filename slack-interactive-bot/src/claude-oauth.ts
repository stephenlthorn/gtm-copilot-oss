import { GTMFunction } from "./prompts";
import { SYSTEM_PROMPTS } from "./system-prompts";

/**
 * Build a message to send to the native Claude Slack app
 * This constructs the full prompt with system context + user inputs
 */
export function buildClaudeMessage(
  functionDef: GTMFunction,
  userInputs: Record<string, string>
): string {
  // Get the system prompt for this function
  const systemPrompt = SYSTEM_PROMPTS[functionDef.systemPrompt] || "";

  // Build the complete message
  let message = "";

  // Add system context as a quoted block
  message += `> **Context:** You are a GTM Copilot specialist.\n>\n`;
  message += systemPrompt
    .split("\n")
    .map((line) => `> ${line}`)
    .join("\n");
  message += "\n\n";

  // Add a clear separator
  message += `---\n\n`;

  // Add the user's request
  message += `**Task:** ${functionDef.name}\n\n`;

  // Add user inputs in a structured format
  for (const [key, value] of Object.entries(userInputs)) {
    if (value && value.trim()) {
      const label = formatLabel(key);

      // For longer fields, use a code block
      if (value.length > 200 || value.includes("\n")) {
        message += `**${label}:**\n\`\`\`\n${value}\n\`\`\`\n\n`;
      } else {
        message += `**${label}:** ${value}\n\n`;
      }
    }
  }

  // Add instructions based on function type
  message += `---\n\n`;
  message += getInstructionsForFunction(functionDef);

  return message;
}

/**
 * Get specific instructions for each function type
 */
function getInstructionsForFunction(functionDef: GTMFunction): string {
  const instructions: Record<string, string> = {
    pre_call: `Please research this prospect and company thoroughly and provide:
1. **Prospect Information** - Role, background, time at company
2. **Company Context** - Industry, size, product, competitors
3. **Current Architecture Hypothesis** - Likely tech stack and databases
4. **Pain Hypothesis** - At least 2 potential pains with evidence
5. **TiDB Value Propositions** - How TiDB addresses each pain
6. **Meeting Goal** - Recommended outcome for this call
7. **Meeting Flow Agreement** - Suggested meeting structure`,

    post_call: `Please analyze this call and provide:
1. **Call Summary** - Key topics, decisions, tone
2. **Next Steps** - All action items with owners and dates
3. **MEDDPICC Analysis** - What was established vs. what's missing for each element
4. **Qualification Assessment** - Is this qualified? Top 3 gaps to close
5. **Recommended Next Action** - Specific next step to advance the deal`,

    follow_up: `Please draft a follow-up email that:
1. References specific moments from the call
2. Reinforces agreed-upon next steps
3. Advances the deal with a clear ask
4. Uses the requested tone
5. Is personalized to this account (NO generic templates)`,

    account_intel: `Please provide a complete account analysis:
1. **Company Overview** - Business, industry, size, revenue
2. **Technology Stack** - Current databases and infrastructure
3. **Key Decision Makers** - Titles and responsibilities
4. **Pain Signals** - Evidence of database/scaling challenges
5. **TiDB Opportunity** - Where and how TiDB fits
6. **Competitive Landscape** - What alternatives they might consider
7. **Recommended Approach** - Entry strategy and first actions`,

    market_research: `Please generate a target account list with:
1. **Account Name** and basic info
2. **ICP Fit Score** (1-10) with rationale
3. **Top Signal** - Why they're a good fit (with source)
4. **Entry Point** - Recommended role and angle
5. **First Action** - Specific next step for each account

Return the top N accounts ranked by fit and buying signals.`,

    poc_plan: `Please create a detailed POC plan including:
1. **POC Objectives** - Success criteria for customer and TiDB
2. **Success Criteria** - Specific measurable criteria (at least 3)
3. **Technical Requirements** - What we need from customer
4. **4-Week Milestone Plan** - Week-by-week breakdown
5. **Resources Required** - From both TiDB and customer
6. **Risk Factors & Mitigations** - Top 3 risks and how to address
7. **Recommended POC Kit** - Relevant docs, benchmarks, tools`,

    arch_fit: `Please analyze TiDB architecture fit:
1. **Current State Assessment** - Their existing database/infrastructure
2. **Scalability Pain Signals** - Evidence of scale limits
3. **MySQL/PostgreSQL/Oracle Compatibility** - Workload compatibility analysis
4. **HTAP Opportunity** - Real-time analytics use cases
5. **Migration Complexity** - Low/Medium/High with explanation
6. **TiDB Placement Recommendation** - Where TiDB fits in their stack
7. **Target State Architecture** - What it looks like with TiDB`,

    competitor: `Please provide competitive coaching:
1. **Competitive Positioning** - Where TiDB wins, where to be careful
2. **Top 5 Objections & Responses** - Specific objection handling
3. **Competitor Weaknesses** - Questions to expose their limitations
4. **TiDB Proof Points** - Benchmarks, case studies, references
5. **Recommended Demo/POC Focus** - What to show that they can't match
6. **Deal Strategy** - Overall win strategy for this account`,
  };

  return (
    instructions[functionDef.id] ||
    `Please provide a comprehensive analysis following the ${functionDef.name} framework.`
  );
}

/**
 * Convert variable name to readable label
 */
function formatLabel(key: string): string {
  const labelOverrides: Record<string, string> = {
    account: "Account Name",
    website: "Website",
    prospect_name: "Prospect Name",
    prospect_linkedin: "Prospect LinkedIn",
    call_context: "Call Context",
    call_notes: "Additional Notes",
    email_to: "To",
    email_cc: "CC",
    email_tone: "Tone",
    icp_description: "ICP Description",
    regions: "Regions",
    industry: "Industry",
    revenue_min: "Min Revenue ($M)",
    revenue_max: "Max Revenue ($M)",
    context: "Context",
    top_n: "Top N Accounts",
    target_offering: "Target Offering",
    competitor: "Competitor",
  };

  return (
    labelOverrides[key] ||
    key
      .split("_")
      .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
      .join(" ")
  );
}

/**
 * Alternative: Build a Canvas-formatted message
 * Use this if you want to post results to a Canvas instead of a message
 */
export function buildClaudeCanvasMessage(
  functionDef: GTMFunction,
  userInputs: Record<string, string>
): string {
  let canvas = `# ${functionDef.name}\n\n`;

  // Add user inputs as a reference section
  canvas += `## Input Parameters\n\n`;
  for (const [key, value] of Object.entries(userInputs)) {
    if (value && value.trim()) {
      canvas += `**${formatLabel(key)}:** ${value}\n\n`;
    }
  }

  canvas += `---\n\n`;

  // Add the request to Claude
  canvas += `@Claude - Please analyze the above using the ${functionDef.name} framework.\n\n`;
  canvas += getInstructionsForFunction(functionDef);

  return canvas;
}
