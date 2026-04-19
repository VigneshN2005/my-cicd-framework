// main.jsx
// This is the ENTRY POINT of your React app
// It connects React to the HTML file (index.html)
// CI/CD Note: Vite starts here when building your app

import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'
import './App.css'

// This line mounts your React app into the <div id="root"> in index.html
ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />  {/* Your main App component loads here */}
  </React.StrictMode>
)