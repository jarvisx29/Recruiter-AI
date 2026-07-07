// Update BACKEND after Railway deploy
export const BACKEND = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000'
export const BACKEND_WS = BACKEND.replace(/^http/, 'ws')
