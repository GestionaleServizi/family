require('dotenv').config();

const express = require('express');
const cors = require('cors');
const bcrypt = require('bcrypt');
const jwt = require('jsonwebtoken');
const { Pool } = require('pg');

const app = express();

// PostgreSQL Railway
const pool = new Pool({
  connectionString: process.env.DATABASE_URL,
  ssl: {
    rejectUnauthorized: false
  }
});

// Middleware
app.use(cors({
  origin: [
    'https://familycontrol-frontend-production.up.railway.app'
      ],
  methods: ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
  allowedHeaders: ['Content-Type', 'Authorization']
}));

app.use(express.json());

// Health check
app.get('/health', (req, res) => {
  res.json({
    status: 'ok',
    database: 'connected'
  });
});

// Login PostgreSQL + JWT
app.post('/api/auth/login', async (req, res) => {
  try {
    const { username, password } = req.body;

    if (!username || !password) {
      return res.status(400).json({
        error: 'Username e password obbligatori'
      });
    }

    // Cerca utente
    const result = await pool.query(
      'SELECT * FROM users WHERE username = $1',
      [username]
    );

    if (result.rows.length === 0) {
      return res.status(401).json({
        error: 'Utente non trovato'
      });
    }

    const user = result.rows[0];

    // Verifica password bcrypt
    const validPassword = await bcrypt.compare(
      password,
      user.password_hash
    );

    if (!validPassword) {
      return res.status(401).json({
        error: 'Password non valida'
      });
    }

    // JWT token
    const token = jwt.sign(
      {
        id: user.id,
        username: user.username,
        email: user.email
      },
      process.env.JWT_SECRET,
      {
        expiresIn: '24h'
      }
    );

    res.json({
      token,
      user: {
        id: user.id,
        username: user.username,
        email: user.email
      }
    });

  } catch (error) {
    console.error('LOGIN ERROR:', error);

    res.status(500).json({
      error: 'Errore server'
    });
  }
});

// Route temporanea reset password
app.post('/api/debug/reset-password', async (req, res) => {
  try {
    const { username, password, secret } = req.body;

    if (secret !== process.env.RESET_SECRET) {
      return res.status(403).json({
        error: 'Forbidden'
      });
    }

    const hash = await bcrypt.hash(password, 10);

    await pool.query(
      'UPDATE users SET password_hash = $1 WHERE username = $2',
      [hash, username]
    );

    res.json({
      status: 'ok',
      username,
      message: 'Password aggiornata'
    });

  } catch (error) {
    console.error('RESET ERROR:', error);

    res.status(500).json({
      error: 'Errore reset password'
    });
  }
});

// Test devices route
app.get('/api/devices', (req, res) => {
  res.json([
    {
      id: 1,
      name: 'Samsung Galaxy',
      status: 'online'
    },
    {
      id: 2,
      name: 'iPhone',
      status: 'offline'
    }
  ]);
});

const PORT = process.env.PORT || 3000;

app.listen(PORT, () => {
  console.log(`✅ Server running on port ${PORT}`);
});
