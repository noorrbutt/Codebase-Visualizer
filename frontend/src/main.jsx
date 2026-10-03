import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App.jsx'
import { API_CONFIG_ERROR } from './utils/api.js'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    {API_CONFIG_ERROR ? <p role="alert" style={{ padding: 24 }}>{API_CONFIG_ERROR}</p> : <App />}
  </StrictMode>,
)
