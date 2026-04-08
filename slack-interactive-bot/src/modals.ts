import { GTMFunction } from "./prompts";

/**
 * Build Slack modal for collecting inputs for a GTM function
 */
export function buildModal(functionId: string, functionDef: GTMFunction) {
  const blocks: any[] = [];

  // Map variable names to user-friendly labels and placeholders
  const fieldConfig: Record<string, { label: string; placeholder: string; multiline?: boolean }> = {
    account: {
      label: "Account Name",
      placeholder: "e.g., Acme Corp",
    },
    website: {
      label: "Company Website",
      placeholder: "e.g., https://acme.com",
    },
    prospect_name: {
      label: "Prospect Name",
      placeholder: "e.g., John Smith",
    },
    prospect_linkedin: {
      label: "Prospect LinkedIn URL",
      placeholder: "e.g., https://linkedin.com/in/johnsmith",
    },
    call_context: {
      label: "Call Context / Summary",
      placeholder: "Paste transcript or summary of the call...",
      multiline: true,
    },
    call_notes: {
      label: "Additional Notes",
      placeholder: "Any additional context or notes...",
      multiline: true,
    },
    email_to: {
      label: "Email To",
      placeholder: "e.g., john@acme.com",
    },
    email_cc: {
      label: "Email CC (optional)",
      placeholder: "e.g., sarah@acme.com",
    },
    email_tone: {
      label: "Email Tone",
      placeholder: "e.g., professional, casual, technical",
    },
    icp_description: {
      label: "ICP Description",
      placeholder: "Describe your ideal customer profile...",
      multiline: true,
    },
    regions: {
      label: "Territory / Regions",
      placeholder: "e.g., North America, EMEA, APAC",
    },
    industry: {
      label: "Industry Vertical",
      placeholder: "e.g., Financial Services, SaaS, E-commerce",
    },
    revenue_min: {
      label: "Min Revenue ($M)",
      placeholder: "e.g., 50",
    },
    revenue_max: {
      label: "Max Revenue ($M)",
      placeholder: "e.g., 500",
    },
    context: {
      label: "Constraints / Priorities",
      placeholder: "Any specific constraints or priorities...",
      multiline: true,
    },
    top_n: {
      label: "Number of Accounts",
      placeholder: "e.g., 10",
    },
    target_offering: {
      label: "Target Offering",
      placeholder: "e.g., TiDB Cloud, TiDB Enterprise",
    },
    competitor: {
      label: "Primary Competitor",
      placeholder: "e.g., CockroachDB, YugabyteDB, Aurora",
    },
  };

  // Add input blocks for each variable
  for (const variable of functionDef.variables) {
    const config = fieldConfig[variable] || {
      label: variable,
      placeholder: `Enter ${variable}...`,
    };

    blocks.push({
      type: "input",
      block_id: variable,
      element: {
        type: "plain_text_input",
        action_id: variable,
        placeholder: {
          type: "plain_text",
          text: config.placeholder,
        },
        multiline: config.multiline || false,
      },
      label: {
        type: "plain_text",
        text: config.label,
      },
      optional: variable.includes("cc") || variable.includes("notes") || variable === "context",
    });
  }

  return {
    type: "modal",
    callback_id: `submit_gtm_${functionId}`,
    title: {
      type: "plain_text",
      text: functionDef.name,
    },
    submit: {
      type: "plain_text",
      text: "Run Analysis",
    },
    close: {
      type: "plain_text",
      text: "Cancel",
    },
    blocks,
  };
}
