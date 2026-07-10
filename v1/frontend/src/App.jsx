import { useEffect } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import Apply from './pages/Apply'
import Interview from './pages/Interview'
import Shortlist from './pages/Shortlist'
import Results from './pages/Results'
import { loadFaceModels } from './hooks/useWebcamSecurity'

export default function App() {
  // Pre-download face models in background as soon as the app loads.
  // By the time the user finishes the form and enters the interview,
  // models are already cached — detection starts instantly.
  useEffect(() => { loadFaceModels().catch(() => {}) }, [])

  return (
    <Routes>
      <Route path="/" element={<Apply />} />
      <Route path="/interview" element={<Interview />} />
      <Route path="/shortlist" element={<Shortlist />} />
      <Route path="/results" element={<Results />} />
      <Route path="*" element={<Navigate to="/" />} />
    </Routes>
  )
}
