import express from 'express';
import { createProxyMiddleware } from 'http-proxy-middleware';

const app = express();
app.disable('x-powered-by');
app.use(createProxyMiddleware({
  pathFilter: '/api',
  target: 'https://httpbin.org',
  changeOrigin: true
}));

app.get('*', (req, res) => res.send("CATCH ALL " + req.path));
app.listen(10006, () => console.log('listening'));
