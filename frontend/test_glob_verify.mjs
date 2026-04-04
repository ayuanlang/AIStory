import express from 'express';
import { createProxyMiddleware } from 'http-proxy-middleware';
const app = express();
app.use(createProxyMiddleware({ pathFilter: '/api', target: 'https://httpbin.org', changeOrigin: true }));
app.get('*', (req, res) => res.send('EXPRESS MATCH: ' + req.path));
app.listen(10009);
