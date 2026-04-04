import express from 'express';
const app = express();
app.disable('x-powered-by');
app.get('*', (req, res, next) => {
  next(); // Simulate fallthrough
});
app.listen(10014, () => console.log('listening'));
