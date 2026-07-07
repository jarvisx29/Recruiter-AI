import { useState, useRef, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { BACKEND } from '../config'
import { loadFaceModels, getDescriptor, captureFromVideo, compareDescriptors } from '../hooks/useWebcamSecurity'

const POSITIONS = [
  // Industry roles
  'Software Development Engineer (SDE)',
  'Junior Developer',
  'Senior Developer',
  'Machine Learning Engineer',
  'Data Scientist',
  'DevOps Engineer',
  'HR Executive',
  'Product Manager',
  // Academic / Faculty roles
  'Lecturer',
  'Assistant Professor',
  'Associate Professor',
  'Professor',
  'Senior Professor',
  'Professor & Head of Department',
  'Research Associate',
]

const LOAD_STEPS = [
  'Uploading resume...',
  'Extracting your profile...',
  'Analysing skills & experience...',
  'Building your personalised interview...',
]

const styles = `
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  .ap-body {
    min-height: 100vh;
    background: #f0f4f8;
    font-family: 'Inter', system-ui, sans-serif;
    color: #1a2332;
    display: flex;
    flex-direction: column;
  }

  /* ── SRM HEADER ── */
  .ap-srm-header {
    background: #fff;
    border-bottom: 1px solid #e0e7ef;
    padding: 0 2rem;
    display: flex;
    align-items: center;
    justify-content: space-between;
  }
  .ap-srm-header-left {
    display: flex;
    align-items: center;
    gap: 20px;
    padding: 14px 0;
  }
  .ap-srm-logo {
    height: 60px;
    object-fit: contain;
  }
  .ap-srm-divider {
    width: 1px;
    height: 48px;
    background: #d8e2ef;
  }
  .ap-srm-title-block {}
  .ap-srm-dept {
    font-size: 0.7rem;
    font-weight: 700;
    color: #1565c0;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    line-height: 1.3;
  }
  .ap-srm-title {
    font-size: 1.05rem;
    font-weight: 900;
    color: #1a237e;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    line-height: 1.2;
    margin-top: 2px;
  }
  .ap-srm-header-right {
    display: flex;
    align-items: center;
    gap: 8px;
    background: rgba(229, 30, 140, 0.08);
    border: 1px solid rgba(229, 30, 140, 0.25);
    border-radius: 20px;
    padding: 5px 14px;
    font-size: 0.72rem;
    font-weight: 700;
    color: #c2185b;
    text-transform: uppercase;
    letter-spacing: 0.6px;
  }
  .ap-srm-dot {
    width: 6px; height: 6px;
    border-radius: 50%;
    background: #e91e8c;
    animation: ap-blink 1.5s ease-in-out infinite;
  }
  @keyframes ap-blink { 0%,100%{opacity:1} 50%{opacity:0.3} }

  /* ── STATS BAR ── */
  .ap-stats {
    display: flex;
    justify-content: center;
    gap: 3rem;
    padding: 1.25rem 2rem;
    background: #fff;
    border-bottom: 1px solid #d8e2ef;
  }
  .ap-stat { text-align: center; }
  .ap-stat-num { font-size: 1.4rem; font-weight: 800; color: #1565c0; }
  .ap-stat-label { font-size: 0.72rem; color: #6b7a8d; font-weight: 500; margin-top: 2px; text-transform: uppercase; letter-spacing: 0.4px; }

  /* ── MAIN ── */
  .ap-main {
    flex: 1;
    display: flex;
    justify-content: center;
    padding: 2.5rem 1.5rem 4rem;
  }
  .ap-card {
    width: 100%; max-width: 520px;
    background: #fff;
    border-radius: 16px;
    border: 1px solid #d8e2ef;
    box-shadow: 0 2px 12px rgba(21,101,192,0.07);
    padding: 2.25rem;
    display: flex; flex-direction: column; gap: 1.25rem;
  }
  .ap-card-title {
    font-size: 0.75rem;
    font-weight: 800;
    color: #1a237e;
    text-transform: uppercase;
    letter-spacing: 1px;
    padding-bottom: 1rem;
    border-bottom: 2px solid #e8edf5;
  }

  /* ── FIELDS ── */
  .ap-field label {
    display: block;
    font-size: 0.75rem; font-weight: 700;
    color: #1565c0;
    margin-bottom: 6px;
    text-transform: uppercase; letter-spacing: 0.5px;
  }
  .ap-field input, .ap-field select {
    width: 100%;
    height: 46px;
    border: 1.5px solid #d8e2ef;
    border-radius: 10px;
    padding: 0 14px;
    font-size: 0.95rem;
    color: #1a2332;
    background: #fff;
    outline: none;
    transition: border-color 0.2s, box-shadow 0.2s;
    font-family: 'Inter', system-ui, sans-serif;
  }
  .ap-field input:focus, .ap-field select:focus {
    border-color: #1565c0;
    box-shadow: 0 0 0 3px rgba(21,101,192,0.1);
  }
  .ap-field input::placeholder { color: #b0bac6; }

  /* ── DROP ZONE ── */
  .ap-drop {
    border: 2px dashed #c5cae9;
    border-radius: 12px;
    padding: 1.75rem;
    text-align: center;
    cursor: pointer;
    transition: all 0.2s;
    background: #f8fafc;
  }
  .ap-drop:hover { border-color: #1565c0; background: rgba(21,101,192,0.03); }
  .ap-drop.dragging { border-color: #1565c0; background: rgba(21,101,192,0.06); }
  .ap-drop.has-file { border-color: #2e7d32; background: rgba(46,125,50,0.04); border-style: solid; }
  .ap-drop-icon { font-size: 2rem; margin-bottom: 0.5rem; }
  .ap-drop-text { font-size: 0.88rem; color: #6b7a8d; }
  .ap-drop-text strong { color: #1565c0; }
  .ap-drop-file { font-weight: 600; color: #2e7d32; font-size: 0.92rem; }

  /* ── BUTTON ── */
  .ap-btn {
    width: 100%;
    height: 52px;
    background: linear-gradient(135deg, #1565c0, #1a6fd4);
    border: none;
    border-radius: 12px;
    color: #fff;
    font-size: 0.95rem; font-weight: 700;
    cursor: pointer;
    display: flex; align-items: center; justify-content: center; gap: 8px;
    transition: opacity 0.2s, transform 0.1s;
    letter-spacing: 0.3px;
    font-family: 'Inter', system-ui, sans-serif;
    text-transform: uppercase;
  }
  .ap-btn:hover:not(:disabled) { opacity: 0.92; transform: translateY(-1px); }
  .ap-btn:disabled { opacity: 0.6; cursor: not-allowed; transform: none; }
  .ap-btn-spin {
    width: 16px; height: 16px;
    border: 2px solid rgba(255,255,255,0.4);
    border-top-color: #fff;
    border-radius: 50%;
    animation: ap-spin 0.7s linear infinite;
  }
  @keyframes ap-spin { to { transform: rotate(360deg); } }

  /* ── LOADING OVERLAY ── */
  .ap-overlay {
    position: fixed; inset: 0; z-index: 999;
    background: rgba(26,35,126,0.93);
    backdrop-filter: blur(6px);
    display: flex; align-items: center; justify-content: center;
    flex-direction: column; gap: 1.5rem;
    animation: ap-fade 0.3s ease;
  }
  @keyframes ap-fade { from{opacity:0} to{opacity:1} }
  .ap-overlay-logo-wrap {
    background: #fff;
    border-radius: 12px;
    padding: 10px 20px;
    display: flex; align-items: center; justify-content: center;
  }
  .ap-overlay-logo { height: 46px; object-fit: contain; }
  .ap-overlay-ring {
    width: 56px; height: 56px;
    border: 4px solid rgba(233,30,140,0.2);
    border-top-color: #e91e8c;
    border-radius: 50%;
    animation: ap-spin 0.9s linear infinite;
  }
  .ap-overlay-text { color: #fff; font-size: 1rem; font-weight: 700; text-align: center; text-transform: uppercase; letter-spacing: 0.5px; }
  .ap-overlay-sub { color: rgba(255,255,255,0.45); font-size: 0.8rem; }
  .ap-overlay-bar {
    width: 200px; height: 3px;
    background: rgba(255,255,255,0.1);
    border-radius: 2px; overflow: hidden;
  }
  .ap-overlay-bar-fill {
    height: 100%;
    background: #e91e8c;
    border-radius: 2px;
    transition: width 1.2s ease;
  }

  .ap-error {
    background: rgba(198,40,40,0.07);
    border: 1px solid rgba(198,40,40,0.25);
    border-radius: 8px;
    padding: 10px 14px;
    color: #c62828;
    font-size: 0.85rem;
    font-weight: 500;
  }

  .ap-note {
    display: flex; align-items: center; gap: 8px;
    padding: 12px 14px;
    background: #f0f4f8;
    border-radius: 10px;
    font-size: 0.78rem; color: #6b7a8d;
  }

  /* ── PHOTO UPLOAD (form page) ── */
  .ap-photo-row {
    display: flex; align-items: center; gap: 1rem;
    border: 2px dashed #c5cae9; border-radius: 10px; padding: 0.75rem 1rem;
    cursor: pointer; transition: border-color 0.2s; background: #f8fafc;
  }
  .ap-photo-row:hover { border-color: #1565c0; }
  .ap-photo-mini-img { width: 56px; height: 72px; object-fit: cover; border-radius: 6px; flex-shrink: 0; border: 1px solid #d8e2ef; }
  .ap-photo-mini-icon { font-size: 1.6rem; flex-shrink: 0; }
  .ap-photo-mini-text { font-size: 0.83rem; color: #374151; }
  .ap-photo-mini-sub { font-size: 0.73rem; color: #6b7a8d; margin-top: 2px; }
  .ap-photo-required-tag { font-size: 0.7rem; font-weight: 700; color: #c62828; background: rgba(198,40,40,0.08); border-radius: 4px; padding: 1px 6px; }

  /* ── VERIFY STEP ── */
  .ap-verify-wrap {
    flex: 1; display: flex; justify-content: center; align-items: flex-start;
    padding: 2.5rem 1.5rem 4rem;
  }
  .ap-verify-card {
    width: 100%; max-width: 560px;
    background: #fff; border: 1px solid #d8e2ef;
    border-radius: 16px; box-shadow: 0 2px 12px rgba(21,101,192,0.07);
    padding: 2.25rem; display: flex; flex-direction: column; gap: 1.5rem;
  }
  .ap-verify-title {
    font-size: 0.75rem; font-weight: 800; color: #1a237e;
    text-transform: uppercase; letter-spacing: 1px;
    padding-bottom: 1rem; border-bottom: 2px solid #e8edf5;
  }
  .ap-verify-panels {
    display: grid; grid-template-columns: 1fr 1fr; gap: 1rem;
  }
  .ap-verify-panel {
    display: flex; flex-direction: column; align-items: center; gap: 0.6rem;
  }
  .ap-verify-panel-label {
    font-size: 0.68rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.7px; color: #6b7a8d;
  }
  .ap-verify-photo {
    width: 100%; aspect-ratio: 3/4; max-height: 220px;
    object-fit: cover; border-radius: 10px; border: 2px solid #d8e2ef;
    background: #f0f4f8;
  }
  .ap-verify-video {
    width: 100%; aspect-ratio: 3/4; max-height: 220px;
    object-fit: cover; border-radius: 10px; border: 2px solid #d8e2ef;
    background: #0a0a0a; transform: scaleX(-1);
  }
  .ap-verify-placeholder {
    width: 100%; aspect-ratio: 3/4; max-height: 220px;
    border-radius: 10px; border: 2px dashed #c5cae9;
    background: #f0f4f8; display: flex; align-items: center; justify-content: center;
    flex-direction: column; gap: 0.5rem; color: #6b7a8d; font-size: 0.8rem; text-align: center;
    padding: 1rem;
  }
  .ap-verify-status {
    text-align: center; padding: 0.75rem 1rem; border-radius: 8px;
    font-size: 0.85rem; font-weight: 600;
  }
  .ap-verify-status.loading { background: rgba(21,101,192,0.07); color: #1565c0; }
  .ap-verify-status.ok { background: rgba(46,125,50,0.08); color: #2e7d32; }
  .ap-verify-status.fail { background: rgba(198,40,40,0.07); color: #c62828; }
  .ap-verify-status.warn { background: rgba(230,81,0,0.07); color: #e65100; }

  .ap-photo-upload-area {
    border: 2px dashed #c5cae9; border-radius: 12px; padding: 1.5rem;
    text-align: center; cursor: pointer; background: #f8fafc;
    transition: all 0.2s;
  }
  .ap-photo-upload-area:hover { border-color: #1565c0; }
  .ap-photo-upload-preview {
    width: 120px; height: 160px; object-fit: cover; border-radius: 8px;
    border: 2px solid #d8e2ef; margin: 0 auto 0.5rem;
    display: block;
  }
  .ap-link-btn {
    background: none; border: none; cursor: pointer;
    color: #1565c0; font-size: 0.8rem; font-weight: 600;
    text-decoration: underline; padding: 0; font-family: inherit;
  }

  @media (max-width: 600px) {
    .ap-srm-header { padding: 0 1rem; }
    .ap-srm-logo { height: 44px; }
    .ap-srm-title { font-size: 0.82rem; }
    .ap-srm-dept { font-size: 0.6rem; }
    .ap-stats { gap: 1.5rem; padding: 1rem; }
    .ap-srm-header-right { display: none; }
    .ap-verify-panels { grid-template-columns: 1fr; }
  }
`

export default function Apply() {
  const navigate = useNavigate()
  const fileRef = useRef(null)
  const photoFileRef = useRef(null)
  const videoRef = useRef(null)
  const refImgRef = useRef(null)
  const streamRef = useRef(null)

  const [file, setFile] = useState(null)
  const [dragging, setDragging] = useState(false)
  const [loading, setLoading] = useState(false)
  const [loadStep, setLoadStep] = useState(0)
  const [error, setError] = useState('')
  const [form, setForm] = useState({ name: '', email: '', position: '' })

  // Photo upload on form page
  const [userPhotoPreview, setUserPhotoPreview] = useState(null) // data-URL from form upload

  // Verify step state
  const [step, setStep] = useState('form') // 'form' | 'verify'
  const [sessionData, setSessionData] = useState(null)
  const [extractedPhoto, setExtractedPhoto] = useState(null) // from resume
  const [referencePhoto, setReferencePhoto] = useState(null) // confirmed photo (data-url)
  const [photoMode, setPhotoMode] = useState('extracted') // 'extracted' | 'upload'
  const [verifyPhase, setVerifyPhase] = useState('photo') // 'photo' | 'facecheck'
  const [verifyStatus, setVerifyStatus] = useState('idle') // 'idle'|'loading'|'ready'|'checking'|'ok'|'fail'|'no_face_ref'|'no_face_cam'|'cam_err'

  useEffect(() => {
    if (!loading) return
    const timers = LOAD_STEPS.map((_, i) =>
      setTimeout(() => setLoadStep(i), i * 1800)
    )
    return () => timers.forEach(clearTimeout)
  }, [loading])

  // Auto-start camera + load models once user enters facecheck phase
  useEffect(() => {
    if (step !== 'verify' || verifyPhase !== 'facecheck') return
    let cancelled = false
    const init = async () => {
      setVerifyStatus('loading')
      try {
        await loadFaceModels()
        if (cancelled) return
        const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'user' } })
        if (cancelled) { stream.getTracks().forEach(t => t.stop()); return }
        streamRef.current = stream
        if (videoRef.current) videoRef.current.srcObject = stream
        setVerifyStatus('ready')
      } catch {
        if (!cancelled) setVerifyStatus('cam_err')
      }
    }
    init()
    return () => {
      cancelled = true
      streamRef.current?.getTracks().forEach(t => t.stop())
      streamRef.current = null
    }
  }, [step, verifyPhase])

  const handleFile = (f) => {
    if (f && (f.name.endsWith('.pdf') || f.name.endsWith('.docx') || f.name.endsWith('.doc'))) {
      setFile(f); setError('')
    }
  }

  const handleDrop = (e) => {
    e.preventDefault(); setDragging(false); handleFile(e.dataTransfer.files[0])
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!file) { setError('Please upload your resume (PDF or DOCX).'); return }

    setLoading(true); setError(''); setLoadStep(0)

    const formData = new FormData()
    formData.append('file', file)
    formData.append('name', form.name)
    formData.append('email', form.email)
    formData.append('position', form.position)

    try {
      const res = await fetch(`${BACKEND}/api/upload-resume`, { method: 'POST', body: formData })
      if (!res.ok) throw new Error()
      const data = await res.json()
      // Determine reference photo — user upload takes priority, then extracted from resume
      const finalPhoto = userPhotoPreview || data.photo_base64 || null
      if (!finalPhoto) {
        setError('No photo found in your resume. Please upload your profile photo and try again.')
        setLoading(false)
        return
      }
      setSessionData({ session_id: data.session_id, candidate: data.candidate, position: data.position })
      setExtractedPhoto(data.photo_base64 || null)
      setReferencePhoto(finalPhoto)
      // If user manually uploaded → skip photo confirm, go straight to face check
      // If only extracted from resume → show confirm step first
      setPhotoMode(userPhotoPreview ? 'upload' : 'extracted')
      setVerifyPhase(userPhotoPreview ? 'facecheck' : 'photo')
      setVerifyStatus('idle')
      setLoading(false)
      setStep('verify')
    } catch {
      setError('Something went wrong. Please try again.')
      setLoading(false)
    }
  }

  const handlePhotoFileUpload = (f) => {
    if (!f || !f.type.startsWith('image/')) return
    const reader = new FileReader()
    reader.onload = (e) => setReferencePhoto(e.target.result)
    reader.readAsDataURL(f)
  }

  const runFaceCheck = async () => {
    if (!videoRef.current || !referencePhoto) return
    setVerifyStatus('checking')
    try {
      // Get descriptor from reference photo
      const refImg = refImgRef.current
      const refDesc = await getDescriptor(refImg)
      if (!refDesc) { setVerifyStatus('no_face_ref'); return }
      // Get descriptor from webcam frame
      const camDesc = await captureFromVideo(videoRef.current)
      if (!camDesc) { setVerifyStatus('no_face_cam'); return }
      const { matched } = compareDescriptors(refDesc, camDesc)
      if (matched) {
        setVerifyStatus('ok')
        // Store reference photo for interview periodic checks
        sessionStorage.setItem('referencePhoto', referencePhoto)
        setTimeout(() => {
          streamRef.current?.getTracks().forEach(t => t.stop())
          navigate(`/interview?session=${sessionData.session_id}&name=${encodeURIComponent(sessionData.candidate)}&position=${encodeURIComponent(sessionData.position)}`)
        }, 1200)
      } else {
        setVerifyStatus('fail')
      }
    } catch {
      setVerifyStatus('fail')
    }
  }

  const progress = Math.round(((loadStep + 1) / LOAD_STEPS.length) * 100)

  return (
    <>
      <style>{styles}</style>
      <div className="ap-body">

        {/* Loading Overlay */}
        {loading && (
          <div className="ap-overlay">
            <div className="ap-overlay-logo-wrap">
              <img src="/srm-logo.png" alt="SRM" className="ap-overlay-logo" />
            </div>
            <div className="ap-overlay-ring" />
            <div className="ap-overlay-text">{LOAD_STEPS[loadStep]}</div>
            <div className="ap-overlay-bar">
              <div className="ap-overlay-bar-fill" style={{ width: `${progress}%` }} />
            </div>
            <div className="ap-overlay-sub">This takes about 10–15 seconds</div>
          </div>
        )}

        {/* SRM Header */}
        <header className="ap-srm-header">
          <div className="ap-srm-header-left">
            <img src="/srm-logo.png" alt="SRM Institute of Science and Technology" className="ap-srm-logo" />
            <div className="ap-srm-divider" />
            <div className="ap-srm-title-block">
              <div className="ap-srm-dept">Department of Computer Science and Engineering</div>
              <div className="ap-srm-title">AI Mock Interview Drive</div>
            </div>
          </div>
          <div className="ap-srm-header-right">
            <span className="ap-srm-dot" />
            AI Powered
          </div>
        </header>

        {/* Stats bar */}
        <div className="ap-stats">
          <div className="ap-stat">
            <div className="ap-stat-num">4</div>
            <div className="ap-stat-label">Topics Evaluated</div>
          </div>
          <div className="ap-stat">
            <div className="ap-stat-num">~12 min</div>
            <div className="ap-stat-label">Avg Duration</div>
          </div>
          <div className="ap-stat">
            <div className="ap-stat-num">Real-time</div>
            <div className="ap-stat-label">Adaptive Questions</div>
          </div>
        </div>

        {/* Form */}
        {step === 'form' && (
          <div className="ap-main">
            <form className="ap-card" onSubmit={handleSubmit}>
              <div className="ap-card-title">Application Form</div>

              <div className="ap-field">
                <label>Full Name</label>
                <input type="text" placeholder="e.g. Mano Prasanna" required
                  value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} />
              </div>

              <div className="ap-field">
                <label>Email Address</label>
                <input type="email" placeholder="you@srmist.edu.in" required
                  value={form.email} onChange={e => setForm(f => ({ ...f, email: e.target.value }))} />
              </div>

              <div className="ap-field">
                <label>Position Applied For</label>
                <select required value={form.position} onChange={e => setForm(f => ({ ...f, position: e.target.value }))}>
                  <option value="">Select a role</option>
                  {POSITIONS.map(p => <option key={p} value={p}>{p}</option>)}
                </select>
              </div>

              <div className="ap-field">
                <label>Resume (PDF or DOCX)</label>
                <div
                  className={`ap-drop${dragging ? ' dragging' : file ? ' has-file' : ''}`}
                  onClick={() => fileRef.current?.click()}
                  onDragOver={e => { e.preventDefault(); setDragging(true) }}
                  onDragLeave={() => setDragging(false)}
                  onDrop={handleDrop}
                >
                  <input ref={fileRef} type="file" accept=".pdf,.docx,.doc" style={{ display: 'none' }}
                    onChange={e => handleFile(e.target.files[0])} />
                  <div className="ap-drop-icon">{file ? '✅' : '📄'}</div>
                  {file
                    ? <div className="ap-drop-file">{file.name}</div>
                    : <div className="ap-drop-text">Drop your resume here or <strong>browse</strong></div>
                  }
                </div>
              </div>

            <div className="ap-field">
                <label>
                  Profile Photo&nbsp;
                  {!userPhotoPreview && <span className="ap-photo-required-tag">Required if not in resume</span>}
                </label>
                <div className="ap-photo-row" onClick={() => photoFileRef.current?.click()}>
                  <input ref={photoFileRef} type="file" accept="image/*" style={{ display: 'none' }}
                    onChange={e => {
                      const f = e.target.files[0]
                      if (!f) return
                      const reader = new FileReader()
                      reader.onload = ev => setUserPhotoPreview(ev.target.result)
                      reader.readAsDataURL(f)
                    }} />
                  {userPhotoPreview
                    ? <img src={userPhotoPreview} className="ap-photo-mini-img" alt="Your photo" />
                    : <div className="ap-photo-mini-icon">📷</div>
                  }
                  <div>
                    <div className="ap-photo-mini-text">
                      {userPhotoPreview ? 'Photo selected — click to change' : 'Upload your photo'}
                    </div>
                    <div className="ap-photo-mini-sub">
                      {userPhotoPreview
                        ? 'Clear, front-facing photo'
                        : 'Leave blank if your resume PDF includes a photo — we\'ll extract it automatically'
                      }
                    </div>
                  </div>
                </div>
              </div>

              {error && <div className="ap-error">{error}</div>}

              <button className="ap-btn" type="submit" disabled={loading}>
                {loading
                  ? <><div className="ap-btn-spin" /> Analysing...</>
                  : 'Analyse Resume →'
                }
              </button>

              <div className="ap-note">
                Your resume is processed locally for this session and not stored permanently.
              </div>
            </form>
          </div>
        )}

        {/* Verify Step */}
        {step === 'verify' && (
          <div className="ap-verify-wrap">
            <div className="ap-verify-card">
              <div className="ap-verify-title">
                {verifyPhase === 'photo' ? 'Step 2 — Confirm Your Identity Photo' : 'Step 3 — Live Face Verification'}
              </div>

              {/* ── PHOTO PHASE ── */}
              {verifyPhase === 'photo' && (
                <>
                  {photoMode === 'extracted' && extractedPhoto ? (
                    <>
                      <div style={{ fontSize: '0.85rem', color: '#374151', lineHeight: 1.5 }}>
                        We found a photo in your resume. Please confirm this is you before we begin the interview.
                      </div>
                      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '0.75rem' }}>
                        <img src={extractedPhoto} alt="Resume photo" className="ap-verify-photo"
                          style={{ width: 140, height: 180 }} />
                        <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap', justifyContent: 'center' }}>
                          <button className="ap-btn" style={{ padding: '0.5rem 1.5rem', fontSize: '0.85rem' }}
                            onClick={() => setVerifyPhase('facecheck')}>
                            Yes, that's me
                          </button>
                          <button className="ap-btn" style={{ padding: '0.5rem 1.25rem', fontSize: '0.85rem', background: '#e8edf5', color: '#1a237e' }}
                            onClick={() => { setPhotoMode('upload'); setReferencePhoto(null) }}>
                            No, upload different
                          </button>
                        </div>
                      </div>
                    </>
                  ) : (
                    <>
                      <div style={{ fontSize: '0.85rem', color: '#374151', lineHeight: 1.5 }}>
                        {photoMode === 'extracted'
                          ? 'No photo found in your resume.'
                          : 'Please upload a clear front-facing photo of yourself.'}&nbsp;
                        <strong>This is required for identity verification.</strong>
                      </div>
                      <input ref={photoFileRef} type="file" accept="image/*" style={{ display: 'none' }}
                        onChange={e => handlePhotoFileUpload(e.target.files[0])} />
                      <div className="ap-photo-upload-area" onClick={() => photoFileRef.current?.click()}>
                        {referencePhoto
                          ? <>
                            <img src={referencePhoto} className="ap-photo-upload-preview" alt="Your photo" />
                            <div style={{ fontSize: '0.78rem', color: '#6b7a8d' }}>Click to change</div>
                          </>
                          : <>
                            <div style={{ fontSize: '2rem', marginBottom: '0.5rem' }}>📷</div>
                            <div style={{ fontSize: '0.85rem', color: '#374151' }}>Click to upload your photo</div>
                            <div style={{ fontSize: '0.75rem', color: '#6b7a8d', marginTop: '0.25rem' }}>JPG, PNG — clear face, good lighting</div>
                          </>
                        }
                      </div>
                      {referencePhoto && (
                        <button className="ap-btn" onClick={() => setVerifyPhase('facecheck')}>
                          Continue to Verification →
                        </button>
                      )}
                      {extractedPhoto && (
                        <div style={{ textAlign: 'center' }}>
                          <button className="ap-link-btn" onClick={() => { setPhotoMode('extracted'); setReferencePhoto(extractedPhoto) }}>
                            ← Use photo from resume instead
                          </button>
                        </div>
                      )}
                    </>
                  )}
                </>
              )}

              {/* ── FACECHECK PHASE ── */}
              {verifyPhase === 'facecheck' && (
                <>
                  <div className="ap-verify-panels">
                    <div className="ap-verify-panel">
                      <div className="ap-verify-panel-label">Your Reference Photo</div>
                      {referencePhoto
                        ? <img ref={refImgRef} src={referencePhoto} className="ap-verify-photo" alt="Reference" crossOrigin="anonymous" />
                        : <div className="ap-verify-placeholder">No photo</div>
                      }
                    </div>
                    <div className="ap-verify-panel">
                      <div className="ap-verify-panel-label">Live Camera</div>
                      {verifyStatus === 'loading' || verifyStatus === 'idle'
                        ? <div className="ap-verify-placeholder"><div className="ap-btn-spin" style={{ width: 28, height: 28, borderWidth: 3 }} /><div style={{ marginTop: 8 }}>Starting camera...</div></div>
                        : <video ref={videoRef} autoPlay muted playsInline className="ap-verify-video" />
                      }
                    </div>
                  </div>

                  {/* Status */}
                  {verifyStatus === 'loading' && (
                    <div className="ap-verify-status loading">Loading face recognition models...</div>
                  )}
                  {verifyStatus === 'ready' && (
                    <div className="ap-verify-status loading">Camera ready. Look directly at the camera and click Verify.</div>
                  )}
                  {verifyStatus === 'checking' && (
                    <div className="ap-verify-status loading">Verifying identity...</div>
                  )}
                  {verifyStatus === 'ok' && (
                    <div className="ap-verify-status ok">Identity verified. Starting interview...</div>
                  )}
                  {verifyStatus === 'fail' && (
                    <div className="ap-verify-status fail">Face does not match. Please ensure you are well-lit and looking at the camera, then try again.</div>
                  )}
                  {verifyStatus === 'no_face_ref' && (
                    <div className="ap-verify-status warn">Could not detect a face in your reference photo. Please go back and upload a clearer photo.</div>
                  )}
                  {verifyStatus === 'no_face_cam' && (
                    <div className="ap-verify-status warn">No face detected in camera. Ensure good lighting and look directly at the camera.</div>
                  )}
                  {verifyStatus === 'cam_err' && (
                    <div className="ap-verify-status fail">Camera access denied. Please allow camera permission and refresh.</div>
                  )}

                  <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
                    {(verifyStatus === 'ready' || verifyStatus === 'fail' || verifyStatus === 'no_face_cam') && (
                      <button className="ap-btn" onClick={runFaceCheck}>
                        Verify Identity
                      </button>
                    )}
                    {(verifyStatus === 'no_face_ref' || verifyStatus === 'cam_err') && (
                      <button className="ap-btn" style={{ background: '#e8edf5', color: '#1a237e' }}
                        onClick={() => setVerifyPhase('photo')}>
                        ← Back to Photo
                      </button>
                    )}
                    {(verifyStatus === 'fail' || verifyStatus === 'no_face_cam') && (
                      <button className="ap-btn" style={{ background: '#e8edf5', color: '#1a237e', padding: '0.5rem 1rem', fontSize: '0.82rem' }}
                        onClick={() => setVerifyPhase('photo')}>
                        Change Photo
                      </button>
                    )}
                  </div>
                </>
              )}
            </div>
          </div>
        )}
      </div>
    </>
  )
}
