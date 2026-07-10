import { Routes, Route, Navigate } from 'react-router-dom'
import Apply from './pages/Apply'
import Interview from './pages/Interview'
import Shortlist from './pages/Shortlist'
import Results from './pages/Results'

export default function App() {
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
