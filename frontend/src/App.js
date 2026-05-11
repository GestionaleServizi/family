import React, { useState } from 'react';
import axios from 'axios';

function App() {
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [devices, setDevices] = useState([]);

  const handleLogin = async (username, password) => {
    try {
      const response = await axios.post('/api/auth/login', { username, password });
      localStorage.setItem('token', response.data.token);
      setIsLoggedIn(true);
    } catch (error) {
      alert('Login fallito');
    }
  };

  if (!isLoggedIn) {
    return (
      <div style={{ padding: '50px', textAlign: 'center' }}>
        <h1>FamilyControl</h1>
        <form onSubmit={(e) => {
          e.preventDefault();
          handleLogin(e.target.username.value, e.target.password.value);
        }}>
          <input name="username" placeholder="Username" /><br /><br />
          <input name="password" type="password" placeholder="Password" /><br /><br />
          <button type="submit">Login</button>
        </form>
      </div>
    );
  }

  return (
    <div style={{ padding: '50px' }}>
      <h1>Dashboard FamilyControl</h1>
      <p>Benvenuto! Qui vedrai i tuoi dispositivi.</p>
    </div>
  );
}

export default App;
