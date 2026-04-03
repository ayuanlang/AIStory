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
const backendProxyTimeoutMsRaw = Number(process.env.BACKEND_PROXY_TIMEOUT_MS || 610000);
const backendProxyTimeoutMs = Number.isFinite(backendProxyTimeoutMsRaw)
  ? Math.max(30000, Math.min(1800000, Math.floor(backendProxyTimeoutMsRaw)))
  : 610000;

const createScopedProxy = (scopePath) => createProxyMiddleware({
  target: backendTarget,
  changeOrigin: true,
  xfwd: true,
  secure: true,
  proxyTimeout: backendProxyTimeoutMs,
  timeout: backendProxyTimeoutMs,
  pathRewrite: (path, req) => {
    // If app.use('/api', proxy) is used, the proxy receives '/api/...'.
    // We want to send that exactly to the backend target, which acts as the root.
    return path;
  },
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
  console.log(`[frontend] listening on ${port}, proxying api to ${backendTarget}, timeout=${backendProxyTimeoutMs}ms`);
});