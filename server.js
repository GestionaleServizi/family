const express = require('express');
const cors = require('cors');

const app = express();

app.use(cors({
  origin: [
    'https://familycontrol-frontend-production.up.railway.app',
    'http://localhost:3000'
  ],
  methods: ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
  allowedHeaders: ['Content-Type', 'Authorization']
}));

app.use(express.json());

// Health check
app.get('/health', (req, res) => {
  res.json({ status: 'ok' });
});

// Login - hardcoded per test
app.post('/api/auth/login', (req, res) => {
  const { username, password } = req.body;

  if (username === 'admin' && password === 'admin123') {
    res.json({
      token: 'test-token-123',
      user: { username: 'admin' }
    });
  } else {
    res.status(401).json({ error: 'Credenziali non valide' });
  }
});

const PORT = process.env.PORT || 3000;

app.listen(PORT, () => {
  console.log(`Server on ${PORT}`);
});
