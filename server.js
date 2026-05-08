const express = require('express');
const cors = require('cors');
require('dotenv').config();

const app = express();

app.use(cors());
app.use(express.json());
app.use(express.static('public'));

const SUPABASE_URL = process.env.SUPABASE_URL || 'https://rclarbbasnnwmwhpoenn.supabase.co';
const SUPABASE_ANON_KEY = process.env.SUPABASE_ANON_KEY || 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InJjbGFyYmJhc25ud213aHBvZW5uIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzgyMzc4OTYsImV4cCI6MjA5MzgxMzg5Nn0.yI9jvnzw_gojcR7jNVK5qBwJs9uwpBMv36vvmHwoZMQ';

// Endpoint per il login
app.post('/api/auth/login', async (req, res) => {
    const { email, password } = req.body;

    try {
        const response = await fetch(`${SUPABASE_URL}/auth/v1/token?grant_type=password`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'apikey': SUPABASE_ANON_KEY
            },
            body: JSON.stringify({ email, password })
        });

        const data = await response.json();

        if (!response.ok || data.error) {
            return res.status(401).json({ error: 'Credenziali non valide' });
        }

        res.json({
            user: {
                email: data.user?.email,
                id: data.user?.id
            },
            token: data.access_token
        });
    } catch (error) {
        res.status(500).json({ error: 'Errore server' });
    }
});

// Endpoint per i dispositivi
app.get('/api/devices', async (req, res) => {
    const token = req.headers.authorization?.split(' ')[1];

    try {
        const response = await fetch(`${SUPABASE_URL}/rest/v1/devices?order=last_seen.desc`, {
            headers: {
                'apikey': SUPABASE_ANON_KEY,
                'Authorization': `Bearer ${token}`
            }
        });

        const data = await response.json();
        res.json(data);
    } catch (error) {
        res.status(500).json({ error: 'Errore' });
    }
});

// Endpoint per i dati del dispositivo
app.get('/api/device-data/:deviceId', async (req, res) => {
    const { deviceId } = req.params;
    const token = req.headers.authorization?.split(' ')[1];

    try {
        const response = await fetch(
            `${SUPABASE_URL}/rest/v1/device_data?device_id=eq.${deviceId}&order=created_at.desc&limit=1`,
            {
                headers: {
                    'apikey': SUPABASE_ANON_KEY,
                    'Authorization': `Bearer ${token}`
                }
            }
        );

        const data = await response.json();
        res.json(data);
    } catch (error) {
        res.status(500).json({ error: 'Errore' });
    }
});

// Endpoint per i comandi
app.post('/api/commands', async (req, res) => {
    const { device_id, command } = req.body;
    const token = req.headers.authorization?.split(' ')[1];

    try {
        const response = await fetch(`${SUPABASE_URL}/rest/v1/commands`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'apikey': SUPABASE_ANON_KEY,
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({
                device_id,
                command,
                params: {},
                status: 'pending'
            })
        });

        const data = await response.json();
        res.json(data);
    } catch (error) {
        res.status(500).json({ error: 'Errore' });
    }
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
    console.log(`Server running on port ${PORT}`);
});
