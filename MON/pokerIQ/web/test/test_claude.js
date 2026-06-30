/* Claude analysis module test — verifies request shape, header set, response
 * parsing, error handling, and key storage, all against a fake fetch (no real
 * network). Run: node test/test_claude.js */
require('../src/analytics.js');                 // exports __piqStore
const PC = require('../src/claude.js');

let pass = 0, fail = 0;
const ok = (c, m) => { if (c) pass++; else { fail++; console.log('  FAIL:', m); } };

// fake fetch capturing the request, returning a canned Messages API response
function fakeFetch(captured, status, payload) {
  return async (url, init) => {
    captured.url = url; captured.init = init; captured.body = JSON.parse(init.body);
    return {
      ok: status >= 200 && status < 300,
      status,
      json: async () => payload,
    };
  };
}

(async () => {
  // key storage
  PC.setKey('sk-ant-test');
  ok(PC.getKey() === 'sk-ant-test' && PC.hasKey(), 'key round-trips through store');

  // critique request shape + headers + parsing
  let cap = {};
  let res = await PC.analyzeOne({ name: 'Hero', seat: 0 }, 'HAND TEXT', {
    key: 'sk-ant-test', mode: 'critique',
    fetchFn: fakeFetch(cap, 200, { content: [{ type: 'text', text: 'You played it well.' }], stop_reason: 'end_turn' }),
  });
  ok(cap.url === 'https://api.anthropic.com/v1/messages', 'POSTs to the Messages endpoint');
  ok(cap.init.headers['x-api-key'] === 'sk-ant-test', 'sends x-api-key');
  ok(cap.init.headers['anthropic-version'] === '2023-06-01', 'sends anthropic-version');
  ok(cap.init.headers['anthropic-dangerous-direct-browser-access'] === 'true', 'sends browser-access header');
  ok(cap.body.model === 'claude-opus-4-8', 'uses claude-opus-4-8');
  ok(cap.body.thinking && cap.body.thinking.type === 'adaptive', 'uses adaptive thinking (not budget_tokens)');
  ok(cap.body.thinking.budget_tokens === undefined, 'no budget_tokens (would 400 on 4.8)');
  ok(/Critique this poker hand from Hero/.test(cap.body.messages[0].content), 'critique prompt names the POV');
  ok(res.text === 'You played it well.' && res.seat === 0, 'parses the text response');

  // annotate mode adds RETROSPECTIVE instructions + line count
  cap = {};
  await PC.analyzeOne({ name: 'Hero', seat: 0 }, 'HAND', {
    key: 'k', mode: 'annotate', lineCount: 5, wordLimit: 120,
    fetchFn: fakeFetch(cap, 200, { content: [{ type: 'text', text: '1. ok' }] }),
  });
  ok(/RETROSPECTIVE/.test(cap.body.messages[0].content) && /1\.\.5/.test(cap.body.messages[0].content), 'annotate prompt has line range + retrospective');

  // API error surfaces inline (not thrown)
  res = await PC.analyzeOne({ name: 'Hero', seat: 0 }, 'HAND', {
    key: 'k', fetchFn: fakeFetch({}, 401, { error: { message: 'invalid x-api-key' } }),
  });
  ok(/API error 401/.test(res.text) && /invalid x-api-key/.test(res.text), 'API error returned inline');

  // refusal handled
  res = await PC.analyzeOne({ name: 'Hero', seat: 0 }, 'HAND', {
    key: 'k', fetchFn: fakeFetch({}, 200, { content: [], stop_reason: 'refusal' }),
  });
  ok(/declined/.test(res.text), 'refusal handled gracefully');

  // missing key short-circuits without a request
  PC.setKey('');
  res = await PC.analyzeOne({ name: 'Hero', seat: 0 }, 'HAND', { fetchFn: fakeFetch({}, 200, {}) });
  ok(/no API key/.test(res.text), 'missing key short-circuits');

  // analyze() loops POVs and reports progress
  PC.setKey('k');
  let prog = 0;
  const results = await PC.analyze({
    povs: [{ name: 'A', seat: 0 }, { name: 'B', seat: 1 }], handText: 'H', mode: 'critique',
    fetchFn: fakeFetch({}, 200, { content: [{ type: 'text', text: 'ok' }] }),
    onProgress: () => { prog++; },
  });
  ok(results.length === 2 && prog === 2, 'analyze loops every POV with progress');

  PC.setKey('');
  console.log(fail ? `\n✗ ${fail} FAILED, ${pass} passed` : `\n✓ ALL PASS — ${pass} passed, 0 failed`);
  process.exit(fail ? 1 : 0);
})();
