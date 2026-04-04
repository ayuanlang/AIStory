import express from 'express';
import { createProxyMiddleware } from 'http-proxy-middleware';

const app = express();
app.disable('x-powered-by');

app.use(createProxyMiddleware({
  pathFilter: (pathname) => pathname.startsWith('/api'),
  target: 'https://httpbin.org',
  changeOrigin: true,
  onProxyRes: (proxyRes) => {
    proxyRes.headers['x-added-by-me'] = 'my-proxy';
  }
}));

app.listen(10015, () => console.log('listening'));
