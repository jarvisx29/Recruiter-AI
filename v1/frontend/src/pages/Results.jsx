import { useState, useEffect } from 'react'
import { useSearchParams, useNavigate } from 'react-router-dom'
import { BACKEND } from '../config'

const styles = `
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  .rs-body {
    min-height: 100vh;
    background: #f0f4f8;
    font-family: 'Inter', system-ui, sans-serif;
    color: #1a2332;
    display: flex; flex-direction: column;
  }

  /* ── SRM HEADER ── */
  .rs-srm-header {
    background: #fff;
    border-bottom: 1px solid #e0e7ef;
    padding: 0 2rem;
    display: flex; align-items: center; justify-content: space-between;
  }
  .rs-srm-header-left {
    display: flex; align-items: center; gap: 20px;
    padding: 14px 0;
  }
  .rs-srm-logo-wrap {
    background: #fff; border-radius: 8px;
    display: flex; align-items: center;
  }
  .rs-srm-logo { height: 60px; object-fit: contain; }
  .rs-srm-divider { width: 1px; height: 48px; background: #d8e2ef; }
  .rs-srm-dept {
    font-size: 0.7rem; font-weight: 700; color: #1565c0;
    text-transform: uppercase; letter-spacing: 0.8px; line-height: 1.3;
  }
  .rs-srm-title {
    font-size: 1.05rem; font-weight: 900; color: #1a237e;
    text-transform: uppercase; letter-spacing: 0.5px; line-height: 1.2; margin-top: 2px;
  }
  .rs-srm-badge {
    display: flex; align-items: center; gap: 8px;
    background: rgba(46,125,50,0.08);
    border: 1px solid rgba(46,125,50,0.25);
    border-radius: 20px; padding: 5px 14px;
    font-size: 0.72rem; font-weight: 700;
    color: #2e7d32; text-transform: uppercase; letter-spacing: 0.6px;
  }

  /* ── MAIN ── */
  .rs-main {
    flex: 1;
    max-width: 720px; margin: 0 auto; width: 100%;
    padding: 2.5rem 1.5rem 4rem;
    display: flex; flex-direction: column; gap: 1.25rem;
  }

  /* ── PAGE HEADING ── */
  .rs-page-title {
    font-size: 0.72rem; font-weight: 800; color: #1565c0;
    text-transform: uppercase; letter-spacing: 1px;
    border-bottom: 2px solid #e8edf5;
    padding-bottom: 0.75rem;
  }
  .rs-candidate-name {
    font-size: 1.5rem; font-weight: 900; color: #1a237e;
    margin-top: 0.4rem;
  }
  .rs-position {
    font-size: 0.88rem; color: #6b7a8d; margin-top: 2px;
  }

  /* ── BANNER ── */
  .rs-banner {
    display: flex; align-items: center; justify-content: space-between;
    padding: 1.4rem 1.75rem;
    border-radius: 14px; border: 1px solid;
  }
  .rs-banner-label-sm { font-size: 0.68rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.6px; opacity: 0.65; margin-bottom: 4px; }
  .rs-banner-rec { font-size: 1.5rem; font-weight: 900; }
  .rs-banner-score { font-size: 2.4rem; font-weight: 900; text-align: right; line-height: 1; }
  .rs-banner-score sup { font-size: 0.9rem; font-weight: 600; opacity: 0.5; }

  /* ── CARDS ── */
  .rs-card {
    background: #fff;
    border: 1px solid #d8e2ef;
    border-radius: 14px;
    padding: 1.5rem;
    box-shadow: 0 2px 10px rgba(21,101,192,0.05);
  }
  .rs-section-title {
    font-size: 0.68rem; font-weight: 800;
    text-transform: uppercase; letter-spacing: 1px;
    color: #1565c0; margin-bottom: 1.1rem;
  }

  /* ── BARS ── */
  .rs-bar-row { margin-bottom: 1rem; }
  .rs-bar-row:last-child { margin-bottom: 0; }
  .rs-bar-meta { display: flex; justify-content: space-between; margin-bottom: 6px; font-size: 0.875rem; }
  .rs-bar-name { font-weight: 600; color: #1a2332; }
  .rs-bar-score { font-weight: 800; }
  .rs-bar-track { background: #f0f4f8; border-radius: 6px; height: 8px; overflow: hidden; }
  .rs-bar-fill { height: 100%; border-radius: 6px; transition: width 1s ease; }

  /* ── TRANSCRIPT ── */
  .rs-transcript { display: flex; flex-direction: column; gap: 0.75rem; max-height: 400px; overflow-y: auto; scrollbar-width: thin; scrollbar-color: #d8e2ef transparent; }
  .rs-msg { display: flex; gap: 0.75rem; font-size: 0.875rem; }
  .rs-msg-role { font-weight: 700; min-width: 86px; flex-shrink: 0; font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.4px; padding-top: 2px; }
  .rs-msg-content { color: #374151; line-height: 1.6; }

  /* ── BUTTON ── */
  .rs-btn {
    display: inline-flex; align-items: center; gap: 6px;
    height: 48px; padding: 0 24px;
    background: linear-gradient(135deg, #1565c0, #1a6fd4);
    border: none; border-radius: 10px;
    color: #fff; font-size: 0.88rem; font-weight: 700;
    cursor: pointer; transition: opacity 0.2s;
    font-family: 'Inter', system-ui, sans-serif;
    text-transform: uppercase; letter-spacing: 0.4px;
  }
  .rs-btn:hover { opacity: 0.9; }

  /* ── FLAGGED BANNER ── */
  .rs-flagged-banner {
    background: rgba(183,28,28,0.06); border: 1.5px solid rgba(183,28,28,0.3);
    border-radius: 12px; padding: 1.1rem 1.5rem;
    display: flex; align-items: center; gap: 1rem;
  }
  .rs-flagged-icon-box { font-size: 1.8rem; flex-shrink: 0; }
  .rs-flagged-title { font-size: 0.82rem; font-weight: 800; color: #b71c1c; text-transform: uppercase; letter-spacing: 0.6px; margin-bottom: 3px; }
  .rs-flagged-detail { font-size: 0.8rem; color: #7f1d1d; line-height: 1.5; }

  /* ── LOADING / ERROR ── */
  .rs-center {
    flex: 1; display: flex; flex-direction: column;
    align-items: center; justify-content: center; gap: 1rem;
  }
  .rs-loading-ring {
    width: 48px; height: 48px;
    border: 4px solid rgba(21,101,192,0.15);
    border-top-color: #1565c0;
    border-radius: 50%;
    animation: rs-spin 0.9s linear infinite;
  }
  @keyframes rs-spin { to { transform: rotate(360deg); } }

  @media (max-width: 600px) {
    .rs-srm-header { padding: 0 1rem; }
    .rs-srm-logo { height: 44px; }
    .rs-srm-title { font-size: 0.82rem; }
    .rs-srm-badge { display: none; }
    .rs-banner { flex-direction: column; gap: 1rem; align-items: flex-start; }
  }
`

