import express from 'express';
import { createProxyMiddleware } from 'http-proxy-middleware';

const app = express();
app.disable('x-powered-by');
app.use(createProxyMiddleware({
  pathFilter: '/api',
  target: 'http://localhost:59999', // Port that is offline
  changeOrigin: true
}));

app.get('*', (req, res) => res.send("CATCH ALL " + req.path));
app.listen(10007, () => console.log('listening'));
