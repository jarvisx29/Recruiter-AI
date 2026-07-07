import { useEffect, useRef, useState } from 'react'
import { useSearchParams, useNavigate } from 'react-router-dom'
import { useInterview } from '../hooks/useInterview'
import { useDeepgramInterview } from '../hooks/useDeepgramInterview'
import { loadFaceModels, getDescriptor, captureFromVideo, compareDescriptors } from '../hooks/useWebcamSecurity'
import { BACKEND } from '../config'

const styles = `
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  .iv-body {
    min-height: 100vh;
    background: #050d1a;
    font-family: 'Inter', system-ui, sans-serif;
    color: #f0f6ff;
    display: flex; flex-direction: column;
    position: relative; overflow-x: hidden;
  }

  .iv-grid {
    position: fixed; inset: 0; z-index: 0; pointer-events: none;
    background-image:
      linear-gradient(rgba(37,99,235,0.04) 1px, transparent 1px),
      linear-gradient(90deg, rgba(37,99,235,0.04) 1px, transparent 1px);
    background-size: 48px 48px;
  }
  .iv-glow {
    position: fixed; top: -30%; left: 50%; transform: translateX(-50%);
    width: 800px; height: 600px;
    background: radial-gradient(ellipse, rgba(37,99,235,0.12) 0%, transparent 70%);
    pointer-events: none; z-index: 0;
  }

  .iv-nav {
    position: relative; z-index: 10;
    display: flex; align-items: center; justify-content: space-between;
    padding: 0 2rem; height: 64px;
    border-bottom: 1px solid rgba(255,255,255,0.07);
    background: rgba(5,13,26,0.92);
    backdrop-filter: blur(12px);
  }
  .iv-nav-logo { display: flex; align-items: center; gap: 14px; text-decoration: none; }
  .iv-nav-logo-wrap { background: #fff; border-radius: 8px; padding: 5px 10px; display: flex; align-items: center; }
  .iv-nav-srm-logo { height: 34px; object-fit: contain; }
  .iv-nav-divider { width: 1px; height: 30px; background: rgba(255,255,255,0.15); }
  .iv-nav-title-block {}
  .iv-nav-dept { font-size: 0.6rem; font-weight: 700; color: rgba(255,255,255,0.45); text-transform: uppercase; letter-spacing: 0.7px; }
  .iv-nav-name { font-size: 0.82rem; font-weight: 800; color: #fff; text-transform: uppercase; letter-spacing: 0.5px; margin-top: 1px; }
  .iv-nav-info { display: flex; align-items: center; gap: 1rem; }
  .iv-nav-candidate {
    font-size: 0.82rem; color: rgba(255,255,255,0.6);
    background: rgba(255,255,255,0.05);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 8px; padding: 5px 12px;
  }
  .iv-nav-candidate strong { color: #f0f6ff; }
  .iv-end-btn {
    padding: 6px 16px;
    background: rgba(239,68,68,0.1);
    border: 1px solid rgba(239,68,68,0.3);
    border-radius: 8px;
    color: #ef4444; font-size: 0.8rem; font-weight: 600;
    cursor: pointer; transition: all 0.2s;
    font-family: 'Inter', system-ui, sans-serif;
  }
  .iv-end-btn:hover { background: rgba(239,68,68,0.2); }

  .iv-main {
    position: relative; z-index: 1;
    flex: 1;
    display: flex; flex-direction: column; align-items: center;
    padding: 2rem 1.5rem 3rem;
    gap: 2rem;
  }

  /* ORB */
  .iv-orb-wrap { display: flex; flex-direction: column; align-items: center; gap: 1rem; }
  .iv-orb {
    width: 120px; height: 120px; border-radius: 50%;
    border: 2px solid rgba(37,99,235,0.4);
    background: radial-gradient(circle at 35% 35%, #1e40af, #0f1e35);
    display: flex; align-items: center; justify-content: center;
    font-size: 2.6rem;
    box-shadow: 0 0 30px rgba(37,99,235,0.35), 0 0 60px rgba(37,99,235,0.15);
    animation: iv-orb-idle 3s ease-in-out infinite;
    transition: all 0.4s;
  }
  .iv-orb.agent { animation: iv-orb-agent 1.5s ease-in-out infinite; }
  .iv-orb.user {
    border-color: rgba(16,185,129,0.5);
    box-shadow: 0 0 30px rgba(16,185,129,0.35), 0 0 60px rgba(16,185,129,0.15);
    animation: iv-orb-user 1.2s ease-in-out infinite;
  }
  .iv-orb.done { border-color: rgba(16,185,129,0.5); animation: none; }
  .iv-orb.error { border-color: rgba(239,68,68,0.5); box-shadow: 0 0 30px rgba(239,68,68,0.3); animation: none; }

  @keyframes iv-orb-idle {
    0%,100% { box-shadow: 0 0 30px rgba(37,99,235,0.35),0 0 60px rgba(37,99,235,0.15); }
    50%      { box-shadow: 0 0 45px rgba(37,99,235,0.5), 0 0 90px rgba(37,99,235,0.2); }
  }
  @keyframes iv-orb-agent {
    0%,100% { box-shadow: 0 0 40px rgba(37,99,235,0.6),  0 0 80px rgba(37,99,235,0.25);  transform: scale(1); }
    50%      { box-shadow: 0 0 65px rgba(37,99,235,0.8),  0 0 120px rgba(37,99,235,0.35); transform: scale(1.04); }
  }
  @keyframes iv-orb-user {
    0%,100% { box-shadow: 0 0 40px rgba(16,185,129,0.5), 0 0 80px rgba(16,185,129,0.2);  transform: scale(1); }
    50%      { box-shadow: 0 0 60px rgba(16,185,129,0.7), 0 0 110px rgba(16,185,129,0.3); transform: scale(1.05); }
  }

  .iv-orb-label {
    font-size: 0.85rem; font-weight: 600;
    padding: 5px 14px; border-radius: 20px;
    border: 1px solid rgba(255,255,255,0.1);
    background: rgba(255,255,255,0.05);
    color: rgba(255,255,255,0.8);
  }
  .iv-orb-label.agent { border-color: rgba(37,99,235,0.4); background: rgba(37,99,235,0.1); color: #93c5fd; }
  .iv-orb-label.user  { border-color: rgba(16,185,129,0.4); background: rgba(16,185,129,0.1); color: #6ee7b7; }
  .iv-orb-label.done  { border-color: rgba(16,185,129,0.4); background: rgba(16,185,129,0.1); color: #6ee7b7; }
  .iv-orb-label.error { border-color: rgba(239,68,68,0.4);  background: rgba(239,68,68,0.1);  color: #fca5a5; }

  /* TRANSCRIPT */
  .iv-transcript-wrap {
    width: 100%; max-width: 720px;
    background: rgba(11,22,40,0.8);
    border: 1px solid rgba(255,255,255,0.07);
    border-radius: 16px; overflow: hidden;
    backdrop-filter: blur(8px);
  }
  .iv-transcript-header {
    display: flex; align-items: center; justify-content: space-between;
    padding: 12px 18px;
    border-bottom: 1px solid rgba(255,255,255,0.06);
    background: rgba(255,255,255,0.02);
  }
  .iv-transcript-title { font-size: 0.72rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.8px; color: rgba(255,255,255,0.35); }
  .iv-live-badge { display: flex; align-items: center; gap: 5px; font-size: 0.7rem; color: #10b981; font-weight: 600; }
  .iv-live-dot { width: 6px; height: 6px; border-radius: 50%; background: #10b981; animation: iv-dot-blink 1.5s ease-in-out infinite; }
  @keyframes iv-dot-blink { 0%,100%{opacity:1} 50%{opacity:0.3} }

  .iv-transcript-body {
    padding: 1.25rem;
    max-height: 320px; overflow-y: auto;
    display: flex; flex-direction: column; gap: 1rem;
    scrollbar-width: thin; scrollbar-color: rgba(255,255,255,0.1) transparent;
  }
  .iv-empty { text-align: center; color: rgba(255,255,255,0.2); padding: 2.5rem 0; font-size: 0.9rem; }

  .iv-msg { display: flex; flex-direction: column; animation: iv-fadein 0.3s ease; }
  .iv-msg.agent { align-items: flex-start; }
  .iv-msg.user, .iv-msg.candidate { align-items: flex-end; }
  @keyframes iv-fadein { from{opacity:0;transform:translateY(6px)} to{opacity:1;transform:none} }

  .iv-msg-role { font-size: 0.68rem; font-weight: 700; margin-bottom: 4px; text-transform: uppercase; letter-spacing: 0.5px; color: rgba(255,255,255,0.3); }
  .iv-msg-bubble { max-width: 82%; padding: 10px 14px; font-size: 0.9rem; line-height: 1.55; }
  .iv-msg.agent .iv-msg-bubble { background: rgba(37,99,235,0.12); border: 1px solid rgba(37,99,235,0.2); border-radius: 4px 12px 12px 12px; color: #e2e8f0; }
  .iv-msg.user .iv-msg-bubble, .iv-msg.candidate .iv-msg-bubble { background: rgba(255,255,255,0.06); border: 1px solid rgba(255,255,255,0.1); border-radius: 12px 4px 12px 12px; color: #cbd5e1; }

  .iv-interim {
    align-self: flex-end;
    max-width: 82%; padding: 8px 14px;
    background: rgba(255,255,255,0.03);
    border: 1px dashed rgba(255,255,255,0.15);
    border-radius: 12px 4px 12px 12px;
    font-size: 0.88rem; color: rgba(255,255,255,0.4);
    font-style: italic;
    animation: iv-fadein 0.2s ease;
  }

  .iv-connecting {
    display: flex; flex-direction: column; align-items: center; gap: 1.2rem;
    padding: 3rem 2rem;
  }
  .iv-connecting-ring {
    width: 60px; height: 60px;
    border: 3px solid rgba(37,99,235,0.2);
    border-top-color: #2563eb;
    border-radius: 50%;
    animation: iv-spin 1s linear infinite;
  }
  @keyframes iv-spin { to{transform:rotate(360deg)} }
  .iv-connecting-text { font-size: 0.95rem; color: rgba(255,255,255,0.6); font-weight: 500; }

  .iv-tips { display: flex; gap: 1rem; flex-wrap: wrap; justify-content: center; max-width: 600px; }
  .iv-tip {
    display: flex; align-items: center; gap: 6px;
    font-size: 0.78rem; color: rgba(255,255,255,0.35);
    background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.06);
    border-radius: 8px; padding: 6px 12px;
  }

  /* ── FACE CHECK ── */
  .iv-webcam-preview {
    position: fixed; bottom: 1.5rem; right: 1.5rem; z-index: 20;
    width: 90px; height: 118px; object-fit: cover;
    border-radius: 12px;
    border: 2px solid rgba(37,99,235,0.4);
    box-shadow: 0 4px 16px rgba(0,0,0,0.6);
    transform: scaleX(-1);
    background: #050d1a;
  }
  .iv-face-badge {
    position: fixed; bottom: 1.5rem; right: 1.5rem; z-index: 21;
    width: 90px;
    font-size: 0.6rem; font-weight: 700; text-align: center;
    padding: 3px 0; border-radius: 0 0 10px 10px;
    color: #fff; background: rgba(37,99,235,0.8);
    letter-spacing: 0.5px; text-transform: uppercase;
  }
  .iv-security-toast {
    position: fixed; top: 80px; left: 50%; transform: translateX(-50%);
    z-index: 30; background: rgba(230,81,0,0.95); color: #fff;
    padding: 12px 22px; border-radius: 10px;
    font-size: 0.85rem; font-weight: 600;
    box-shadow: 0 4px 20px rgba(0,0,0,0.4);
    animation: iv-fadein 0.3s ease;
    text-align: center;
  }
  .iv-flagged-overlay {
    position: fixed; inset: 0; z-index: 50;
    background: rgba(5,13,26,0.97);
    display: flex; flex-direction: column; align-items: center; justify-content: center;
    gap: 1.5rem;
  }
  .iv-flagged-icon { font-size: 3.5rem; }
  .iv-flagged-title { font-size: 1.4rem; font-weight: 800; color: #ef4444; }
  .iv-flagged-sub { font-size: 0.9rem; color: rgba(255,255,255,0.5); text-align: center; max-width: 360px; line-height: 1.6; }
`

