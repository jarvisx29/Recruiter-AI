import { useEffect } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import Apply from './pages/Apply'
import Interview from './pages/Interview'
import Shortlist from './pages/Shortlist'
import Results from './pages/Results'
import { loadFaceModels } from './hooks/useWebcamSecurity'

export default function App() {
  // Preload face models the moment the app opens — ~7MB download happens in background
  // while user fills the form, so by interview time models are already cached.
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
