import "node:fs";
import { readState, writeState, appendProgress, incrementIteration } from "./state.js";
import { runPmAgent } from "./agents/pm.js";
import { runScrumAgent } from "./agents/scrum.js";
import { runSpecCompilerAgent } from "./agents/spec-compiler.js";
import { runEngineerAgent } from "./agents/engineer.js";
import { runQaBuildAgent } from "./agents/qa-build.js";
import { runQaFixLoopAgent } from "./agents/qa-fix-loop.js";
import { runQaRegressionAgent } from "./agents/qa-regression.js";
import { runCommitAgent } from "./agents/commit.js";
import { runEndUserTesterAgent } from "./agents/end-user-tester.js";
import { runTechWriterAgent } from "./agents/tech-writer.js";
import { QA_MAX_RETRIES } from "./config.js";

async function runPipeline(): Promise<void> {
  const startState = readState();
  const iteration = startState.totalIterations + 1;
  console.log(`\n=== iOS Dev Pipeline — Iteration ${iteration} (Phase ${startState.phase}) ===\n`);

  appendProgress(`START iteration=${iteration} phase=${startState.phase}`);

  // ── 1. Planning track ───────────────────────────────────────────────────────
  console.log("[1/9] PM Agent...");
  const pmResult = await runPmAgent();
  appendProgress(`PM done tool_calls=${pmResult.toolCallCount}`);

  console.log("[2/9] Scrum Master...");
  const scrumResult = await runScrumAgent(pmResult.output);
  appendProgress(`Scrum done tool_calls=${scrumResult.toolCallCount}`);

  console.log("[3/9] Spec Compiler...");
  const specResult = await runSpecCompilerAgent(scrumResult.output);
  appendProgress(`Spec done tool_calls=${specResult.toolCallCount}`);

  // ── 2. Engineer Swarm (parallel) ─────────────────────────────────────────────
  console.log("[4/9] Engineer Swarm (UI + Core + Tests in parallel)...");
  const [uiResult, coreResult, testsResult] = await Promise.all([
    runEngineerAgent("ui", specResult.output),
    runEngineerAgent("core", specResult.output),
    runEngineerAgent("tests", specResult.output),
  ]);
  appendProgress(
    `Engineers done ui=${uiResult.toolCallCount} core=${coreResult.toolCallCount} tests=${testsResult.toolCallCount}`,
  );

  // ── 3. QA Build/Fix Loop ─────────────────────────────────────────────────────
  console.log("[5/9] QA Build/Fix Loop...");
  let qaPass = false;
  let buildErrors = "";
  for (let attempt = 0; attempt < QA_MAX_RETRIES && !qaPass; attempt++) {
    console.log(`  QA Build attempt ${attempt + 1}/${QA_MAX_RETRIES}...`);
    const buildResult = await runQaBuildAgent();
    if (buildResult.pass) {
      qaPass = true;
      appendProgress(`QA Build PASS attempt=${attempt + 1}`);
    } else {
      buildErrors = buildResult.errors;
      appendProgress(`QA Build FAIL attempt=${attempt + 1}`);
      if (attempt < QA_MAX_RETRIES - 1) {
        console.log(`  QA Fix Loop (attempt ${attempt + 1})...`);
        await runQaFixLoopAgent(attempt, buildErrors);
      }
    }
  }

  if (!qaPass) {
    console.error("QA Build failed after max retries. Stopping pipeline.");
    appendProgress(`ABORT qa_failed_after=${QA_MAX_RETRIES}_attempts`);
    writeState({ ...startState, lastQAStatus: "fail", lastUpdated: new Date().toISOString() });
    process.exit(1);
  }

  // ── 4. QA Regression ─────────────────────────────────────────────────────────
  console.log("[6/9] QA Regression...");
  const regressionResult = await runQaRegressionAgent();
  appendProgress(`QA Regression done tool_calls=${regressionResult.toolCallCount}`);

  // ── 5. Commit ─────────────────────────────────────────────────────────────────
  console.log("[7/9] Commit Agent...");
  const commitResult = await runCommitAgent(iteration);
  appendProgress(`Commit done tool_calls=${commitResult.toolCallCount}`);

  // ── 6. End User Tester ────────────────────────────────────────────────────────
  console.log("[8/9] End User Tester...");
  const testerResult = await runEndUserTesterAgent();
  appendProgress(`End User Tester done tool_calls=${testerResult.toolCallCount}`);

  // ── 7. Tech Writer ────────────────────────────────────────────────────────────
  console.log("[9/9] Tech Writer...");
  const writerResult = await runTechWriterAgent(commitResult.output);
  appendProgress(`Tech Writer done tool_calls=${writerResult.toolCallCount}`);

  // ── Update state ─────────────────────────────────────────────────────────────
  writeState(incrementIteration({ ...startState, lastQAStatus: "pass" }));
  appendProgress(`END iteration=${iteration} status=pass`);

  console.log(`\n=== Pipeline complete — iteration ${iteration} done ===`);
}

runPipeline().catch((err: unknown) => {
  console.error("Pipeline error:", err);
  process.exit(1);
});