const REC = {
  Hire:   { color: '#1b5e20', bg: 'rgba(46,125,50,0.07)',   border: 'rgba(46,125,50,0.25)',   label: 'Hire' },
  Hold:   { color: '#e65100', bg: 'rgba(245,124,0,0.07)',   border: 'rgba(245,124,0,0.25)',   label: 'Hold for Review' },
  Reject: { color: '#b71c1c', bg: 'rgba(198,40,40,0.07)',   border: 'rgba(198,40,40,0.25)',   label: 'Reject' },
}

function barColor(score) {
  return score >= 7 ? '#2e7d32' : score >= 5 ? '#e65100' : '#c62828'
}

function SrmHeader() {
  return (
    <header className="rs-srm-header">
      <div className="rs-srm-header-left">
        <div className="rs-srm-logo-wrap">
          <img src="/srm-logo.png" alt="SRM Institute of Science and Technology" className="rs-srm-logo" />
        </div>
        <div className="rs-srm-divider" />
        <div>
          <div className="rs-srm-dept">Department of Computer Science and Engineering</div>
          <div className="rs-srm-title">AI Mock Interview Drive</div>
        </div>
      </div>
      <div className="rs-srm-badge">Interview Complete</div>
    </header>
  )
}

export default function Results() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const sessionId = searchParams.get('session')

  const [results, setResults] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!sessionId) { navigate('/'); return }
    let attempts = 0
    const MAX = 12

    async function tryFetch() {
      try {
        const r = await fetch(`${BACKEND}/api/results/${sessionId}`)
        if (r.ok) { setResults(await r.json()); return }
      } catch {}
      attempts++
      if (attempts < MAX) setTimeout(tryFetch, 1000)
      else setError('Could not load results. Please try again.')
    }

    tryFetch()
  }, [sessionId])

  if (error) return (
    <>
      <style>{styles}</style>
      <div className="rs-body">
        <SrmHeader />
        <div className="rs-center">
          <p style={{ color: '#c62828', fontWeight: 600 }}>{error}</p>
          <button className="rs-btn" onClick={() => navigate('/')}>Go Home</button>
        </div>
      </div>
    </>
  )

  if (!results) return (
    <>
      <style>{styles}</style>
      <div className="rs-body">
        <SrmHeader />
        <div className="rs-center">
          <div className="rs-loading-ring" />
          <div style={{ color: '#1565c0', fontSize: '0.95rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.5px' }}>
            Generating Results...
          </div>
          <div style={{ color: '#6b7a8d', fontSize: '0.82rem' }}>This may take a few seconds</div>
        </div>
      </div>
    </>
  )

  const rec = REC[results.recommendation] || REC.Hold
  const overallPct = Math.round((results.overall_score / 10) * 100)

  return (
    <>
      <style>{styles}</style>
      <div className="rs-body">
        <SrmHeader />

        <div className="rs-main">

          {/* Page heading */}
          <div>
            <div className="rs-page-title">Interview Results</div>
            <div className="rs-candidate-name">{results.candidate}</div>
            <div className="rs-position">{results.position}</div>
          </div>

          {/* Flagged banner — shown above recommendation if session was flagged */}
          {results.is_flagged && (
            <div className="rs-flagged-banner">
              <div className="rs-flagged-icon-box">🚨</div>
              <div>
                <div className="rs-flagged-title">Session Flagged — Possible Proxy Attempt</div>
                <div className="rs-flagged-detail">
                  Face verification failed during the interview. This session has been flagged for manual review and will be disqualified pending investigation.
                </div>
              </div>
            </div>
          )}

          {/* Recommendation banner */}
          <div className="rs-banner" style={{ background: rec.bg, borderColor: rec.border, color: rec.color }}>
            <div>
              <div className="rs-banner-label-sm">Recommendation</div>
              <div className="rs-banner-rec">{rec.label}</div>
            </div>
            <div style={{ textAlign: 'right' }}>
              <div className="rs-banner-label-sm">Overall Score</div>
              <div className="rs-banner-score">{results.overall_score}<sup>/10</sup></div>
            </div>
          </div>

          {/* Overall bar */}
          <div className="rs-card">
            <div className="rs-section-title">Overall Performance</div>
            <div className="rs-bar-track">
              <div className="rs-bar-fill" style={{
                width: `${overallPct}%`,
                background: overallPct >= 65 ? '#2e7d32' : overallPct >= 50 ? '#e65100' : '#c62828'
              }} />
            </div>
            <div style={{ textAlign: 'right', fontSize: '0.78rem', color: '#6b7a8d', marginTop: 6, fontWeight: 600 }}>
              {overallPct}%
            </div>
          </div>

          {/* Topic breakdown */}
          {Object.keys(results.topic_scores || {}).length > 0 && (
            <div className="rs-card">
              <div className="rs-section-title">Topic Breakdown</div>
              {Object.entries(results.topic_scores).map(([topic, score]) => (
                <div key={topic} className="rs-bar-row">
                  <div className="rs-bar-meta">
                    <span className="rs-bar-name">{topic}</span>
                    <span className="rs-bar-score" style={{ color: barColor(score) }}>{score}/10</span>
                  </div>
                  <div className="rs-bar-track">
                    <div className="rs-bar-fill" style={{ width: `${score * 10}%`, background: barColor(score) }} />
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Transcript */}
          {results.transcript?.length > 0 && (
            <div className="rs-card">
              <div className="rs-section-title">Full Transcript</div>
              <div className="rs-transcript">
                {results.transcript.map((msg, i) => (
                  <div key={i} className="rs-msg">
                    <div className="rs-msg-role" style={{ color: msg.role === 'assistant' ? '#1565c0' : '#6b7a8d' }}>
                      {msg.role === 'assistant' ? 'Interviewer' : 'Candidate'}
                    </div>
                    <div className="rs-msg-content">{msg.content}</div>
                  </div>
                ))}
              </div>
            </div>
          )}

          <button className="rs-btn" onClick={() => navigate('/')}>
            ← Start Another Interview
          </button>

        </div>
      </div>
    </>
  )
}
