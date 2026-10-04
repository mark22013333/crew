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

function annotationsOf(test) {
  return Array.isArray(test && test.annotations) ? test.annotations : [];
}

function annotationValues(test, type) {
  return annotationsOf(test)
    .filter((item) => item && item.type === type && item.description)
    .map((item) => String(item.description));
}

function scenarioOf(test) {
  const annotated = annotationValues(test, 'crew-scenario')[0];
  if (annotated) return annotated;

  if (test && typeof test.titlePath === 'function') {
    const parts = test.titlePath().filter(Boolean);
    if (parts.length) return parts.join(' > ');
  }
  return test && test.title ? String(test.title) : 'unknown';
}

function blockedReasonOf(test) {
  return annotationValues(test, 'crew-blocked')[0] || null;
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

function collectStepRecords(steps, blockedReason) {
  const records = [];
  for (const step of Array.isArray(steps) ? steps : []) {
    const keys = extractAcKeys(step && step.title);
    for (const ac of keys) {
      records.push({
        ac,
        status: blockedReason ? 'blocked' : (step.error ? 'failed' : 'passed'),
        duration_ms: Number(step.duration || 0),
        reason: blockedReason || errorMessage(step.error),
      });
    }
    records.push(...collectStepRecords(step && step.steps, blockedReason));
  }
  return records;
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
    const blockedReason = blockedReasonOf(test);
    const stepRecords = collectStepRecords(result && result.steps, blockedReason);
    const evidence = evidenceOf(result);
    const scenario = scenarioOf(test);
    const testId = test && test.id ? String(test.id) : scenario;

    let records = stepRecords;

    if (!records.length) {
      const annotationKeys = annotationValues(test, 'crew-ac').flatMap(extractAcKeys);
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
    annotations: [
      { type: 'crew-ac', description: 'feature-a#AC-3' },
      { type: 'crew-blocked', description: 'fixture unavailable' },
    ],
    titlePath: () => ['suite', 'feature-a#AC-3 fixture'],
  };
  reporter.onTestEnd(blockedTest, {
    status: 'skipped',
    retry: 0,
    duration: 1,
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

  reporter.onEnd();
  const payload = JSON.parse(fs.readFileSync(output, 'utf8'));
  const byAc = Object.fromEntries(payload.results.map((item) => [item.ac, item]));

  assert.equal(payload.schema_version, 1);
  assert.equal(byAc['feature-a#AC-1'].status, 'passed');
  assert.equal(byAc['feature-a#AC-2'].status, 'flaky');
  assert.equal(byAc['feature-a#AC-2'].attempts, 2);
  assert.equal(byAc['feature-a#AC-3'].status, 'blocked');
  assert.equal(byAc['feature-a#AC-3'].reason, 'fixture unavailable');
  assert.equal(byAc['feature-b#AC-1'].status, 'passed');
  assert.equal(byAc['feature-b#AC-2'].status, 'failed');

  console.log('✅ crew-reporter self-test passed');
}

module.exports = CrewReporter;
module.exports._internals = {
  extractAcKeys,
  finalStatus,
  collectStepRecords,
};

if (require.main === module) {
  selfTest();
}
