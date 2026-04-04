import express from 'express';
import { createProxyMiddleware } from 'http-proxy-middleware';
const app = express();
app.use('/api', createProxyMiddleware({ target: 'https://httpbin.org', changeOrigin: true }));
app.listen(10003, () => console.log('listening'));
