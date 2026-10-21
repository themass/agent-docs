import { test } from 'node:test';
import assert from 'node:assert/strict';
import config from '../next.config.ts';

test('proxy exceeds the maximum backend review budget, instead of Next 30s default', () => {
  assert.ok(config.experimental.proxyTimeout > 120_000);
  assert.ok(config.experimental.proxyTimeout <= 300_000);
});

// Opt-in: real local sockets, no application server or production API involved.
if (process.env.RUN_PROXY_INTEGRATION === '1') {
  test('real Next proxy receives a reviewer response later than 30 seconds', { timeout: 40_000 }, async () => {
    const { createServer } = await import('node:http');
    const { parse } = await import('node:url');
    const { createRequire } = await import('node:module');
    const require = createRequire(import.meta.url);
    const { proxyRequest } = require('next/dist/server/lib/router-utils/proxy-request.js');
    const upstream = createServer((_req, res) => {
      setTimeout(() => {
        res.setHeader('Content-Type', 'application/json');
        res.end(JSON.stringify({ status: 'passed', reviewed: true }));
      }, 31_000);
    });
    const listen = (server) => new Promise((resolve, reject) => {
      server.once('error', reject);
      server.listen(0, '127.0.0.1', resolve);
    });
    let proxy;
    try {
      await listen(upstream);
      const target = `http://127.0.0.1:${upstream.address().port}/review`;
      proxy = createServer((req, res) => {
        proxyRequest(req, res, parse(target, true), undefined, undefined,
          config.experimental.proxyTimeout).catch((error) => res.destroy(error));
      });
      await listen(proxy);
      const response = await fetch(`http://127.0.0.1:${proxy.address().port}/review`);
      assert.equal(response.status, 200);
      assert.deepEqual(await response.json(), { status: 'passed', reviewed: true });
    } finally {
      proxy?.closeAllConnections();
      proxy?.close();
      upstream.closeAllConnections();
      upstream.close();
    }
  });
}
