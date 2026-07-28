import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'

const ADMIN_PASSWORD = import.meta.env.VITE_ADMIN_PASSWORD || 'srm2026'
const LS_KEY = 'srm_interviews'

const styles = `
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  .ad-body {
    min-height: 100vh;
    background: #f0f4f8;
    font-family: 'Inter', system-ui, sans-serif;
    color: #1a2332;
    display: flex; flex-direction: column;
  }

  /* HEADER */
  .ad-header {
    background: #fff;
    border-bottom: 1px solid #e0e7ef;
    padding: 0 2rem;
    display: flex; align-items: center; justify-content: space-between;
  }
  .ad-header-left { display: flex; align-items: center; gap: 20px; padding: 14px 0; }
  .ad-logo { height: 60px; object-fit: contain; }
  .ad-divider { width: 1px; height: 48px; background: #d8e2ef; }
  .ad-dept { font-size: 0.7rem; font-weight: 700; color: #1565c0; text-transform: uppercase; letter-spacing: 0.8px; line-height: 1.3; }
  .ad-title { font-size: 1.05rem; font-weight: 900; color: #1a237e; text-transform: uppercase; letter-spacing: 0.5px; line-height: 1.2; margin-top: 2px; }
  .ad-header-right { display: flex; align-items: center; gap: 10px; }
  .ad-badge {
    display: flex; align-items: center; gap: 6px;
    background: rgba(26,35,126,0.07); border: 1px solid rgba(26,35,126,0.2);
    border-radius: 20px; padding: 5px 14px;
    font-size: 0.72rem; font-weight: 700; color: #1a237e;
    text-transform: uppercase; letter-spacing: 0.6px;
  }
  .ad-back-btn {
    background: none; border: 1px solid #d8e2ef; border-radius: 8px;
    padding: 6px 14px; font-size: 0.78rem; font-weight: 600;
    color: #6b7a8d; cursor: pointer; font-family: inherit;
    transition: border-color 0.2s, color 0.2s;
  }
  .ad-back-btn:hover { border-color: #1565c0; color: #1565c0; }
  .ad-logout-btn {
    background: none; border: 1px solid rgba(198,40,40,0.3); border-radius: 8px;
    padding: 6px 14px; font-size: 0.78rem; font-weight: 600;
    color: #c62828; cursor: pointer; font-family: inherit; transition: all 0.2s;
  }
  .ad-logout-btn:hover { background: rgba(198,40,40,0.06); }

  /* LOGIN */
  .ad-login-wrap { flex: 1; display: flex; align-items: center; justify-content: center; padding: 2rem; }
  .ad-login-card {
    width: 100%; max-width: 400px;
    background: #fff; border: 1px solid #d8e2ef;
    border-radius: 16px; box-shadow: 0 4px 24px rgba(21,101,192,0.08);
    padding: 2.5rem; display: flex; flex-direction: column; gap: 1.25rem; align-items: center;
  }
  .ad-login-logo { height: 56px; margin-bottom: 0.25rem; }
  .ad-login-title { font-size: 1rem; font-weight: 900; color: #1a237e; text-transform: uppercase; letter-spacing: 0.5px; text-align: center; }
  .ad-login-sub { font-size: 0.82rem; color: #6b7a8d; text-align: center; }
  .ad-input {
    width: 100%; height: 48px;
    border: 1.5px solid #d8e2ef; border-radius: 10px;
    padding: 0 14px; font-size: 0.95rem; color: #1a2332;
    background: #fff; outline: none;
    transition: border-color 0.2s, box-shadow 0.2s;
    font-family: 'Inter', system-ui, sans-serif;
  }
  .ad-input:focus { border-color: #1565c0; box-shadow: 0 0 0 3px rgba(21,101,192,0.1); }
  .ad-login-btn {
    width: 100%; height: 50px;
    background: linear-gradient(135deg, #1565c0, #1a6fd4);
    border: none; border-radius: 12px;
    color: #fff; font-size: 0.95rem; font-weight: 700;
    cursor: pointer; display: flex; align-items: center; justify-content: center; gap: 8px;
    transition: opacity 0.2s; letter-spacing: 0.3px;
    font-family: 'Inter', system-ui, sans-serif; text-transform: uppercase;
  }
  .ad-login-btn:hover:not(:disabled) { opacity: 0.9; }
  .ad-login-btn:disabled { opacity: 0.6; cursor: not-allowed; }
  .ad-login-error {
    background: rgba(198,40,40,0.07); border: 1px solid rgba(198,40,40,0.25);
    border-radius: 8px; padding: 10px 14px;
    color: #c62828; font-size: 0.83rem; font-weight: 500;
    text-align: center; width: 100%;
  }

  /* DASHBOARD */
  .ad-main {
    flex: 1; max-width: 1100px; margin: 0 auto; width: 100%;
    padding: 2rem 1.5rem 4rem;
    display: flex; flex-direction: column; gap: 1.5rem;
  }
  .ad-page-head { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 1rem; }
  .ad-page-eyebrow { font-size: 0.68rem; font-weight: 800; color: #1565c0; text-transform: uppercase; letter-spacing: 1px; }
  .ad-page-name { font-size: 1.5rem; font-weight: 900; color: #1a237e; margin-top: 2px; }

  .ad-head-actions { display: flex; gap: 8px; }
  .ad-clear-btn {
    height: 40px; padding: 0 16px;
    background: #fff; border: 1.5px solid rgba(198,40,40,0.3); border-radius: 10px;
    font-size: 0.8rem; font-weight: 700; color: #c62828;
    cursor: pointer; font-family: inherit; transition: all 0.2s;
  }
  .ad-clear-btn:hover { background: rgba(198,40,40,0.05); }
  .ad-refresh-btn {
    height: 40px; padding: 0 18px;
    background: #fff; border: 1.5px solid #d8e2ef; border-radius: 10px;
    font-size: 0.82rem; font-weight: 700; color: #1565c0;
    cursor: pointer; display: flex; align-items: center; gap: 6px;
    transition: all 0.2s; font-family: inherit;
  }
  .ad-refresh-btn:hover { border-color: #1565c0; background: rgba(21,101,192,0.04); }

  /* STATS */
  .ad-stats { display: flex; gap: 1rem; flex-wrap: wrap; }
  .ad-stat {
    flex: 1; min-width: 100px;
    background: #fff; border: 1px solid #d8e2ef;
    border-radius: 12px; padding: 1rem 1.25rem;
    box-shadow: 0 1px 6px rgba(21,101,192,0.05);
  }
  .ad-stat-num { font-size: 1.8rem; font-weight: 900; line-height: 1; }
  .ad-stat-label { font-size: 0.68rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; color: #6b7a8d; margin-top: 4px; }

  /* EMPTY */
  .ad-empty {
    background: #fff; border: 1px solid #d8e2ef; border-radius: 14px;
    padding: 4rem 2rem; text-align: center;
    display: flex; flex-direction: column; align-items: center; gap: 0.75rem;
  }
  .ad-empty-icon { font-size: 3rem; }
  .ad-empty-title { font-size: 1rem; font-weight: 700; color: #1a2332; }
  .ad-empty-sub { font-size: 0.85rem; color: #6b7a8d; max-width: 340px; line-height: 1.5; }

  /* CARDS */
  .ad-cards { display: flex; flex-direction: column; gap: 1rem; }
  .ad-card { background: #fff; border: 1px solid #d8e2ef; border-radius: 14px; overflow: hidden; box-shadow: 0 2px 10px rgba(21,101,192,0.05); }
  .ad-card-head {
    padding: 1.25rem 1.5rem;
    display: flex; align-items: flex-start; justify-content: space-between; gap: 1rem; flex-wrap: wrap;
    cursor: pointer; transition: background 0.15s;
  }
  .ad-card-head:hover { background: rgba(21,101,192,0.02); }
  .ad-card-left { flex: 1; min-width: 200px; }
  .ad-candidate-name { font-size: 1.05rem; font-weight: 800; color: #1a237e; }
  .ad-candidate-meta { display: flex; flex-wrap: wrap; gap: 0.4rem 1.25rem; margin-top: 4px; }
  .ad-meta-item { font-size: 0.78rem; color: #6b7a8d; font-weight: 500; display: flex; align-items: center; gap: 4px; }
  .ad-meta-label { font-weight: 700; color: #374151; }
  .ad-position-tag {
    display: inline-flex; align-items: center;
    background: rgba(21,101,192,0.07); color: #1565c0;
    border-radius: 6px; padding: 2px 8px;
    font-size: 0.72rem; font-weight: 700;
    text-transform: uppercase; letter-spacing: 0.3px; margin-top: 6px;
  }
  .ad-card-right { display: flex; align-items: center; gap: 0.75rem; flex-shrink: 0; flex-wrap: wrap; justify-content: flex-end; }
  .ad-score-box { text-align: center; min-width: 48px; }
  .ad-score-num { font-size: 1.6rem; font-weight: 900; line-height: 1; }
  .ad-score-denom { font-size: 0.7rem; color: #6b7a8d; font-weight: 600; }
  .ad-rec-badge {
    display: inline-flex; align-items: center;
    border-radius: 8px; padding: 5px 12px;
    font-size: 0.75rem; font-weight: 800;
    text-transform: uppercase; letter-spacing: 0.4px;
    border: 1px solid;
  }
  .ad-flag-icon { font-size: 1.2rem; flex-shrink: 0; }
  .ad-expand-col { display: flex; flex-direction: column; align-items: flex-end; gap: 4px; }
  .ad-expand-chevron { font-size: 0.75rem; color: #9ba8b5; font-weight: 700; transition: transform 0.2s; }
  .ad-expand-chevron.open { transform: rotate(180deg); }
  .ad-card-time { font-size: 0.7rem; color: #9ba8b5; font-weight: 500; white-space: nowrap; }

  /* EXPANDED */
  .ad-expand { border-top: 1px solid #e8edf5; padding: 1.25rem 1.5rem; display: flex; flex-direction: column; gap: 1.25rem; }
  .ad-section-title { font-size: 0.68rem; font-weight: 800; text-transform: uppercase; letter-spacing: 1px; color: #1565c0; margin-bottom: 0.75rem; }
  .ad-flag-alert {
    background: rgba(183,28,28,0.06); border: 1px solid rgba(183,28,28,0.25);
    border-radius: 10px; padding: 0.75rem 1rem;
    font-size: 0.82rem; font-weight: 600; color: #b71c1c;
  }

  /* BARS */
  .ad-bar-row { margin-bottom: 0.85rem; }
  .ad-bar-row:last-child { margin-bottom: 0; }
  .ad-bar-meta { display: flex; justify-content: space-between; margin-bottom: 5px; font-size: 0.85rem; }
  .ad-bar-name { font-weight: 600; color: #1a2332; }
  .ad-bar-score { font-weight: 800; }
  .ad-bar-track { background: #f0f4f8; border-radius: 6px; height: 7px; overflow: hidden; }
  .ad-bar-fill { height: 100%; border-radius: 6px; transition: width 0.8s ease; }

  /* TRANSCRIPT */
  .ad-transcript { display: flex; flex-direction: column; gap: 0.6rem; max-height: 320px; overflow-y: auto; scrollbar-width: thin; scrollbar-color: #d8e2ef transparent; }
  .ad-msg { display: flex; gap: 0.75rem; font-size: 0.83rem; }
  .ad-msg-role { font-weight: 700; min-width: 80px; flex-shrink: 0; font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.4px; padding-top: 2px; }
  .ad-msg-content { color: #374151; line-height: 1.55; }

  @media (max-width: 640px) {
    .ad-header { padding: 0 1rem; }
    .ad-logo { height: 44px; }
    .ad-title { font-size: 0.82rem; }
    .ad-badge { display: none; }
    .ad-card-head { flex-direction: column; }
    .ad-card-right { justify-content: flex-start; }
  }
`

