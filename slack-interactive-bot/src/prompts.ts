/**
 * GTM Copilot Function Definitions
 * Maps to the templates in api/app/prompts/defaults.py
 */

export interface GTMFunction {
  id: string;
  name: string;
  description: string;
  systemPrompt: string;
  template: string;
  variables: string[];
  icon: string;
}

export const GTM_FUNCTIONS: Record<string, GTMFunction> = {
  pre_call: {
    id: "pre_call",
    name: "Pre-Call Intel",
    description: "Research prospect and company before sales call",
    icon: "🔍",
    systemPrompt: "system_pre_call_intel",
    template: "tpl_pre_call",
    variables: ["account", "website", "prospect_name", "prospect_linkedin"],
  },
  post_call: {
    id: "post_call",
    name: "Post-Call Analysis",
    description: "MEDDPICC analysis and next steps after call",
    icon: "📊",
    systemPrompt: "system_post_call_analysis",
    template: "tpl_post_call",
    variables: ["account", "call_context"],
  },
  follow_up: {
    id: "follow_up",
    name: "Follow-Up Email",
    description: "Draft personalized follow-up email",
    icon: "✉️",
    systemPrompt: "system_rep_execution",
    template: "tpl_follow_up",
    variables: ["account", "call_context", "call_notes", "email_to", "email_cc", "email_tone"],
  },
  market_research: {
    id: "market_research",
    name: "Market Research / TAL",
    description: "Generate target account list for territory",
    icon: "🎯",
    systemPrompt: "system_market_research",
    template: "tpl_tal",
    variables: ["icp_description", "regions", "industry", "revenue_min", "revenue_max", "context", "top_n"],
  },
  poc_plan: {
    id: "poc_plan",
    name: "SE: POC Plan",
    description: "Create technical POC evaluation roadmap",
    icon: "🛠️",
    systemPrompt: "system_se_execution",
    template: "tpl_se_poc_plan",
    variables: ["account", "target_offering", "call_context"],
  },
  arch_fit: {
    id: "arch_fit",
    name: "SE: Architecture Fit",
    description: "Analyze TiDB architecture fit for account",
    icon: "🏗️",
    systemPrompt: "system_se_execution",
    template: "tpl_se_arch_fit",
    variables: ["account", "call_context"],
  },
  competitor: {
    id: "competitor",
    name: "SE: Competitor Coach",
    description: "Competitive positioning and objection handling",
    icon: "⚔️",
    systemPrompt: "system_se_analysis",
    template: "tpl_se_competitor",
    variables: ["account", "competitor", "call_context"],
  },
  account_intel: {
    id: "account_intel",
    name: "Account Intel",
    description: "Full analysis on current account - deep dive into company, tech stack, and opportunities",
    icon: "🎯",
    systemPrompt: "system_oracle",
    template: "tpl_account_intel",
    variables: ["account", "website"],
  },
};

/**
 * Generate Slack Block Kit menu with buttons for all functions
 */
export function getPromptMenu() {
  return [
    {
      type: "header",
      text: {
        type: "plain_text",
        text: "🚀 GTM Copilot Functions",
      },
    },
    {
      type: "section",
      text: {
        type: "mrkdwn",
        text: "Select a function to run with Claude:",
      },
    },
    {
      type: "divider",
    },
    {
      type: "section",
      text: {
        type: "mrkdwn",
        text: `${GTM_FUNCTIONS.pre_call.icon} *${GTM_FUNCTIONS.pre_call.name}*\n${GTM_FUNCTIONS.pre_call.description}`,
      },
      accessory: {
        type: "button",
        text: {
          type: "plain_text",
          text: "Run",
        },
        action_id: `gtm_${GTM_FUNCTIONS.pre_call.id}`,
        style: "primary",
      },
    },
    {
      type: "section",
      text: {
        type: "mrkdwn",
        text: `${GTM_FUNCTIONS.post_call.icon} *${GTM_FUNCTIONS.post_call.name}*\n${GTM_FUNCTIONS.post_call.description}`,
      },
      accessory: {
        type: "button",
        text: {
          type: "plain_text",
          text: "Run",
        },
        action_id: `gtm_${GTM_FUNCTIONS.post_call.id}`,
      },
    },
    {
      type: "section",
      text: {
        type: "mrkdwn",
        text: `${GTM_FUNCTIONS.follow_up.icon} *${GTM_FUNCTIONS.follow_up.name}*\n${GTM_FUNCTIONS.follow_up.description}`,
      },
      accessory: {
        type: "button",
        text: {
          type: "plain_text",
          text: "Run",
        },
        action_id: `gtm_${GTM_FUNCTIONS.follow_up.id}`,
      },
    },
    {
      type: "section",
      text: {
        type: "mrkdwn",
        text: `${GTM_FUNCTIONS.account_intel.icon} *${GTM_FUNCTIONS.account_intel.name}*\n${GTM_FUNCTIONS.account_intel.description}`,
      },
      accessory: {
        type: "button",
        text: {
          type: "plain_text",
          text: "Run",
        },
        action_id: `gtm_${GTM_FUNCTIONS.account_intel.id}`,
        style: "primary",
      },
    },
    {
      type: "section",
      text: {
        type: "mrkdwn",
        text: `${GTM_FUNCTIONS.market_research.icon} *${GTM_FUNCTIONS.market_research.name}*\n${GTM_FUNCTIONS.market_research.description}`,
      },
      accessory: {
        type: "button",
        text: {
          type: "plain_text",
          text: "Run",
        },
        action_id: `gtm_${GTM_FUNCTIONS.market_research.id}`,
      },
    },
    {
      type: "divider",
    },
    {
      type: "context",
      elements: [
        {
          type: "mrkdwn",
          text: "*Sales Engineering Functions*",
        },
      ],
    },
    {
      type: "section",
      text: {
        type: "mrkdwn",
        text: `${GTM_FUNCTIONS.poc_plan.icon} *${GTM_FUNCTIONS.poc_plan.name}*\n${GTM_FUNCTIONS.poc_plan.description}`,
      },
      accessory: {
        type: "button",
        text: {
          type: "plain_text",
          text: "Run",
        },
        action_id: `gtm_${GTM_FUNCTIONS.poc_plan.id}`,
      },
    },
    {
      type: "section",
      text: {
        type: "mrkdwn",
        text: `${GTM_FUNCTIONS.arch_fit.icon} *${GTM_FUNCTIONS.arch_fit.name}*\n${GTM_FUNCTIONS.arch_fit.description}`,
      },
      accessory: {
        type: "button",
        text: {
          type: "plain_text",
          text: "Run",
        },
        action_id: `gtm_${GTM_FUNCTIONS.arch_fit.id}`,
      },
    },
    {
      type: "section",
      text: {
        type: "mrkdwn",
        text: `${GTM_FUNCTIONS.competitor.icon} *${GTM_FUNCTIONS.competitor.name}*\n${GTM_FUNCTIONS.competitor.description}`,
      },
      accessory: {
        type: "button",
        text: {
          type: "plain_text",
          text: "Run",
        },
        action_id: `gtm_${GTM_FUNCTIONS.competitor.id}`,
      },
    },
  ];
}