const ORB_EMOJI = {
  idle: '⏳', connecting: '🔄', agent_talking: '🔊', user_talking: '🎙️',
  processing: '⚙️', done: '✅', error: '❌',
}
const LABELS = {
  idle: 'Initialising', connecting: 'Connecting...', agent_talking: 'AI Interviewer speaking',
  user_talking: 'Your turn — speak now', processing: 'Processing...',
  done: 'Interview complete', error: 'Connection error',
}

// ── Wrapper components to avoid conditional hook calls ────────────────────────

function RetellInterview({ sessionId, name, position }) {
  const hook = useInterview(sessionId)
  return <InterviewUI sessionId={sessionId} name={name} position={position} {...hook} />
}

function DeepgramInterview({ sessionId, name, position }) {
  const hook = useDeepgramInterview(sessionId)
  return <InterviewUI sessionId={sessionId} name={name} position={position} {...hook} />
}

// ── Shared UI ─────────────────────────────────────────────────────────────────

function InterviewUI({ sessionId, name, position, connect, endCall, status, transcript, interimText, results, error }) {
  const navigate = useNavigate()
  const transcriptRef = useRef(null)
  const faceVideoRef = useRef(null)
  const faceStreamRef = useRef(null)
  const refDescRef = useRef(null)
  const warningCountRef = useRef(0)
  const checkIntervalRef = useRef(null)
  const [faceWarning, setFaceWarning] = useState(null) // toast text or null
  const [flagged, setFlagged] = useState(false)
  const [cameraActive, setCameraActive] = useState(false)

  useEffect(() => {
    if (!sessionId) { navigate('/'); return }
    connect()
  }, [sessionId])

  useEffect(() => {
    if (transcriptRef.current) transcriptRef.current.scrollTop = transcriptRef.current.scrollHeight
  }, [transcript, interimText])

  useEffect(() => {
    if (status === 'done') {
      setTimeout(() => navigate(`/results?session=${sessionId}`), 2000)
    }
  }, [status])

  // Periodic face security check
  useEffect(() => {
    const refPhotoUrl = sessionStorage.getItem('referencePhoto')
    if (!refPhotoUrl) return // no reference photo — skip checking

    let cancelled = false

    const init = async () => {
      try {
        await loadFaceModels()
        // Build reference descriptor from stored photo
        const img = new Image()
        img.src = refPhotoUrl
        await img.decode()
        const desc = await getDescriptor(img)
        if (!desc || cancelled) return
        refDescRef.current = desc

        // Open webcam (video only, separate from audio)
        const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'user' } })
        if (cancelled) { stream.getTracks().forEach(t => t.stop()); return }
        faceStreamRef.current = stream
        if (faceVideoRef.current) faceVideoRef.current.srcObject = stream
        setCameraActive(true)

        // Start 30-second checks
        checkIntervalRef.current = setInterval(async () => {
          if (cancelled || !faceVideoRef.current || !refDescRef.current) return
          try {
            const camDesc = await captureFromVideo(faceVideoRef.current)
            if (!camDesc) {
              setFaceWarning('No face detected — please remain visible')
              setTimeout(() => setFaceWarning(null), 6000)
              return
            }
            const { matched } = compareDescriptors(refDescRef.current, camDesc)
            if (!matched) {
              warningCountRef.current += 1
              if (warningCountRef.current >= 2) {
                // Flag the session and terminate
                clearInterval(checkIntervalRef.current)
                await fetch(`${BACKEND}/api/flag/${sessionId}`, { method: 'POST' }).catch(() => {})
                setFlagged(true)
                setTimeout(() => navigate(`/results?session=${sessionId}`), 5000)
              } else {
                setFaceWarning('Warning: Face does not match reference. Please face the camera.')
                setTimeout(() => setFaceWarning(null), 8000)
              }
            }
          } catch { /* silent — don't disrupt interview */ }
        }, 30000)
      } catch { /* camera denied or models failed — skip silently */ }
    }

    init()
    return () => {
      cancelled = true
      clearInterval(checkIntervalRef.current)
      faceStreamRef.current?.getTracks().forEach(t => t.stop())
      faceStreamRef.current = null
    }
  }, [sessionId])

  if (!sessionId) return null

  const orbClass = status === 'agent_talking' ? 'agent'
    : status === 'user_talking' ? 'user'
    : status === 'done' ? 'done'
    : status === 'error' ? 'error' : ''

  const isConnecting = status === 'idle' || status === 'connecting'
  const isActive = !['done', 'error', 'connecting', 'idle'].includes(status)

  return (
    <>
      <style>{styles}</style>
      <div className="iv-body">
        <div className="iv-grid" />
        <div className="iv-glow" />

        {/* Flagged overlay */}
        {flagged && (
          <div className="iv-flagged-overlay">
            <div className="iv-flagged-icon">🚨</div>
            <div className="iv-flagged-title">Session Flagged</div>
            <div className="iv-flagged-sub">Possible proxy attempt detected. This session has been flagged for review. Redirecting to results...</div>
          </div>
        )}

        {/* Face mismatch warning toast */}
        {faceWarning && <div className="iv-security-toast">{faceWarning}</div>}

        {/* Webcam for periodic face checks (visible corner preview) */}
        <video ref={faceVideoRef} autoPlay muted playsInline
          className={cameraActive ? 'iv-webcam-preview' : ''}
          style={cameraActive ? {} : { display: 'none' }} />
        {cameraActive && <div className="iv-face-badge" style={{ bottom: '0.8rem' }}>Security</div>}

        <nav className="iv-nav">
          <a className="iv-nav-logo" href="/">
            <div className="iv-nav-logo-wrap">
              <img src="/srm-logo.png" alt="SRM" className="iv-nav-srm-logo" />
            </div>
            <div className="iv-nav-divider" />
            <div className="iv-nav-title-block">
              <div className="iv-nav-dept">Dept. of CS&amp;E</div>
              <div className="iv-nav-name">SRM Placements</div>
            </div>
          </a>
          <div className="iv-nav-info">
            <div className="iv-nav-candidate"><strong>{name}</strong> · {position}</div>
            {isActive && <button className="iv-end-btn" onClick={endCall}>End Interview</button>}
          </div>
        </nav>

        <div className="iv-main">
          <div className="iv-orb-wrap">
            <div className={`iv-orb ${orbClass}`}>{ORB_EMOJI[status] || '⏳'}</div>
            <div className={`iv-orb-label ${orbClass}`}>{LABELS[status]}</div>
          </div>

          <div className="iv-transcript-wrap">
            <div className="iv-transcript-header">
              <span className="iv-transcript-title">Live Transcript</span>
              {transcript.length > 0 && (
                <span className="iv-live-badge"><span className="iv-live-dot" /> Live</span>
              )}
            </div>
            <div className="iv-transcript-body" ref={transcriptRef}>
              {isConnecting && (
                <div className="iv-connecting">
                  <div className="iv-connecting-ring" />
                  <div className="iv-connecting-text">Connecting to your AI interviewer...</div>
                </div>
              )}
              {!isConnecting && transcript.length === 0 && (
                <div className="iv-empty">Interview starting — the AI will speak first</div>
              )}
              {transcript.map((msg, i) => (
                <div key={i} className={`iv-msg ${msg.role}`}>
                  <div className="iv-msg-role">{msg.role === 'agent' ? '🤖 Interviewer' : '👤 You'}</div>
                  <div className="iv-msg-bubble">{msg.text}</div>
                </div>
              ))}
              {interimText && <div className="iv-interim">{interimText}...</div>}
              {status === 'done' && (
                <div style={{ textAlign: 'center', color: '#6ee7b7', fontWeight: 600, padding: '0.75rem 0' }}>
                  ✅ Interview complete — loading your results...
                </div>
              )}
              {status === 'error' && (
                <div style={{ textAlign: 'center', color: '#fca5a5', padding: '0.75rem 0', fontSize: '0.88rem' }}>
                  {error || 'Connection failed. Please refresh and try again.'}
                </div>
              )}
            </div>
          </div>

          <div className="iv-tips">
            <div className="iv-tip">🎯 Be specific — vague answers get probed</div>
            <div className="iv-tip">⏸️ Wait for AI to finish before speaking</div>
            <div className="iv-tip">🧠 It adapts to your level in real-time</div>
          </div>
        </div>
      </div>
    </>
  )
}

// ── Entry point ───────────────────────────────────────────────────────────────

export default function Interview() {
  const [params] = useSearchParams()
  const mode = params.get('mode') || 'deepgram'
  const sessionId = params.get('session')
  const name = params.get('name') || 'Candidate'
  const position = params.get('position') || ''

  if (mode === 'retell') {
    return <RetellInterview sessionId={sessionId} name={name} position={position} />
  }
  return <DeepgramInterview sessionId={sessionId} name={name} position={position} />
}
