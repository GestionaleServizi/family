require('dotenv').config();

const express = require('express');
const cors = require('cors');
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

// Middleware CORS
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
app.get('/health', async (req, res) => {
  try {
    await pool.query('SELECT 1');

    res.json({
      status: 'ok',
      database: 'connected'
    });
  } catch (error) {
    console.error('DB HEALTH ERROR:', error);

    res.status(500).json({
      status: 'error',
      database: 'disconnected'
    });
  }
});

// Login TEMPORANEO con password in chiaro
app.post('/api/auth/login', async (req, res) => {
  try {
    const { username, password } = req.body;

    if (!username || !password) {
      return res.status(400).json({
        error: 'Username e password obbligatori'
      });
    }

    const result = await pool.query(
      'SELECT id, username, password_hash, email FROM users WHERE username = $1',
      [username]
    );

    if (result.rows.length === 0) {
      return res.status(401).json({
        error: 'Utente non trovato'
      });
    }

    const user = result.rows[0];

    // TEST TEMPORANEO: confronto password in chiaro
    if (password !== user.password_hash) {
      return res.status(401).json({
        error: 'Password non valida'
      });
    }

    const token = jwt.sign(
      {
        id: user.id,
        username: user.username,
        email: user.email
      },
      process.env.JWT_SECRET || 'temporary_secret_for_test',
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

// Test route devices
app.get('/api/devices', async (req, res) => {
  try {
    const result = await pool.query(
      'SELECT id, name, device_type, status, last_seen, user_id FROM devices ORDER BY id ASC'
    );

    res.json(result.rows);
  } catch (error) {
    console.error('DEVICES ERROR:', error);

    res.status(500).json({
      error: 'Errore recupero dispositivi'
    });
  }
});

const PORT = process.env.PORT || 3000;

app.listen(PORT, () => {
  console.log(`✅ Server running on port ${PORT}`);
});
