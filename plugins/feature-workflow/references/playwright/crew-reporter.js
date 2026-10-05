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
 *   add annotation { type: "crew-blocked", description: "reason" }
 */

const fs = require('fs');
const os = require('os');
const path = require('path');
const assert = require('assert');

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
        duration_ms: 0,
        reasons: [],
      });
    }
    const merged = grouped.get(record.ac);
    merged.duration_ms += Number(record.duration_ms || 0);
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
        duration_ms: Number((result && result.duration) || 0),
        reason: blockedReason || errorMessage(result && result.error),
      }));
    }

    // Conservative fallback: if the test failed outside an AC-labeled step
    // (for example teardown/global assertion), do not emit a false-green set
    // of AC records. A project adapter may classify known environment failures
    // as crew-blocked before the test ends.
    if (
      !blockedReason &&
      result &&
      result.status === 'failed' &&
      records.length &&
      records.every((record) => record.status === 'passed')
    ) {
      const unscopedError =
        errorMessage(result.error) ||
        errorMessage(Array.isArray(result.errors) ? result.errors[0] : null) ||
        'test failed outside AC-labeled step';
      records = records.map((record) => ({
        ...record,
        status: 'failed',
        reason: unscopedError,
      }));
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
        duration_ms: record.duration_ms,
        reason: record.reason,
        evidence,
        retry: Number((result && result.retry) || 0),
      });
    }
  }

  onEnd() {
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
  }
}

function selfTest() {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'crew-reporter-'));
  const output = path.join(dir, 'crew-results.json');
  const reporter = new CrewReporter({ outputFile: output, environment: 'self-test' });

  const passedTest = {
    id: 't1',
    title: 'feature-a#AC-1 query',
    annotations: [{ type: 'crew-ac', description: 'feature-a#AC-1' }],
    titlePath: () => ['suite', 'feature-a#AC-1 query'],
  };
  reporter.onTestEnd(passedTest, {
    status: 'passed',
    retry: 0,
    duration: 10,
    attachments: [],
    steps: [],
  });

  const flakyTest = {
    id: 't2',
    title: 'feature-a#AC-2 save',
    annotations: [{ type: 'crew-ac', description: 'feature-a#AC-2' }],
    titlePath: () => ['suite', 'feature-a#AC-2 save'],
  };
  reporter.onTestEnd(flakyTest, {
    status: 'failed',
    retry: 0,
    duration: 20,
    error: { message: 'first attempt failed\nstack' },
    attachments: [],
    steps: [],
  });
  reporter.onTestEnd(flakyTest, {
    status: 'passed',
    retry: 1,
    duration: 15,
    attachments: [],
    steps: [],
  });

  const blockedTest = {
    id: 't3',
    title: 'feature-a#AC-3 fixture',
    annotations: [{ type: 'crew-ac', description: 'feature-a#AC-3' }],
    titlePath: () => ['suite', 'feature-a#AC-3 fixture'],
  };
  reporter.onTestEnd(blockedTest, {
    status: 'skipped',
    retry: 0,
    duration: 1,
    annotations: [
      { type: 'crew-ac', description: 'feature-a#AC-3' },
      { type: 'crew-blocked', description: 'fixture unavailable' },
      { type: 'skip', description: 'blocked precondition' },
    ],
    attachments: [],
    steps: [],
  });

  const steppedTest = {
    id: 't4',
    title: 'stateful scenario',
    annotations: [],
    titlePath: () => ['suite', 'stateful scenario'],
  };
  reporter.onTestEnd(steppedTest, {
    status: 'failed',
    retry: 0,
    duration: 30,
    attachments: [],
    steps: [
      { title: 'feature-b#AC-1 first step', duration: 10, steps: [] },
      { title: 'feature-b#AC-2 second step', duration: 20, error: { message: 'assert failed' }, steps: [] },
    ],
  });

  // Soft assertions can fail in a nested expect step while the parent
  // test.step itself has no direct error.
  const softStepTest = {
    id: 't5',
    title: 'soft stateful scenario',
    annotations: [],
    titlePath: () => ['suite', 'soft stateful scenario'],
  };
  reporter.onTestEnd(softStepTest, {
    status: 'failed',
    retry: 0,
    duration: 12,
    attachments: [],
    steps: [
      {
        title: 'feature-c#AC-1 soft checks',
        duration: 12,
        steps: [
          { title: 'expect.soft.toBe', duration: 2, error: { message: 'soft assertion failed' }, steps: [] },
        ],
      },
    ],
  });

  // Two steps may contribute evidence to the same AC in one run. They are
  // one attempt, not two retries.
  const repeatedAcTest = {
    id: 't6',
    title: 'repeated AC evidence',
    annotations: [],
    titlePath: () => ['suite', 'repeated AC evidence'],
  };
  reporter.onTestEnd(repeatedAcTest, {
    status: 'passed',
    retry: 0,
    duration: 9,
    attachments: [],
    steps: [
      { title: 'feature-d#AC-4 category search', duration: 4, steps: [] },
      { title: 'feature-d#AC-4 template search', duration: 5, steps: [] },
    ],
  });

  // A failure outside AC-labeled steps must not leave every AC green.
  const unscopedFailureTest = {
    id: 't7',
    title: 'unscoped failure',
    annotations: [],
    titlePath: () => ['suite', 'unscoped failure'],
  };
  reporter.onTestEnd(unscopedFailureTest, {
    status: 'failed',
    retry: 0,
    duration: 7,
    error: { message: 'teardown failed' },
    attachments: [],
    steps: [
      { title: 'feature-e#AC-1 main assertion', duration: 5, steps: [] },
      { title: 'afterEach', duration: 2, error: { message: 'teardown failed' }, steps: [] },
    ],
  });

  reporter.onEnd();
  const payload = JSON.parse(fs.readFileSync(output, 'utf8'));
  const byAc = Object.fromEntries(payload.results.map((item) => [item.ac, item]));

  assert.equal(payload.schema_version, 1);
  assert.equal(byAc['feature-a#AC-1'].status, 'passed');
  assert.equal(byAc['feature-a#AC-2'].status, 'flaky');
  assert.equal(byAc['feature-a#AC-2'].attempts, 2);
  assert.equal(byAc['feature-a#AC-3'].status, 'blocked');
  assert.equal(byAc['feature-a#AC-3'].reason, 'fixture unavailable');
  // A failure inside AC-2 must not erase a clean AC-1 result from the same
  // stateful scenario.
  assert.equal(byAc['feature-b#AC-1'].status, 'passed');
  assert.equal(byAc['feature-b#AC-2'].status, 'failed');
  assert.equal(byAc['feature-c#AC-1'].status, 'failed');
  assert.equal(byAc['feature-c#AC-1'].reason, 'soft assertion failed');
  assert.equal(byAc['feature-d#AC-4'].status, 'passed');
  assert.equal(byAc['feature-d#AC-4'].attempts, 1);
  assert.equal(byAc['feature-e#AC-1'].status, 'failed');
  assert.equal(byAc['feature-e#AC-1'].reason, 'teardown failed');

  console.log('✅ crew-reporter self-test passed');
}

module.exports = CrewReporter;
module.exports._internals = {
  extractAcKeys,
  finalStatus,
  collectStepRecords,
  mergeAttemptRecords,
  annotationsOf,
};

if (require.main === module) {
  selfTest();
}
