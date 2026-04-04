import express from 'express';
import { createProxyMiddleware } from 'http-proxy-middleware';

const app = express();
app.use(createProxyMiddleware({
  pathFilter: ['/api/**', '/uploads/**'],
  target: 'https://aistory-backend-xggg.onrender.com',
  changeOrigin: true
}));

app.get('*', (req, res) => res.status(404).send('Not Found By Node'));

app.listen(10087, () => console.log('started'));
