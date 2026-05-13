require('dotenv').config();

const express = require('express');
const cors = require('cors');
const bcrypt = require('bcrypt');
const jwt = require('jsonwebtoken');
const helmet = require('helmet');
const morgan = require('morgan');
const compression = require('compression');
const rateLimit = require('express-rate-limit');
const { Pool } = require('pg');

const app = express();

// ==================== VALIDAZIONE VARIABILI ====================
if (!process.env.DATABASE_URL) {
  console.error('❌ DATABASE_URL mancante');
  process.exit(1);
}

if (!process.env.JWT_SECRET) {
  console.error('❌ JWT_SECRET mancante');
  process.exit(1);
}

// ==================== DATABASE ====================
const pool = new Pool({
  connectionString: process.env.DATABASE_URL,
  ssl: { rejectUnauthorized: false }
});

pool.connect((err, client, release) => {
  if (err) {
    console.error('❌ Errore connessione database:', err.stack);
  } else {
    console.log('✅ Database connesso');
    release();
  }
});

// ==================== MIDDLEWARE ====================
app.use(helmet());
app.use(compression());
app.use(morgan('combined'));

app.use(cors({
  origin: [
    'https://familycontrol-frontend-production.up.railway.app',
    'http://localhost:3000'
  ],
  methods: ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
  allowedHeaders: ['Content-Type', 'Authorization']
}));

app.use(express.json({ limit: '10mb' }));

// Rate limit generale
app.use(rateLimit({
  windowMs: 15 * 60 * 1000,
  max: 300,
  message: { error: 'Troppe richieste, riprova più tardi' }
}));

// Rate limit login
const loginLimiter = rateLimit({
  windowMs: 15 * 60 * 1000,
  max: 10,
  message: { error: 'Troppi tentativi di login, riprova più tardi' }
});

// ==================== MIDDLEWARE JWT ====================
function verifyToken(req, res, next) {
  const authHeader = req.headers.authorization;
  if (!authHeader || !authHeader.startsWith('Bearer ')) {
    return res.status(401).json({ error: 'Token mancante o non valido' });
  }
  const token = authHeader.split(' ')[1];
  try {
    const decoded = jwt.verify(token, process.env.JWT_SECRET);
    req.user = decoded;
    next();
  } catch (error) {
    return res.status(401).json({ error: 'Token scaduto o non valido' });
  }
}

// ==================== ROUTES ====================

// Health check
app.get('/health', async (req, res) => {
  try {
    await pool.query('SELECT 1');
    res.json({ status: 'ok', database: 'connected' });
  } catch (error) {
    res.status(500).json({ status: 'error', database: 'disconnected' });
  }
});

// Login
app.post('/api/auth/login', loginLimiter, async (req, res) => {
  try {
    const { username, password } = req.body;
    if (!username || !password) {
      return res.status(400).json({ error: 'Username e password obbligatori' });
    }

    const result = await pool.query(
      'SELECT id, username, password_hash, email FROM users WHERE username = $1',
      [username]
    );

    if (result.rows.length === 0) {
      return res.status(401).json({ error: 'Credenziali non valide' });
    }

    const user = result.rows[0];
    const validPassword = await bcrypt.compare(password, user.password_hash);
    if (!validPassword) {
      return res.status(401).json({ error: 'Credenziali non valide' });
    }

    const token = jwt.sign(
      { id: user.id, username: user.username, email: user.email },
      process.env.JWT_SECRET,
      { expiresIn: '24h' }
    );

    res.json({ token, user: { id: user.id, username: user.username, email: user.email } });
  } catch (error) {
    console.error('LOGIN ERROR:', error);
    res.status(500).json({ error: 'Errore server' });
  }
});

// Profilo utente
app.get('/api/auth/me', verifyToken, async (req, res) => {
  res.json({ user: { id: req.user.id, username: req.user.username, email: req.user.email } });
});

// ==================== API DISPOSITIVI ====================

// Lista dispositivi
app.get('/api/devices', verifyToken, async (req, res) => {
  try {
    const result = await pool.query(
      `SELECT id, name, device_type, status, last_seen, user_id
       FROM devices WHERE user_id = $1 ORDER BY last_seen DESC NULLS LAST`,
      [req.user.id]
    );
    res.json(result.rows);
  } catch (error) {
    console.error('DEVICES ERROR:', error);
    res.status(500).json({ error: 'Errore recupero dispositivi' });
  }
});

