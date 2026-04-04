import express from 'express';
import { createProxyMiddleware } from 'http-proxy-middleware';

const app = express();
const proxyMiddleware = createProxyMiddleware({
  target: 'https://aistory-backend-xggg.onrender.com',
  changeOrigin: true
});

app.use((req, res, next) => {
  if (req.url.startsWith('/api') || req.url.startsWith('/uploads')) {
    return proxyMiddleware(req, res, next);
  }
  next();
});

app.get('*', (req, res) => res.status(404).send('Node proxy fallback HTML 404'));

const server = app.listen(10080, async () => {
    console.log('started');
    const http = await import('http');
    http.get('http://localhost:10080/api/v1/projects/review_threads/inbox', res => {
        let text = '';
        res.on('data', d => text+=d);
        res.on('end', () => {
            console.log('Status code:', res.statusCode);
            console.log('Response body:', text);
            process.exit(0);
        });
    });
});
