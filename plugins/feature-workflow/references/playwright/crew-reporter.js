'use strict';

/**
 * Generic Playwright reporter for CREW.
 *
 * Copy/vendor this file into the E2E repository (or implement the same schema)
 * and configure Playwright to write crew-results.json.
 *
 * Stable AC identity:
 *   - preferred: step/title contains "{slug}#AC-n"
 *   - fallback: test annotation { type: "crew-ac", description: "{slug}#AC-n" }
 *
 * BLOCKED:
 *   - whole test: { type: "crew-blocked", description: "reason" }
 *   - selected ACs: push runtime annotation
 *       { type: "crew-ac-status",
 *         description: '{"ac":"slug#AC-5","status":"blocked","reason":"..."}' }
 *
 * Partial evidence:
 *   { type: "crew-ac-status",
 *     description: '{"ac":"slug#AC-9","coverage":"partial","reason":"browser half only"}' }
 *
 * Compatibility:
 *   The same JSON may be attached with testInfo.attach('crew-ac-status', ...).
 *   Attachments work with older Playwright versions where TestResult.annotations
 *   does not yet expose runtime annotations.
 */

const fs = require('fs');
const path = require('path');

const AC_KEY_RE = /([A-Za-z0-9][A-Za-z0-9._-]*#AC-\d+)\b/g;

function extractAcKeys(text) {
  const keys = [];
  const seen = new Set();
  for (const match of String(text || '').matchAll(AC_KEY_RE)) {
    if (!seen.has(match[1])) {
      seen.add(match[1]);
      keys.push(match[1]);
    }
  }
  return keys;
}

function annotationsOf(test, result) {
  // Playwright v1.52+ exposes runtime annotations (including testInfo.annotations
  // and runtime test.skip/fixme/fail annotations) on TestResult.annotations.
  // Prefer result annotations, then merge static TestCase annotations for
  // compatibility with older runners.
  const combined = [
    ...(Array.isArray(result && result.annotations) ? result.annotations : []),
    ...(Array.isArray(test && test.annotations) ? test.annotations : []),
  ];
  const seen = new Set();
  return combined.filter((item) => {
    if (!item || !item.type) return false;
    const key = `${item.type}::${item.description || ''}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function annotationValues(test, result, type) {
  return annotationsOf(test, result)
    .filter((item) => item.type === type && item.description)
    .map((item) => String(item.description));
}

function scenarioOf(test, result) {
  const annotated = annotationValues(test, result, 'crew-scenario')[0];
  if (annotated) return annotated;

  if (test && typeof test.titlePath === 'function') {
    const parts = test.titlePath().filter(Boolean);
    if (parts.length) return parts.join(' > ');
  }
  return test && test.title ? String(test.title) : 'unknown';
}

function blockedReasonOf(test, result) {
  return annotationValues(test, result, 'crew-blocked')[0] || null;
}

function acStatusPayloads(test, result) {
  const payloads = [...annotationValues(test, result, 'crew-ac-status')];
  const attachments = Array.isArray(result && result.attachments) ? result.attachments : [];

  for (const attachment of attachments) {
    if (!attachment || attachment.name !== 'crew-ac-status') continue;
    try {
      if (attachment.body != null) {
        payloads.push(Buffer.isBuffer(attachment.body) ? attachment.body.toString('utf8') : String(attachment.body));
      } else if (attachment.path) {
        payloads.push(fs.readFileSync(attachment.path, 'utf8'));
      }
    } catch {
      // Reporter must not crash because one optional compatibility attachment
      // is unreadable. The corresponding AC will remain unmapped instead.
    }
  }

  return payloads;
}

function acStatusOverrides(test, result) {
  const allowedStatus = new Set(['passed', 'failed', 'blocked', 'skipped', 'manual']);
  const allowedCoverage = new Set(['full', 'partial']);
  const overrides = new Map();

  for (const raw of acStatusPayloads(test, result)) {
    let value;
    try {
      value = JSON.parse(raw);
    } catch {
      continue;
    }
    if (!value || typeof value !== 'object') continue;
    const keys = extractAcKeys(value.ac);
    if (keys.length !== 1) continue;

    const ac = keys[0];
    if (!overrides.has(ac)) {
      overrides.set(ac, { ac, status: null, coverage: 'full', reasons: [] });
    }
    const current = overrides.get(ac);
    if (value.status && allowedStatus.has(value.status)) current.status = value.status;
    if (value.coverage && allowedCoverage.has(value.coverage)) current.coverage = value.coverage;
    if (value.reason && !current.reasons.includes(String(value.reason))) {
      current.reasons.push(String(value.reason));
    }
  }

  return overrides;
}

function errorMessage(error) {
  if (!error) return null;
  if (typeof error === 'string') return error.split('\n')[0];
  if (error.message) return String(error.message).split('\n')[0];
  return String(error).split('\n')[0];
}

function mapAttemptStatus(result, blockedReason) {
  if (blockedReason) return 'blocked';
  const status = result && result.status ? result.status : 'failed';
  if (status === 'passed') return 'passed';
  if (status === 'skipped') return 'skipped';
  return 'failed';
}

function relativeArtifactPath(filePath) {
  if (!filePath) return null;
  const rel = path.relative(process.cwd(), filePath);
  return rel && !rel.startsWith('..') ? rel : filePath;
}

function evidenceOf(result) {
  const evidence = {
    trace: null,
    screenshot: null,
    video: null,
  };

  const attachments = Array.isArray(result && result.attachments) ? result.attachments : [];
  for (const attachment of attachments) {
    if (!attachment || !attachment.path) continue;
    const name = String(attachment.name || '').toLowerCase();
    const contentType = String(attachment.contentType || '').toLowerCase();
    const ext = path.extname(attachment.path).toLowerCase();
    const value = relativeArtifactPath(attachment.path);

    if (!evidence.trace && (name.includes('trace') || ext === '.zip')) {
      evidence.trace = value;
    } else if (!evidence.screenshot && (name.includes('screenshot') || contentType.startsWith('image/'))) {
      evidence.screenshot = value;
    } else if (!evidence.video && (name.includes('video') || contentType.startsWith('video/') || ext === '.webm')) {
      evidence.video = value;
    }
  }

  return evidence;
}

function firstStepError(step) {
  if (!step) return null;
  if (step.error) return step.error;
  for (const child of Array.isArray(step.steps) ? step.steps : []) {
    const error = firstStepError(child);
    if (error) return error;
  }
  return null;
}

function collectStepRecords(steps, blockedReason) {
  const records = [];
  for (const step of Array.isArray(steps) ? steps : []) {
    const keys = extractAcKeys(step && step.title);
    const nestedError = firstStepError(step);
    for (const ac of keys) {
      records.push({
        ac,
        status: blockedReason ? 'blocked' : (nestedError ? 'failed' : 'passed'),
        duration_ms: Number(step.duration || 0),
        reason: blockedReason || errorMessage(nestedError),
      });
    }
    records.push(...collectStepRecords(step && step.steps, blockedReason));
  }
  return records;
}

function mergeAttemptRecords(records) {
  const rank = { passed: 0, skipped: 1, manual: 2, flaky: 3, blocked: 4, failed: 5 };
  const grouped = new Map();

  for (const record of records) {
    if (!grouped.has(record.ac)) {
      grouped.set(record.ac, {
        ac: record.ac,
        status: record.status,
        coverage: record.coverage || 'full',
        duration_ms: 0,
        reasons: [],
      });
    }
    const merged = grouped.get(record.ac);
    merged.duration_ms += Number(record.duration_ms || 0);
    if (record.coverage === 'partial') merged.coverage = 'partial';
    if ((rank[record.status] ?? 99) > (rank[merged.status] ?? 99)) {
      merged.status = record.status;
    }
    if (record.reason && !merged.reasons.includes(record.reason)) {
      merged.reasons.push(record.reason);
    }
  }

  return [...grouped.values()].map((record) => ({
    ac: record.ac,
    status: record.status,
    coverage: record.coverage || 'full',
    duration_ms: record.duration_ms,
    reason: record.reasons.length ? record.reasons.join(' | ') : null,
  }));
}

function finalStatus(attempts) {
  if (!attempts.length) return 'failed';
  const last = attempts[attempts.length - 1].status;
  if (last === 'passed' && attempts.slice(0, -1).some((a) => a.status !== 'passed')) {
    return 'flaky';
  }
  return last;
}

class CrewReporter {
  constructor(options = {}) {
    this.options = options || {};
    this.outputFile =
      this.options.outputFile ||
      process.env.CREW_RESULTS_FILE ||
      'test-results/crew-results.json';
    this.environment =
      this.options.environment ||
      process.env.CREW_E2E_ENV ||
      process.env.PROFILE ||
      'unknown';
    this.groups = new Map();
  }

  onTestEnd(test, result) {
    const blockedReason = blockedReasonOf(test, result);
    const overrides = acStatusOverrides(test, result);
    const evidence = evidenceOf(result);
    const scenario = scenarioOf(test, result);
    const testId = test && test.id ? String(test.id) : scenario;

    let records = mergeAttemptRecords(collectStepRecords(result && result.steps, blockedReason));

    if (!records.length) {
      const annotationKeys = annotationValues(test, result, 'crew-ac').flatMap(extractAcKeys);
      const titleKeys = [
        ...extractAcKeys(test && test.title),
        ...(test && typeof test.titlePath === 'function'
          ? extractAcKeys(test.titlePath().join(' '))
          : []),
      ];
      const keys = [...new Set([...annotationKeys, ...titleKeys])];

      records = keys.map((ac) => ({
        ac,
        status: mapAttemptStatus(result, blockedReason),
        coverage: 'full',
        duration_ms: Number((result && result.duration) || 0),
        reason: blockedReason || errorMessage(result && result.error),
      }));
    }

    // Apply per-AC runtime outcomes after step inference. This allows a
    // stateful scenario to BLOCK only the ACs whose fixture/precondition is
    // unavailable, while preserving earlier valid AC evidence.
    const byAc = new Map(records.map((record) => [record.ac, { ...record }]));
    for (const [ac, override] of overrides.entries()) {
      const record = byAc.get(ac) || {
        ac,
        status: override.status || 'manual',
        coverage: override.coverage || 'full',
        duration_ms: 0,
        reason: null,
      };
      if (override.status) record.status = override.status;
      if (override.coverage) record.coverage = override.coverage;
      if (override.reasons.length) {
        record.reason = [record.reason, ...override.reasons].filter(Boolean).join(' | ');
      }
      byAc.set(ac, record);
    }
    records = [...byAc.values()];

    // Conservative fallback: if the test failed outside an AC-labeled step
    // (for example teardown/global assertion), do not emit a false-green set
    // of AC records. A project adapter may classify known environment failures
    // as crew-blocked before the test ends.
    if (
      !blockedReason &&
      result &&
      result.status === 'failed' &&
      records.length &&
      !records.some((record) => record.status === 'failed')
    ) {
      const unscopedError =
        errorMessage(result.error) ||
        errorMessage(Array.isArray(result.errors) ? result.errors[0] : null) ||
        'test failed outside AC-labeled step';
      records = records.map((record) =>
        record.status === 'passed'
          ? { ...record, status: 'failed', reason: unscopedError }
          : record
      );
    }

    for (const record of records) {
      const key = `${testId}::${record.ac}`;
      if (!this.groups.has(key)) {
        this.groups.set(key, {
          ac: record.ac,
          scenario,
          attempts: [],
        });
      }
      this.groups.get(key).attempts.push({
        status: record.status,
        coverage: record.coverage || 'full',
        duration_ms: record.duration_ms,
        reason: record.reason,
        evidence,
        retry: Number((result && result.retry) || 0),
      });
    }
  }

  onEnd() {
    try {
      const results = [...this.groups.values()]
      .map((group) => {
        const attempts = group.attempts;
        const status = finalStatus(attempts);
        const last = attempts[attempts.length - 1] || {};
        const previousReason = attempts.find((item) => item.reason);

        return {
          ac: group.ac,
          scenario: group.scenario,
          status,
          coverage: last.coverage || 'full',
          attempts: attempts.length,
          duration_ms: attempts.reduce((sum, item) => sum + Number(item.duration_ms || 0), 0),
          reason: last.reason || (status === 'flaky' && previousReason ? previousReason.reason : null),
          evidence: last.evidence || { trace: null, screenshot: null, video: null },
        };
      })
      .sort((a, b) => a.ac.localeCompare(b.ac) || a.scenario.localeCompare(b.scenario));

    const payload = {
      schema_version: 1,
      runner: 'playwright',
      environment: this.environment,
      git_sha:
        process.env.GITHUB_SHA ||
        process.env.CI_COMMIT_SHA ||
        process.env.GIT_COMMIT ||
        null,
      run_id:
        process.env.GITHUB_RUN_ID ||
        process.env.CI_PIPELINE_ID ||
        process.env.BUILD_ID ||
        null,
      results,
    };

      const outputPath = path.resolve(this.outputFile);
      fs.mkdirSync(path.dirname(outputPath), { recursive: true });
      fs.writeFileSync(outputPath, JSON.stringify(payload, null, 2) + '\n', 'utf8');
      console.log(`[crew-reporter] wrote ${results.length} AC result(s) to ${this.outputFile}`);
      return undefined;
    } catch (error) {
      // Playwright can swallow reporter exceptions. Return an explicit failed
      // run status so a broken CREW result artifact cannot make CI look green.
      console.error(`[crew-reporter] failed to write ${this.outputFile}: ${error && error.message ? error.message : error}`);
      return { status: 'failed' };
    }
  }
}

module.exports = CrewReporter;
module.exports._internals = {
  extractAcKeys,
  finalStatus,
  collectStepRecords,
  mergeAttemptRecords,
  annotationsOf,
  acStatusPayloads,
  acStatusOverrides,
};
