import { useState, useRef } from 'react'
import { BACKEND } from '../config'

const REC_STYLE = {
  Shortlist: { tag: 'tag-green', label: 'Shortlist' },
  Maybe: { tag: 'tag-amber', label: 'Maybe' },
  Reject: { tag: 'tag-red', label: 'Reject' },
}

export default function Shortlist() {
  const fileRef = useRef(null)
  const [files, setFiles] = useState([])
  const [position, setPosition] = useState('')
  const [requirements, setRequirements] = useState('')
  const [loading, setLoading] = useState(false)
  const [results, setResults] = useState(null)
  const [error, setError] = useState('')

  const handleFiles = (fileList) => {
    const valid = Array.from(fileList).filter(f => f.name.match(/\.(pdf|docx|doc)$/i))
    setFiles(valid)
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (files.length === 0) { setError('Upload at least one resume.'); return }
    setLoading(true)
    setError('')
    setResults(null)

    const formData = new FormData()
    files.forEach(f => formData.append('files', f))
    formData.append('position', position)
    formData.append('requirements', requirements)

    try {
      const res = await fetch(`${BACKEND}/api/shortlist`, { method: 'POST', body: formData })
      if (!res.ok) throw new Error()
      setResults(await res.json())
    } catch {
      setError('Something went wrong. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ minHeight: '100vh', padding: '2rem', maxWidth: 900, margin: '0 auto' }}>
      <div style={{ marginBottom: '2rem' }}>
        <span className="tag tag-blue" style={{ marginBottom: '0.75rem', display: 'inline-block' }}>Admin</span>
        <h1 style={{ fontSize: '1.8rem', fontWeight: 700 }}>Resume Shortlister</h1>
        <p style={{ color: 'var(--text-muted)', marginTop: '0.3rem' }}>Upload multiple resumes — AI ranks and shortlists them against your requirements.</p>
      </div>

      {/* Upload form */}
      <form className="card" onSubmit={handleSubmit} style={{ marginBottom: '2rem' }}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '1rem' }}>
          <div className="field" style={{ marginBottom: 0 }}>
            <label>Position</label>
            <input type="text" placeholder="e.g. Machine Learning Engineer" required
              value={position} onChange={e => setPosition(e.target.value)} />
          </div>
          <div className="field" style={{ marginBottom: 0 }}>
            <label>Resumes</label>
            <div
              onClick={() => fileRef.current?.click()}
              style={{
                padding: '0.65rem 1rem',
                background: 'var(--surface2)',
                border: '1px solid var(--border)',
                borderRadius: 8,
                cursor: 'pointer',
                color: files.length ? 'var(--green)' : 'var(--text-muted)',
                fontSize: '0.9rem'
              }}
            >
              {files.length ? `✓ ${files.length} file${files.length > 1 ? 's' : ''} selected` : '📂 Click to upload (PDF/DOCX)'}
            </div>
            <input ref={fileRef} type="file" multiple accept=".pdf,.docx,.doc"
              style={{ display: 'none' }} onChange={e => handleFiles(e.target.files)} />
          </div>
        </div>

        <div className="field" style={{ marginBottom: '1rem' }}>
          <label>Job Requirements</label>
          <textarea
            rows={4} required
            placeholder="List the key skills, experience, and qualifications required for this role..."
            value={requirements}
            onChange={e => setRequirements(e.target.value)}
            style={{
              width: '100%', padding: '0.75rem 1rem',
              background: 'var(--surface2)', border: '1px solid var(--border)',
              borderRadius: 8, color: 'var(--text)', fontSize: '0.9rem',
              outline: 'none', resize: 'vertical', fontFamily: 'var(--font)'
            }}
          />
        </div>

        {error && <div style={{ color: 'var(--red)', fontSize: '0.875rem', marginBottom: '0.75rem' }}>{error}</div>}

        <button className="btn-primary" type="submit" disabled={loading}>
          {loading ? <><span className="spinner" />Evaluating {files.length} resume{files.length > 1 ? 's' : ''}...</> : 'Run Shortlisting →'}
        </button>
      </form>

      {/* Results */}
      {results && (
        <div>
          <div style={{ display: 'flex', gap: '1rem', marginBottom: '1.5rem', flexWrap: 'wrap' }}>
            {[
              { label: 'Total', value: results.total, color: 'var(--text)' },
              { label: 'Shortlisted', value: results.breakdown.shortlist, color: 'var(--green)' },
              { label: 'Maybe', value: results.breakdown.maybe, color: 'var(--amber)' },
              { label: 'Rejected', value: results.breakdown.reject, color: 'var(--red)' },
            ].map(s => (
              <div key={s.label} className="card" style={{ flex: '1 1 120px', textAlign: 'center', padding: '1rem' }}>
                <div style={{ fontSize: '1.8rem', fontWeight: 700, color: s.color }}>{s.value}</div>
                <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.5px' }}>{s.label}</div>
              </div>
            ))}
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
            {results.shortlist.map((r, i) => {
              const style = REC_STYLE[r.recommendation] || REC_STYLE.Maybe
              return (
                <div key={i} className="card" style={{ display: 'flex', gap: '1rem', alignItems: 'flex-start' }}>
                  <div style={{
                    width: 36, height: 36, borderRadius: '50%',
                    background: 'var(--surface2)', border: '1px solid var(--border)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontWeight: 700, fontSize: '0.9rem', flexShrink: 0, color: 'var(--text-muted)'
                  }}>
                    {i + 1}
                  </div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.25rem', flexWrap: 'wrap' }}>
                      <span style={{ fontWeight: 700 }}>{r.candidate}</span>
                      <span className={`tag ${style.tag}`}>{style.label}</span>
                      <span style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>{r.domain}</span>
                    </div>
                    <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '0.5rem' }}>{r.filename}</div>
                    <div style={{ fontSize: '0.85rem', color: 'var(--text-dim)', marginBottom: '0.5rem' }}>{r.reasoning}</div>
                    {r.strengths.length > 0 && (
                      <div style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap' }}>
                        {r.strengths.map((s, j) => <span key={j} className="tag tag-blue">{s}</span>)}
                      </div>
                    )}
                  </div>
                  <div style={{ textAlign: 'right', flexShrink: 0 }}>
                    <div style={{ fontSize: '1.4rem', fontWeight: 700 }}>{r.score}</div>
                    <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>/ 100</div>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
