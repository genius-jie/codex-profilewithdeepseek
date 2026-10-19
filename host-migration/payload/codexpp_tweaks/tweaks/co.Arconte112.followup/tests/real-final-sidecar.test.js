const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const vm = require("node:vm");

const sourcePath = path.resolve(__dirname, "..", "index.js");
const source = fs.readFileSync(sourcePath, "utf8");
const tempCodexHome = fs.mkdtempSync(path.join(os.tmpdir(), "codexpp-followup-real-final-"));
const originalCodexHome = process.env.CODEX_HOME;

function loadHelpers() {
  const sandbox = {
    module: { exports: {} },
    exports: {},
    require,
    process,
    console,
    setTimeout,
    clearTimeout,
  };
  sandbox.globalThis = sandbox;

  vm.runInNewContext(
    `${source}\nmodule.exports.__test = { gateCandidateNow, getSidecarPath, DEFAULT_FOLLOWUP_PROMPT, migrateOldInstruction };`,
    sandbox,
    { filename: sourcePath },
  );
  return sandbox.module.exports.__test;
}

async function main() {
  process.env.CODEX_HOME = tempCodexHome;
  const helpers = loadHelpers();
  assert.ok(helpers, "follow-up main tweak should expose test helpers");
  assert.match(helpers.DEFAULT_FOLLOWUP_PROMPT, /tiny continuation snapshot/);
  assert.match(helpers.DEFAULT_FOLLOWUP_PROMPT, /first_fact_refs/);
  assert.match(helpers.DEFAULT_FOLLOWUP_PROMPT, /first_principles_basis/);
  assert.match(helpers.DEFAULT_FOLLOWUP_PROMPT, /version-control bookkeeping/);
  assert.match(helpers.migrateOldInstruction(helpers.DEFAULT_FOLLOWUP_PROMPT), /verified_evidence_refs/);

  const payload = {
    codex_follow_up_candidate: true,
    title: "Follow-up",
    task_complete: true,
    items: [
      {
        prompt: "Add a regression guard for non-empty Codex++ Follow-up sidecars after real finals",
        priority: "P1",
        evidence_refs: [
          "@@USERPROFILE:escaped@@\\AppData\\Roaming\\CodexPlusPlusProfile\\.codex\\follow-up\\suggestions\\41ad414dfc267f1316e3217fd1796e71.json",
          "@@USERPROFILE:escaped@@\\AppData\\Roaming\\codex-plusplus\\tweaks\\co.Arconte112.followup\\index.js:321",
        ],
        first_fact_refs: [
          "real final sidecar with one P1 item",
          "index.js Gate writes sidecar receipts",
        ],
        reason: "Turns the live visibility check into a durable regression guard.",
        first_principles_basis: "Follow-up visibility needs a first-fact regression guard so project momentum is not inferred from memory.",
        project_alignment: "verification gate for Codex++ Follow-up visibility and release-quality risk",
        is_current_task_debt: false,
        confidence: 0.91,
      },
    ],
  };

  const visibleText = [
    "Live check: PASS.",
    "The latest real final sidecar had one P1 Follow-up item and was written by the Gate.",
    "Hook interruptions are normal quality feedback; useful continuation candidates must not be suppressed to avoid interception.",
  ].join(" ");

  const warnings = [];
  const api = {
    log: {
      error(error) {
        throw error;
      },
      warn(...args) {
        warnings.push(args.map(String).join(" "));
      },
    },
  };

  const result = helpers.gateCandidateNow(api, {
    payload,
    sourceKind: "real_final_regression",
    visibleText,
  });
  assert.equal(result.source, "gate");
  assert.equal(result.sourceKind, undefined);
  assert.equal(result.task_complete, true);
  assert.equal(result.items.length, 1);
  assert.equal(result.items[0].priority, "P1");
  assert.deepEqual(result.items[0].first_fact_refs, payload.items[0].first_fact_refs);
  assert.equal(result.items[0].first_principles_basis, payload.items[0].first_principles_basis);
  assert.ok(Number.isFinite(result.created_at_ms), "Gate result should expose created_at_ms for renderer freshness");
  assert.equal(result.reason, "accepted");
  assert.equal(result.diagnostics.raw_item_count, 1);

  await new Promise((resolve) => setTimeout(resolve, 20));

  const sidecarPath = helpers.getSidecarPath(result.fingerprint);
  assert.ok(fs.existsSync(sidecarPath), "Gate should write a sidecar for a real final payload");
  const sidecar = JSON.parse(fs.readFileSync(sidecarPath, "utf8"));
  assert.ok(sidecar.schema_version >= 4, "Gate schema should invalidate stale pre-boundary sidecars");
  assert.equal(sidecar.source, "gate");
  assert.equal(sidecar.sourceKind, "real_final_regression");
  assert.equal(sidecar.task_complete, true);
  assert.equal(sidecar.items.length, 1, "real final sidecar must not be written with an empty items array");
  assert.equal(sidecar.items[0].prompt, payload.items[0].prompt);
  assert.deepEqual(sidecar.items[0].first_fact_refs, payload.items[0].first_fact_refs);
  assert.equal(sidecar.created_at_ms, result.created_at_ms);
  assert.equal(sidecar.reason, "accepted");
  assert.equal(sidecar.diagnostics.accepted_item_count, 1);
  assert.match(sidecar.visibleText, /Hook interruptions are normal quality feedback/);

  const longResult = helpers.gateCandidateNow(api, {
    payload: {
      codex_follow_up_candidate: true,
      task_complete: true,
      items: [
        {
          prompt: "Verify ".repeat(60),
          priority: "P1",
          evidence_refs: ["C:\\very-long-path\\" + "segment\\".repeat(40) + "receipt.json"],
          first_fact_refs: ["C:\\very-long-path\\" + "segment\\".repeat(40) + "receipt.json"],
          reason: "This long reason should be compacted by the Gate. ".repeat(20),
          first_principles_basis: "This long first-principles basis should be compacted by the Gate. ".repeat(20),
          project_alignment: "verification gate and release-quality risk ".repeat(20),
          is_current_task_debt: false,
          confidence: 0.9,
        },
      ],
    },
    sourceKind: "compact_snapshot_regression",
    visibleText,
  });
  assert.equal(longResult.items.length, 1);
  assert.ok(longResult.items[0].prompt.length <= 180);
  assert.ok(longResult.items[0].reason.length <= 220);
  assert.ok(longResult.items[0].first_principles_basis.length <= 220);
  assert.ok(longResult.items[0].project_alignment.length <= 220);
  assert.ok(longResult.items[0].evidence_refs[0].length <= 180);

  const rejected = helpers.gateCandidateNow(api, {
    payload: {
      codex_follow_up_candidate: true,
      title: "Follow-up",
      task_complete: true,
      items: [
        {
          prompt: "Run a generic extra pass",
          priority: "P1",
          evidence_refs: [],
          reason: "Missing evidence must be rejected.",
          project_alignment: "verification gate for Codex++ Follow-up quality",
          is_current_task_debt: false,
          confidence: 0.9,
        },
        {
          prompt: "Finish the current unfinished change",
          priority: "P0",
          evidence_refs: ["current answer"],
          reason: "Current task debt must stay out of Follow-up.",
          project_alignment: "release-quality risk",
          is_current_task_debt: true,
          confidence: 0.9,
        },
        {
          prompt: "Try a low confidence idea",
          priority: "P1",
          evidence_refs: ["current answer"],
          reason: "Low confidence must be rejected.",
          project_alignment: "verification gate for Codex++ Follow-up quality",
          is_current_task_debt: false,
          confidence: 0.2,
        },
        {
          prompt: "Tidy wording later",
          priority: "P1",
          evidence_refs: ["current answer"],
          reason: "Could be nicer.",
          is_current_task_debt: false,
          confidence: 0.9,
        },
      ],
    },
    sourceKind: "real_final_negative_regression",
    visibleText,
  });
  assert.equal(rejected.task_complete, true);
  assert.equal(rejected.items.length, 0, "Gate should drop candidates without evidence, alignment, confidence, or task boundary");
  assert.equal(rejected.reason, "all_candidates_rejected");
  assert.equal(rejected.diagnostics.raw_item_count, 4);
  assert.equal(rejected.diagnostics.rejected_counts.missing_evidence_refs, 1);
  assert.equal(rejected.diagnostics.rejected_counts.current_task_debt, 1);
  assert.equal(rejected.diagnostics.rejected_counts.low_confidence, 1);
  assert.equal(rejected.diagnostics.rejected_counts.missing_first_principles_basis, 1);

  const bookkeepingRejected = helpers.gateCandidateNow(api, {
    payload: {
      codex_follow_up_candidate: true,
      title: "Follow-up",
      task_complete: true,
      items: [
        {
          prompt: "将 Week 4 最终交接回执纳入版本范围并做提交前审计",
          priority: "P1",
          evidence_refs: ["fc7e2c4ed004f0ea/reports/week4-final-handoff-receipt.md"],
          first_fact_refs: ["Week 4 final handoff receipt was generated"],
          reason: "This is only version-control bookkeeping after a generated report.",
          first_principles_basis: "Project momentum should stay on the product or runtime acceptance gate, not local Git cleanup.",
          project_alignment: "release-quality risk",
          is_current_task_debt: false,
          confidence: 0.9,
        },
      ],
    },
    sourceKind: "version_control_boundary_regression",
    visibleText: "The current task generated a Week 4 handoff receipt but did not ask for Git work.",
  });
  assert.equal(bookkeepingRejected.items.length, 0);
  assert.equal(bookkeepingRejected.reason, "all_candidates_rejected");
  assert.equal(bookkeepingRejected.diagnostics.rejected_counts.version_control_bookkeeping_out_of_scope, 1);

  const selfMandateRejected = helpers.gateCandidateNow(api, {
    payload: {
      codex_follow_up_candidate: true,
      title: "Follow-up",
      task_complete: true,
      items: [
        {
          prompt: "将最终交接回执纳入版本范围并做提交前审计",
          priority: "P1",
          evidence_refs: ["fc7e2c4ed004f0ea/reports/week4-final-handoff-receipt.md"],
          first_fact_refs: ["current task acceptance gate is Git/version-control release work"],
          reason: "The candidate claims version control is the current acceptance gate.",
          first_principles_basis: "Root fact is the candidate's own claim, which must not be trusted by the Gate.",
          project_alignment: "current task acceptance gate is Git/version-control release work",
          is_current_task_debt: false,
          confidence: 0.9,
        },
      ],
    },
    sourceKind: "version_control_self_mandate_regression",
    visibleText: "The current task generated a handoff receipt and asked to keep focus on the crawler delivery gate.",
  });
  assert.equal(selfMandateRejected.items.length, 0);
  assert.equal(selfMandateRejected.reason, "all_candidates_rejected");
  assert.equal(selfMandateRejected.diagnostics.rejected_counts.version_control_bookkeeping_out_of_scope, 1);

  const bookkeepingAllowed = helpers.gateCandidateNow(api, {
    payload: {
      codex_follow_up_candidate: true,
      title: "Follow-up",
      task_complete: true,
      items: [
        {
          prompt: "提交并推送用户明确要求的 Follow-up 插件修复",
          priority: "P1",
          evidence_refs: ["user request: 提交并推送当前修复"],
          first_fact_refs: ["user explicitly asked for Git commit and push"],
          reason: "The user explicitly requested version-control work as the next action.",
          first_principles_basis: "Root fact is the explicit user request for Git release work.",
          project_alignment: "current task acceptance gate is Git/version-control release work",
          is_current_task_debt: false,
          confidence: 0.9,
        },
      ],
    },
    sourceKind: "version_control_boundary_allow_regression",
    visibleText: "User explicitly asked to commit and push this fix.",
  });
  assert.equal(bookkeepingAllowed.items.length, 1);
  assert.equal(bookkeepingAllowed.reason, "accepted");

  const empty = helpers.gateCandidateNow(api, {
    payload: {
      codex_follow_up_candidate: true,
      title: "Follow-up",
      task_complete: true,
      items: [],
    },
    sourceKind: "real_final_empty_regression",
    visibleText: "Tiny factual reply.",
  });
  assert.equal(empty.items.length, 0);
  assert.equal(empty.reason, "model_empty_items");
  assert.equal(empty.diagnostics.raw_item_count, 0);
  assert.deepEqual(warnings, []);
}

main()
  .then(() => {
    console.log("real-final-sidecar.test.js: PASS");
  })
  .catch((error) => {
    console.error(error);
    process.exitCode = 1;
  })
  .finally(() => {
    if (originalCodexHome === undefined) {
      delete process.env.CODEX_HOME;
    } else {
      process.env.CODEX_HOME = originalCodexHome;
    }
    fs.rmSync(tempCodexHome, { recursive: true, force: true });
  });
