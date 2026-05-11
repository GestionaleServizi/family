const express = require('express');
const cors = require('cors');
const helmet = require('helmet');
const { Pool } = require('pg');
const jwt = require('jsonwebtoken');
const bcrypt = require('bcrypt');
require('dotenv').config();

const app = express();
const PORT = process.env.PORT || 3000;

// ==================== CONFIGURAZIONE CORS ====================
app.use(cors({
  origin: [
    'https://familycontrol-frontend-production.up.railway.app',
    'https://familycontrol-frontend.up.railway.app'
      ],
  credentials: true,
  methods: ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
  allowedHeaders: ['Content-Type', 'Authorization']
}));

// ==================== MIDDLEWARE ====================
app.use(helmet({
  crossOriginResourcePolicy: { policy: "cross-origin" }
}));
app.use(express.json());

// Logging per debug
app.use((req, res, next) => {
  console.log(`📡 ${req.method} ${req.url} from ${req.headers.origin || 'unknown'}`);
  next();
});

// ==================== DATABASE ====================
const pool = new Pool({
  connectionString: process.env.DATABASE_URL,
  ssl: { rejectUnauthorized: false }
});

// Test database connection
pool.connect((err, client, release) => {
  if (err) {
    console.error('❌ Errore connessione database:', err.stack);
  } else {
    console.log('✅ Database connesso');
    release();
  }
});

// ==================== ROUTES ====================

// Health check
app.get('/health', (req, res) => {
  res.json({ status: 'ok', timestamp: new Date().toISOString() });
});

// Login
app.post('/api/auth/login', async (req, res) => {
  const { username, password } = req.body;
  
  console.log(`🔐 Tentativo login per: ${username}`);
  
  try {
    const result = await pool.query(
      'SELECT * FROM users WHERE username = $1',
      [username]
    );
    
    if (result.rows.length === 0) {
      console.log(`❌ Utente non trovato: ${username}`);
      return res.status(401).json({ error: 'Credenziali non valide' });
    }
    
    const user = result.rows[0];
    const valid = await bcrypt.compare(password, user.password_hash);
    
    if (!valid) {
      console.log(`❌ Password errata per: ${username}`);
      return res.status(401).json({ error: 'Credenziali non valide' });
    }
    
    const token = jwt.sign(
      { userId: user.id, username: user.username },
      process.env.JWT_SECRET || 'secretkey',
      { expiresIn: '24h' }
    );
    
    console.log(`✅ Login riuscito per: ${username}`);
    res.json({ 
      token, 
      user: { 
        id: user.id, 
        username: user.username,
        email: user.email 
      } 
    });
    
  } catch (error) {
    console.error('Errore login:', error);
    res.status(500).json({ error: 'Errore server' });
  }
});

// Verifica token
app.get('/api/verify', async (req, res) => {
  const token = req.headers.authorization?.split(' ')[1];
  
  if (!token) {
    return res.status(401).json({ error: 'Token mancante' });
  }
  
  try {
    const decoded = jwt.verify(token, process.env.JWT_SECRET || 'secretkey');
    res.json({ valid: true, user: decoded });
  } catch (error) {
    res.status(401).json({ error: 'Token non valido' });
  }
});

// Lista dispositivi
app.get('/api/devices', async (req, res) => {
  const token = req.headers.authorization?.split(' ')[1];
  
  if (!token) {
    return res.status(401).json({ error: 'Token mancante' });
  }
  
  try {
    const decoded = jwt.verify(token, process.env.JWT_SECRET || 'secretkey');
    
    const result = await pool.query(
      'SELECT * FROM devices WHERE user_id = $1 ORDER BY last_seen DESC',
      [decoded.userId]
    );
    
    res.json(result.rows);
  } catch (error) {
    console.error('Errore devices:', error);
    res.status(401).json({ error: 'Token non valido' });
  }
});

// Registrazione dispositivo
app.post('/api/devices/register', async (req, res) => {
  const token = req.headers.authorization?.split(' ')[1];
  const { deviceId, deviceName, deviceType } = req.body;
  
  if (!token) {
    return res.status(401).json({ error: 'Token mancante' });
  }
  
  try {
    const decoded = jwt.verify(token, process.env.JWT_SECRET || 'secretkey');
    
    const result = await pool.query(
      `INSERT INTO devices (id, name, device_type, user_id, status, last_seen) 
       VALUES ($1, $2, $3, $4, 'online', NOW()) 
       ON CONFLICT (id) 
       DO UPDATE SET name = $2, device_type = $3, last_seen = NOW(), status = 'online'
       RETURNING *`,
      [deviceId, deviceName, deviceType, decoded.userId]
    );
    
    res.json(result.rows[0]);
  } catch (error) {
    console.error('Errore registrazione dispositivo:', error);
    res.status(500).json({ error: 'Errore server' });
  }
});

// ==================== AVVIA SERVER ====================
app.listen(PORT, '0.0.0.0', () => {
  console.log(`🚀 Server running on port ${PORT}`);
  console.log(`📍 Health check: http://0.0.0.0:${PORT}/health`);
  console.log(`🔗 CORS allowed origins:`);
  console.log(`   - https://familycontrol-frontend-production.up.railway.app`);
  console.log(`   - http://localhost:3000`);
});
