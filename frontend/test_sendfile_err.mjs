import express from 'express';
import path from 'path';
import { fileURLToPath } from 'url';
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const app = express();
app.disable('x-powered-by');

app.get('*', (req, res) => res.sendFile(path.join(__dirname, 'NON_EXISTENT.html')));
app.listen(10010, () => console.log('listening'));
