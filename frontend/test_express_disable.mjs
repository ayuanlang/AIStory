import express from 'express';
const app = express();
app.disable('x-powered-by');
app.get('/foo', (req, res) => res.send('foo'));
app.listen(10019);
