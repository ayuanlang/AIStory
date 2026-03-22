import express from 'express';
import path from 'path';
import { fileURLToPath } from 'url';
import { createProxyMiddleware } from 'http-proxy-middleware';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const app = express();

const port = Number(process.env.PORT || 10000);
const distDir = path.join(__dirname, 'dist');
const indexPath = path.join(distDir, 'index.html');
const backendTarget = String(process.env.BACKEND_PROXY_TARGET || 'https://aistory-backend-xggg.onrender.com').trim();

const createScopedProxy = (scopePath) => createProxyMiddleware({
  target: `${backendTarget}${scopePath}`,
  changeOrigin: true,
  xfwd: true,
  secure: true,
  proxyTimeout: 65000,
  timeout: 65000,
  onProxyReq(proxyReq) {
    proxyReq.setHeader('X-Forwarded-Host', 'aistory-frontend.onrender.com');
  },
});

app.disable('x-powered-by');

app.use('/api', createScopedProxy('/api'));
app.use('/uploads', createScopedProxy('/uploads'));

app.use(express.static(distDir, {
  etag: true,
  maxAge: '1y',
  index: false,
  setHeaders(res, filePath) {
    if (filePath.endsWith('.html')) {
      res.setHeader('Cache-Control', 'no-store, no-cache, must-revalidate');
      return;
    }
    if (filePath.includes(`${path.sep}assets${path.sep}`)) {
      res.setHeader('Cache-Control', 'public, max-age=31536000, immutable');
    }
  },
}));

app.get('*', (_req, res) => {
  res.setHeader('Cache-Control', 'no-store, no-cache, must-revalidate');
  res.sendFile(indexPath);
});

app.listen(port, () => {
  console.log(`[frontend] listening on ${port}, proxying api to ${backendTarget}`);
});