// Ricevi dati da un dispositivo
app.post('/api/devices/:deviceId/data', verifyToken, async (req, res) => {
  const { deviceId } = req.params;
  const { dataType, dataContent } = req.body;
  
  try {
    const deviceCheck = await pool.query('SELECT user_id FROM devices WHERE id = $1', [deviceId]);
    
    if (deviceCheck.rows.length === 0) {
      await pool.query(
        `INSERT INTO devices (id, name, device_type, user_id, status, last_seen)
         VALUES ($1, $2, 'android', $3, 'online', NOW())`,
        [deviceId, deviceId, req.user.id]
      );
    } else if (deviceCheck.rows[0].user_id !== req.user.id) {
      return res.status(403).json({ error: 'Dispositivo non autorizzato' });
    }
    
    await pool.query(
      `INSERT INTO device_data (device_id, data_type, data_content, created_at)
       VALUES ($1, $2, $3, NOW())`,
      [deviceId, dataType, JSON.stringify(dataContent)]
    );
    
    await pool.query(`UPDATE devices SET last_seen = NOW(), status = 'online' WHERE id = $1`, [deviceId]);
    
    res.json({ status: 'ok' });
  } catch (error) {
    console.error('DATA ERROR:', error);
    res.status(500).json({ error: 'Errore salvataggio dati' });
  }
});

// Ottieni dati di un dispositivo
app.get('/api/devices/:deviceId/data', verifyToken, async (req, res) => {
  const { deviceId } = req.params;
  const { limit = 50 } = req.query;
  
  try {
    const result = await pool.query(
      `SELECT data_type, data_content, created_at
       FROM device_data WHERE device_id = $1
       ORDER BY created_at DESC LIMIT $2`,
      [deviceId, limit]
    );
    res.json(result.rows);
  } catch (error) {
    console.error('FETCH DATA ERROR:', error);
    res.status(500).json({ error: 'Errore recupero dati' });
  }
});

// Registrazione dispositivo
app.post('/api/devices/register', verifyToken, async (req, res) => {
  const { deviceId, deviceName, deviceType } = req.body;
  
  try {
    const result = await pool.query(
      `INSERT INTO devices (id, name, device_type, user_id, status, last_seen)
       VALUES ($1, $2, $3, $4, 'online', NOW())
       ON CONFLICT (id) DO UPDATE
       SET name = $2, device_type = $3, last_seen = NOW(), status = 'online'
       RETURNING *`,
      [deviceId, deviceName || deviceId, deviceType || 'android', req.user.id]
    );
    res.json(result.rows[0]);
  } catch (error) {
    console.error('REGISTER ERROR:', error);
    res.status(500).json({ error: 'Errore registrazione dispositivo' });
  }
});

// Ottieni comandi pendenti
app.get('/api/devices/:deviceId/commands', verifyToken, async (req, res) => {
  const { deviceId } = req.params;
  
  try {
    const result = await pool.query(
      `SELECT id, command, params, status, created_at
       FROM commands WHERE device_id = $1 AND status = 'pending'
       ORDER BY created_at ASC`,
      [deviceId]
    );
    res.json(result.rows);
  } catch (error) {
    console.error('COMMANDS ERROR:', error);
    res.status(500).json({ error: 'Errore recupero comandi' });
  }
});

// Marca comando come completato
app.patch('/api/commands/:commandId', verifyToken, async (req, res) => {
  const { commandId } = req.params;
  const { status, result } = req.body;
  
  try {
    await pool.query(
      `UPDATE commands SET status = $1, executed_at = NOW(), result = $2
       WHERE id = $3`,
      [status || 'completed', JSON.stringify(result || {}), commandId]
    );
    res.json({ status: 'ok' });
  } catch (error) {
    console.error('UPDATE COMMAND ERROR:', error);
    res.status(500).json({ error: 'Errore aggiornamento comando' });
  }
});

// Invia comando a dispositivo
app.post('/api/devices/:deviceId/command', verifyToken, async (req, res) => {
  const { deviceId } = req.params;
  const { command, params } = req.body;
  
  try {
    const result = await pool.query(
      `INSERT INTO commands (device_id, command, params, status, created_at)
       VALUES ($1, $2, $3, 'pending', NOW())
       RETURNING *`,
      [deviceId, command, JSON.stringify(params || {})]
    );
    res.json(result.rows[0]);
  } catch (error) {
    console.error('SEND COMMAND ERROR:', error);
    res.status(500).json({ error: 'Errore invio comando' });
  }
});

// Aggiorna stato dispositivo
app.patch('/api/devices/:deviceId/status', verifyToken, async (req, res) => {
  const { deviceId } = req.params;
  const { status } = req.body;
  
  try {
    await pool.query(`UPDATE devices SET status = $1, last_seen = NOW() WHERE id = $2`, [status || 'offline', deviceId]);
    res.json({ status: 'ok' });
  } catch (error) {
    console.error('STATUS ERROR:', error);
    res.status(500).json({ error: 'Errore aggiornamento stato' });
  }
});

// ==================== 404 ====================
app.use('/api', (req, res) => {
  res.status(404).json({ error: 'Endpoint non trovato' });
});

// Error handler
app.use((error, req, res, next) => {
  console.error('GLOBAL ERROR:', error);
  res.status(500).json({ error: 'Errore interno server' });
});

// ==================== AVVIO SERVER ====================
const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`✅ Server running on port ${PORT}`);
});