const REC_STYLE = {
  Hire:   { background: 'rgba(46,125,50,0.08)',  color: '#1b5e20', borderColor: 'rgba(46,125,50,0.3)' },
  Hold:   { background: 'rgba(245,124,0,0.08)',  color: '#bf360c', borderColor: 'rgba(245,124,0,0.3)' },
  Reject: { background: 'rgba(198,40,40,0.08)',  color: '#b71c1c', borderColor: 'rgba(198,40,40,0.3)' },
}

const barColor = s => s >= 7 ? '#2e7d32' : s >= 5 ? '#e65100' : '#c62828'
const scoreColor = s => s >= 6.5 ? '#2e7d32' : s >= 5 ? '#e65100' : '#c62828'

function formatTime(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('en-IN', {
    day: '2-digit', month: 'short',
    hour: '2-digit', minute: '2-digit', hour12: true,
  })
}

function loadFromStorage() {
  try {
    return JSON.parse(localStorage.getItem(LS_KEY) || '[]')
  } catch {
    return []
  }
}

export default function Admin() {
  const navigate = useNavigate()
  const [password, setPassword] = useState('')
  const [authed, setAuthed] = useState(() => sessionStorage.getItem('admin_authed') === '1')
  const [authError, setAuthError] = useState('')
  const [interviews, setInterviews] = useState([])
  const [expandedId, setExpandedId] = useState(null)

  useEffect(() => {
    if (authed) setInterviews(loadFromStorage())
  }, [authed])

  const handleLogin = (e) => {
    e?.preventDefault()
    if (!password.trim()) return
    if (password === ADMIN_PASSWORD) {
      sessionStorage.setItem('admin_authed', '1')
      setAuthed(true)
      setAuthError('')
    } else {
      setAuthError('Incorrect password. Please try again.')
    }
  }

  const refresh = () => setInterviews(loadFromStorage())

  const clearData = () => {
    if (!window.confirm('Clear all stored interview records from this browser? This cannot be undone.')) return
    localStorage.removeItem(LS_KEY)
    setInterviews([])
  }

  const logout = () => {
    sessionStorage.removeItem('admin_authed')
    setAuthed(false)
    setPassword('')
  }

  const toggleExpand = (id) => setExpandedId(prev => prev === id ? null : id)

  const total = interviews.length
  const hireCount = interviews.filter(i => i.recommendation === 'Hire').length
  const holdCount = interviews.filter(i => i.recommendation === 'Hold').length
  const rejectCount = interviews.filter(i => i.recommendation === 'Reject').length
  const flaggedCount = interviews.filter(i => i.is_flagged).length

  return (
    <>
      <style>{styles}</style>
      <div className="ad-body">

        {/* Header */}
        <header className="ad-header">
          <div className="ad-header-left">
            <img src="/srm-logo.png" alt="SRM" className="ad-logo" />
            <div className="ad-divider" />
            <div>
              <div className="ad-dept">Department of Computer Science and Engineering</div>
              <div className="ad-title">AI Mock Interview Drive</div>
            </div>
          </div>
          <div className="ad-header-right">
            <div className="ad-badge">Admin Panel</div>
            {authed && <button className="ad-logout-btn" onClick={logout}>Sign Out</button>}
            <button className="ad-back-btn" onClick={() => navigate('/')}>← Home</button>
          </div>
        </header>

        {/* LOGIN */}
        {!authed && (
          <div className="ad-login-wrap">
            <div className="ad-login-card">
              <img src="/srm-logo.png" alt="SRM" className="ad-login-logo" />
              <div className="ad-login-title">Admin Access</div>
              <div className="ad-login-sub">Enter the admin password to view interview reports</div>
              <form style={{ width: '100%', display: 'flex', flexDirection: 'column', gap: '0.75rem' }}
                onSubmit={handleLogin}>
                <input
                  className="ad-input"
                  type="password"
                  placeholder="Admin password"
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  autoFocus
                />
                {authError && <div className="ad-login-error">{authError}</div>}
                <button className="ad-login-btn" type="submit" disabled={!password.trim()}>
                  Access Dashboard →
                </button>
              </form>
            </div>
          </div>
        )}

        {/* DASHBOARD */}
        {authed && (
          <div className="ad-main">

            {/* Page heading */}
            <div className="ad-page-head">
              <div>
                <div className="ad-page-eyebrow">Interview Dashboard</div>
                <div className="ad-page-name">Candidate Reports</div>
              </div>
              <div className="ad-head-actions">
                {interviews.length > 0 && (
                  <button className="ad-clear-btn" onClick={clearData}>Clear All</button>
                )}
                <button className="ad-refresh-btn" onClick={refresh}>↻ Refresh</button>
              </div>
            </div>

            {/* Stats */}
            <div className="ad-stats">
              <div className="ad-stat">
                <div className="ad-stat-num" style={{ color: '#1565c0' }}>{total}</div>
                <div className="ad-stat-label">Total</div>
              </div>
              <div className="ad-stat">
                <div className="ad-stat-num" style={{ color: '#1b5e20' }}>{hireCount}</div>
                <div className="ad-stat-label">Hire</div>
              </div>
              <div className="ad-stat">
                <div className="ad-stat-num" style={{ color: '#bf360c' }}>{holdCount}</div>
                <div className="ad-stat-label">Hold</div>
              </div>
              <div className="ad-stat">
                <div className="ad-stat-num" style={{ color: '#b71c1c' }}>{rejectCount}</div>
                <div className="ad-stat-label">Reject</div>
              </div>
              <div className="ad-stat">
                <div className="ad-stat-num" style={{ color: flaggedCount > 0 ? '#b71c1c' : '#9ba8b5' }}>{flaggedCount}</div>
                <div className="ad-stat-label">Flagged</div>
              </div>
            </div>

            {/* Empty */}
            {interviews.length === 0 && (
              <div className="ad-empty">
                <div className="ad-empty-icon">📋</div>
                <div className="ad-empty-title">No interviews completed yet</div>
                <div className="ad-empty-sub">Reports appear here automatically once students complete their interview on this device. Click Refresh to check.</div>
              </div>
            )}

            {/* Cards */}
            {interviews.length > 0 && (
              <div className="ad-cards">
                {interviews.map((iv, idx) => {
                  const rec = REC_STYLE[iv.recommendation] || REC_STYLE.Hold
                  const isOpen = expandedId === (iv.session_id || idx)
                  const topicEntries = Object.entries(iv.topic_scores || {})
                  const cardKey = iv.session_id || idx

                  return (
                    <div className="ad-card" key={cardKey}>

                      <div className="ad-card-head" onClick={() => toggleExpand(cardKey)}>
                        <div className="ad-card-left">
                          <div className="ad-candidate-name">{iv.candidate}</div>
                          <div className="ad-candidate-meta">
                            <span className="ad-meta-item">
                              <span className="ad-meta-label">Email:</span> {iv.email || '—'}
                            </span>
                            <span className="ad-meta-item">
                              <span className="ad-meta-label">Phone:</span> {iv.phone || '—'}
                            </span>
                          </div>
                          <div className="ad-position-tag">{iv.position}</div>
                        </div>

                        <div className="ad-card-right">
                          <div className="ad-score-box">
                            <div className="ad-score-num" style={{ color: scoreColor(iv.overall_score) }}>
                              {iv.overall_score}
                            </div>
                            <div className="ad-score-denom">/10</div>
                          </div>

                          <div className="ad-rec-badge" style={rec}>
                            {iv.recommendation}
                          </div>

                          {iv.is_flagged && (
                            <div className="ad-flag-icon" title="Session flagged — proxy attempt suspected">🚨</div>
                          )}

                          <div className="ad-expand-col">
                            <div className={`ad-expand-chevron${isOpen ? ' open' : ''}`}>▼</div>
                            <div className="ad-card-time">{formatTime(iv.completed_at)}</div>
                          </div>
                        </div>
                      </div>

                      {/* Expanded */}
                      {isOpen && (
                        <div className="ad-expand">

                          {iv.is_flagged && (
                            <div className="ad-flag-alert">
                              🚨 Session flagged — face verification failed during the interview. Disqualified pending manual review.
                            </div>
                          )}

                          {topicEntries.length > 0 && (
                            <div>
                              <div className="ad-section-title">Topic Breakdown</div>
                              {topicEntries.map(([topic, score]) => (
                                <div className="ad-bar-row" key={topic}>
                                  <div className="ad-bar-meta">
                                    <span className="ad-bar-name">{topic}</span>
                                    <span className="ad-bar-score" style={{ color: barColor(score) }}>{score}/10</span>
                                  </div>
                                  <div className="ad-bar-track">
                                    <div className="ad-bar-fill" style={{ width: `${score * 10}%`, background: barColor(score) }} />
                                  </div>
                                </div>
                              ))}
                            </div>
                          )}

                          {iv.transcript?.length > 0 && (
                            <div>
                              <div className="ad-section-title">Full Transcript</div>
                              <div className="ad-transcript">
                                {iv.transcript.map((msg, i) => (
                                  <div className="ad-msg" key={i}>
                                    <div className="ad-msg-role"
                                      style={{ color: msg.role === 'assistant' ? '#1565c0' : '#6b7a8d' }}>
                                      {msg.role === 'assistant' ? 'Interviewer' : (iv.candidate?.split(' ')[0] || 'Candidate')}
                                    </div>
                                    <div className="ad-msg-content">{msg.content}</div>
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}

                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            )}

          </div>
        )}

      </div>
    </>
  )
}
