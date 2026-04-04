import express from 'express';
import { createProxyMiddleware } from 'http-proxy-middleware';
import path from 'path';
const app = express();
app.disable('x-powered-by');

app.get('*', (req, res) => res.sendFile(path.join(__dirname, 'BOGUS_FILE.html')));
app.listen(10008, () => console.log('listening'));
