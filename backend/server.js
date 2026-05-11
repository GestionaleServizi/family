const express = require('express');
const cors = require('cors');
const helmet = require('helmet');
const { Pool } = require('pg');
const jwt = require('jsonwebtoken');
const bcrypt = require('bcrypt');
require('dotenv').config();

const app = express();
const PORT = process.env.PORT || 3000;

// Middleware
app.use(helmet());
app.use(cors());
app.use(express.json());

// Database
const pool = new Pool({
  connectionString: process.env.DATABASE_URL,
  ssl: { rejectUnauthorized: false }
});

// Health check
app.get('/health', (req, res) => {
  res.json({ status: 'ok', timestamp: new Date() });
});

// Login
app.post('/api/auth/login', async (req, res) => {
  const { username, password } = req.body;
  
  try {
    const result = await pool.query('SELECT * FROM users WHERE username = $1', [username]);
    
    if (result.rows.length === 0) {
      return res.status(401).json({ error: 'Credenziali non valide' });
    }
    
    const valid = await bcrypt.compare(password, result.rows[0].password_hash);
    
    if (!valid) {
      return res.status(401).json({ error: 'Credenziali non valide' });
    }
    
    const token = jwt.sign(
      { userId: result.rows[0].id, username: result.rows[0].username },
      process.env.JWT_SECRET,
      { expiresIn: '24h' }
    );
    
    res.json({ token, user: { id: result.rows[0].id, username: result.rows[0].username } });
  } catch (error) {
    res.status(500).json({ error: 'Errore server' });
  }
});

app.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
});
