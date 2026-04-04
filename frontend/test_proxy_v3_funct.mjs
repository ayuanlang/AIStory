import express from 'express';
import { createProxyMiddleware } from 'http-proxy-middleware';

const app = express();
app.use(createProxyMiddleware({
  pathFilter: (pathname) => pathname.startsWith('/api'),
  target: 'https://httpbin.org',
  changeOrigin: true
}));

app.listen(10012, () => console.log('listening'));
