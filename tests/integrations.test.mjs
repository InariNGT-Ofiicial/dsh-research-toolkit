import assert from 'node:assert/strict';
import test from 'node:test';
import { integrationSnapshot } from '../src/integrations.js';

test('companion discovery follows caller scope and never elevates registration to execution', () => {
  const agent = {};
  const tool = { name: 'mcp__matlab__check_matlab_code', parameters: {type:'object'} };
  const runtime = { schemas(scope) { assert.equal(scope, agent); return [tool, {name:'hidden_unrelated'}]; } };
  const data = integrationSnapshot(runtime, agent);
  assert.deepEqual(data.integrations[0].tools, [{...tool, description:''}]);
  assert.equal(data.integrations[0].status, 'tools_registered');
  assert.equal(data.integrations[0].application_verified, false);
  assert.equal(data.integrations[1].status, 'not_registered');
  assert.equal(integrationSnapshot({schemas:()=>[]}, agent).integrations[0].tools.length, 0);
});
