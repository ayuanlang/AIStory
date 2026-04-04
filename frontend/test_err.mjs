import express from 'express';
const app = express();
app.get('*', (req, res) => res.sendFile('C:/BOGUS/PATH.html'));
app.listen(10084, () => console.log('started'));
