import express from 'express';
import { createProxyMiddleware } from 'http-proxy-middleware';

const app = express();
const createScopedProxy = (scopePath) => createProxyMiddleware({
  pathFilter: scopePath,
  target: 'https://httpbin.org',
  changeOrigin: true
});

app.use(createScopedProxy('/api'));
app.listen(10004, () => console.log('listening'));
