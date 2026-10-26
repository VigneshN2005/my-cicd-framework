// App.jsx
// This is the MAIN COMPONENT of your React app
// This is what users see in the browser
// It also calls the backend API to show the connection

import { useState, useEffect } from 'react'
import './App.css'

function App() {

  // State to store message from backend
  const [backendMessage, setBackendMessage] = useState('Loading...')
  const [status, setStatus] = useState('checking...')

  // useEffect runs when component loads
  // It calls the FastAPI backend to get a message
  useEffect(() => {
    // Calling our FastAPI backend
    fetch('/api/hello')
      .then(response => response.json())
      .then(data => {
        setBackendMessage(data.message)  // show backend message
        setStatus('Connected ✅')
      })
      .catch(() => {
        setBackendMessage('Could not reach backend')
        setStatus('Not Connected ❌')
      })
  }, [])

  return (
    <div className="app">

      {/* Header */}
      <header className="header">
        <h1>🚀 My CI/CD Framework</h1>
        <p>Built with React + FastAPI + Docker + GitHub Actions</p>
      </header>

      {/* Pipeline Status Card */}
      <div className="card">
        <h2>Pipeline Stages</h2>
        <div className="stages">
          <div className="stage">✅ Config validated (pipeline-config.yml)</div>
          <div className="stage">✅ Lint passed (ruff, ESLint)</div>
          <div className="stage">✅ Tests passed with coverage gates</div>
          <div className="stage">✅ Security scans passed (pip-audit, npm audit, Gitleaks, Trivy)</div>
          <div className="stage">✅ Docker image built and smoke-tested</div>
          <div className="stage">✅ Image published to GitHub Container Registry</div>
          <div className="stage">✅ Deployed and health-checked (auto rollback on failure)</div>
        </div>
      </div>

      {/* Backend Connection Card */}
      <div className="card">
        <h2>Backend Connection</h2>
        <p>Status: <strong>{status}</strong></p>
        <p>Message from FastAPI: <strong>{backendMessage}</strong></p>
      </div>

      {/* Info Card */}
      <div className="card">
        <h2>What is Running</h2>
        <p>🌐 Frontend → React (Port 3001)</p>
        <p>⚙️ Backend → FastAPI (Port 8000)</p>
        <p>🐳 Container → Docker</p>
        <p>🔄 Pipeline → GitHub Actions</p>
      </div>

    </div>
  )
}

export default App