import type { Provider } from "./interface.js";
import type { ProviderName } from "../types.js";

let _claude: import("./claude.js").ClaudeProvider | undefined;
let _openai: import("./openai.js").OpenAIProvider | undefined;
let _minimax: import("./minimax.js").MiniMaxProvider | undefined;

export async function getProvider(name: ProviderName): Promise<Provider> {
  switch (name) {
    case "claude": {
      if (!_claude) {
        const { ClaudeProvider } = await import("./claude.js");
        _claude = new ClaudeProvider();
      }
      return _claude;
    }
    case "openai": {
      if (!_openai) {
        const { OpenAIProvider } = await import("./openai.js");
        _openai = new OpenAIProvider();
      }
      return _openai;
    }
    case "minimax": {
      if (!_minimax) {
        const { MiniMaxProvider } = await import("./minimax.js");
        _minimax = new MiniMaxProvider();
      }
      return _minimax;
    }
  }
}

export type { Provider };
