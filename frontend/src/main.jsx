import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import { NeonAuthUIProvider } from '@neondatabase/neon-js/auth/react'
import '@neondatabase/neon-js/ui/css'

import './index.css'
import App from './App.jsx'
import { authClient } from './lib/auth.js'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <NeonAuthUIProvider emailOTP authClient={authClient}>
      <App />
    </NeonAuthUIProvider>
  </StrictMode>,
)