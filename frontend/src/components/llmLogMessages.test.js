import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { extractLogMessages } from './llmLogMessages.js';

describe('extractLogMessages', () => {
  it('splits chat completions messages inside payload', () => {
    const rows = extractLogMessages({
      provider: 'grsai',
      payload: {
        model: 'gpt-6.1-sol',
        messages: [
          { role: 'system', content: '技能' },
          { role: 'user', content: '项目信息' },
        ],
      },
    });
    assert.deepEqual(rows.map((row) => row.role), ['system', 'user']);
    assert.equal(rows[1].content, '项目信息');
  });

  it('splits responses input and keeps instructions as the system prompt', () => {
    const rows = extractLogMessages({
      payload: {
        instructions: '系统说明',
        input: [{ role: 'user', content: [{ type: 'input_text', text: '问句' }] }],
      },
    });
    assert.equal(rows[0].role, 'system');
    assert.equal(rows[0].content, '系统说明');
    assert.equal(rows[1].role, 'user');
  });

  it('splits Gemini contents into separate prompt blocks instead of the raw payload', () => {
    const rows = extractLogMessages({
      provider: 'kie',
      model: 'gemini-3-8-flash',
      payload: {
        stream: true,
        contents: [{
          role: 'user',
          parts: [
            { text: '# Prompt File: skills/scene_analysis' },
            { text: '[项目信息开始]' },
            { fileData: { mimeType: 'image/png', fileUri: 'https://cdn.example/ref.png' } },
          ],
        }],
        generationConfig: { thinkingConfig: { thinkingLevel: 'high' } },
      },
    });
    assert.equal(rows.length, 2);
    assert.deepEqual(rows.map((row) => row.role), ['user', 'user']);
    assert.equal(rows[0].content, '# Prompt File: skills/scene_analysis');
    assert.deepEqual(rows[1].content, [
      { type: 'text', text: '[项目信息开始]' },
      { type: 'image_url', image_url: { url: 'https://cdn.example/ref.png' } },
    ]);
  });

  it('reads Gemini contents nested under request.payload and maps model to assistant', () => {
    const rows = extractLogMessages({
      request: {
        url: 'https://api.example/gemini',
        payload: {
          contents: [
            { role: 'user', parts: [{ text: '问' }] },
            { role: 'model', parts: [{ text: '答' }] },
          ],
          systemInstruction: { parts: [{ text: '守则' }] },
        },
      },
    });
    assert.deepEqual(rows.map((row) => [row.role, row.content]), [
      ['system', '守则'],
      ['user', '问'],
      ['assistant', '答'],
    ]);
  });

  it('prepends a Claude system string that is not inside messages', () => {
    const rows = extractLogMessages({
      payload: {
        system: '克劳德系统',
        messages: [{ role: 'user', content: '用户句' }],
      },
    });
    assert.deepEqual(rows.map((row) => row.role), ['system', 'user']);
    assert.equal(rows[0].content, '克劳德系统');
  });

  it('returns null when the payload has no prompt text', () => {
    assert.equal(extractLogMessages({ payload: { stream: true, generationConfig: {} } }), null);
    assert.equal(extractLogMessages(null), null);
  });
});
