import express from 'express';
import { createProxyMiddleware } from 'http-proxy-middleware';

const app = express();
app.use(createProxyMiddleware({
  pathFilter: '/api',
  target: 'https://httpbin.org',
  changeOrigin: true
}));

app.listen(10005, () => console.log('listening'));
