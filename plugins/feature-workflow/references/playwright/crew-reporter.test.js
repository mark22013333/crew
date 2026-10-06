'use strict';

const fs = require('fs');
const os = require('os');
const path = require('path');
const assert = require('assert');
const CrewReporter = require('./crew-reporter');

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

  // One late fixture may block only selected ACs in a stateful scenario.
  const targetedBlockedTest = {
    id: 't8',
    title: 'targeted block',
    annotations: [],
    titlePath: () => ['suite', 'targeted block'],
  };
  reporter.onTestEnd(targetedBlockedTest, {
    status: 'passed',
    retry: 0,
    duration: 8,
    annotations: [
      {
        type: 'crew-ac-status',
        description: JSON.stringify({
          ac: 'feature-f#AC-5',
          status: 'blocked',
          reason: 'schedule fixture mismatch',
        }),
      },
      {
        type: 'crew-ac-status',
        description: JSON.stringify({
          ac: 'feature-f#AC-9',
          coverage: 'partial',
          reason: 'browser half only',
        }),
      },
    ],
    attachments: [],
    steps: [
      { title: 'feature-f#AC-1 early evidence', duration: 3, steps: [] },
      { title: 'feature-f#AC-9 frontend evidence', duration: 5, steps: [] },
    ],
  });

  const attachmentOnlyStatusTest = {
    id: 't10',
    title: 'attachment compatibility',
    annotations: [],
    titlePath: () => ['suite', 'attachment compatibility'],
  };
  reporter.onTestEnd(attachmentOnlyStatusTest, {
    status: 'skipped',
    retry: 0,
    duration: 1,
    attachments: [
      {
        name: 'crew-ac-status',
        contentType: 'application/json',
        body: Buffer.from(JSON.stringify({
          ac: 'feature-h#AC-2',
          status: 'blocked',
          reason: 'runtime attachment fallback',
        })),
      },
    ],
    steps: [],
  });

  const targetedBlockedWithSafetyFailure = {
    id: 't9',
    title: 'targeted block plus global safety failure',
    annotations: [],
    titlePath: () => ['suite', 'targeted block plus global safety failure'],
  };
  reporter.onTestEnd(targetedBlockedWithSafetyFailure, {
    status: 'failed',
    retry: 0,
    duration: 9,
    error: { message: 'forbidden request observed' },
    annotations: [
      {
        type: 'crew-ac-status',
        description: JSON.stringify({
          ac: 'feature-g#AC-5',
          status: 'blocked',
          reason: 'fixture mismatch',
        }),
      },
    ],
    attachments: [],
    steps: [
      { title: 'feature-g#AC-1 browser evidence', duration: 4, steps: [] },
      { title: 'afterEach safety guard', duration: 5, error: { message: 'forbidden request observed' }, steps: [] },
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
  assert.equal(byAc['feature-f#AC-1'].status, 'passed');
  assert.equal(byAc['feature-f#AC-5'].status, 'blocked');
  assert.equal(byAc['feature-f#AC-5'].reason, 'schedule fixture mismatch');
  assert.equal(byAc['feature-f#AC-9'].status, 'passed');
  assert.equal(byAc['feature-f#AC-9'].coverage, 'partial');
  assert.equal(byAc['feature-g#AC-1'].status, 'failed');
  assert.equal(byAc['feature-g#AC-5'].status, 'blocked');
  assert.equal(byAc['feature-h#AC-2'].status, 'blocked');
  assert.equal(byAc['feature-h#AC-2'].reason, 'runtime attachment fallback');

  const brokenReporter = new CrewReporter({ outputFile: dir, environment: 'self-test' });
  const brokenResult = brokenReporter.onEnd();
  assert.equal(brokenResult && brokenResult.status, 'failed');

  console.log('✅ crew-reporter self-test passed');
}

selfTest();
