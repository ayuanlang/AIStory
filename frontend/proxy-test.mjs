import express from 'express';
import { createProxyMiddleware } from 'http-proxy-middleware';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const app = express();

const createScopedProxy = (scopePath) => createProxyMiddleware({
  pathFilter: (pathname) => pathname.startsWith(scopePath),
  target: 'https://httpbin.org',
  changeOrigin: true
});

app.use(createScopedProxy('/api'));
app.get('*', (req, res) => res.status(404).send('My Custom 404'));

app.listen(10081);
console.log('started');
