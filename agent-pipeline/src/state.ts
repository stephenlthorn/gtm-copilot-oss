import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { resolve } from "node:path";
import { IOS_APP_ROOT } from "./config.js";
import type { PipelineState } from "./types.js";

function appPath(relative: string): string {
  return resolve(IOS_APP_ROOT, relative);
}

export function readState(): PipelineState {
  const phaseFile = appPath("phase.json");
  if (!existsSync(phaseFile)) {
    return {
      phase: "A",
      totalIterations: 0,
      lastQAStatus: "unknown",
      lastUpdated: new Date().toISOString(),
    };
  }
  return JSON.parse(readFileSync(phaseFile, "utf-8")) as PipelineState;
}

export function writeState(state: PipelineState): void {
  writeFileSync(appPath("phase.json"), JSON.stringify(state, null, 2));
}

export function appendProgress(entry: string): void {
  const logFile = appPath("progress.log");
  const timestamp = new Date().toISOString();
  const line = `[${timestamp}] ${entry}\n`;
  writeFileSync(logFile, line, { flag: "a" });
}

export function readDoc(relativePath: string): string {
  const fullPath = appPath(relativePath);
  if (!existsSync(fullPath)) return "";
  return readFileSync(fullPath, "utf-8");
}

export function writeDoc(relativePath: string, content: string): void {
  writeFileSync(appPath(relativePath), content, "utf-8");
}

export function incrementIteration(state: PipelineState): PipelineState {
  return {
    ...state,
    totalIterations: state.totalIterations + 1,
    lastUpdated: new Date().toISOString(),
  };
}
