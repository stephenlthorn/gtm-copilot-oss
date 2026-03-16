import type { Provider } from "./interface.js";
import type { ProviderName } from "../types.js";

let _openai: import("./openai.js").OpenAIProvider | undefined;

export async function getProvider(name: ProviderName): Promise<Provider> {
  if (!_openai) {
    const { OpenAIProvider } = await import("./openai.js");
    _openai = new OpenAIProvider();
  }
  return _openai;
}

export type { Provider };

export type { Provider };
