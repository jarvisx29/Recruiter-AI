import { useRef, useState, useCallback, useEffect } from 'react'
import { BACKEND, BACKEND_WS } from '../config'

// Linear interpolation resampler — handles mismatch between TTS rate and AudioContext rate
function resample(int16Buffer, fromRate, toRate) {
  const input = new Int16Array(int16Buffer)
  if (fromRate === toRate) {
    const out = new Float32Array(input.length)
    for (let i = 0; i < input.length; i++) out[i] = input[i] / 32768
    return out
  }
  const ratio = toRate / fromRate
  const outputLen = Math.round(input.length * ratio)
  const out = new Float32Array(outputLen)
  for (let i = 0; i < outputLen; i++) {
    const src = i / ratio
    const lo = Math.floor(src)
    const hi = Math.min(lo + 1, input.length - 1)
    const frac = src - lo
    const sample = input[lo] * (1 - frac) + input[hi] * frac
    out[i] = sample / 32768
  }
  return out
}

export function useDeepgramInterview(sessionId) {
  const wsRef = useRef(null)

  // Capture (mic → Deepgram): 16 kHz
  const captureCtxRef = useRef(null)
  const processorRef = useRef(null)
  const sourceRef = useRef(null)
  const silentGainRef = useRef(null)
  const streamRef = useRef(null)
  const micMutedRef = useRef(false) // always on — echo cancellation handles feedback

  // Playback (TTS PCM → speakers)
  const playbackCtxRef = useRef(null)
  const outputProcessorRef = useRef(null)
  const pcmQueueRef = useRef([])   // Float32Array chunks
  const ttsRateRef = useRef(24000) // set from audio_start message

  const [status, setStatus] = useState('idle')
  const [transcript, setTranscript] = useState([])
  const [interimText, setInterimText] = useState('')
  const [results, setResults] = useState(null)
  const [error, setError] = useState('')

  // ── cleanup ──────────────────────────────────────────────────────────────

  const cleanup = useCallback(() => {
    try {
      processorRef.current?.disconnect()
      sourceRef.current?.disconnect()
      silentGainRef.current?.disconnect()
      outputProcessorRef.current?.disconnect()
      streamRef.current?.getTracks().forEach(t => t.stop())
      if (captureCtxRef.current?.state !== 'closed') captureCtxRef.current?.close()
      if (playbackCtxRef.current?.state !== 'closed') playbackCtxRef.current?.close()
    } catch {}
    pcmQueueRef.current = []
  }, [])

  // ── PCM playback setup ────────────────────────────────────────────────────

  const setupPlayback = useCallback((ttsRate) => {
    ttsRateRef.current = ttsRate

    // Try to create playback context at TTS rate so no resampling needed
    let pbCtx
    try { pbCtx = new AudioContext({ sampleRate: ttsRate }) }
    catch  { pbCtx = new AudioContext() }
    playbackCtxRef.current = pbCtx

    // ScriptProcessor drains pcmQueue into speakers
    const outputProc = pbCtx.createScriptProcessor(2048, 0, 1)
    outputProcessorRef.current = outputProc

    outputProc.onaudioprocess = (e) => {
      const output = e.outputBuffer.getChannelData(0)
      let pos = 0
      const queue = pcmQueueRef.current
      while (pos < output.length && queue.length > 0) {
        const chunk = queue[0]
        const need = output.length - pos
        if (chunk.length <= need) {
          output.set(chunk, pos)
          pos += chunk.length
          queue.shift()
        } else {
          output.set(chunk.subarray(0, need), pos)
          queue[0] = chunk.subarray(need)
          pos = output.length
        }
      }
      // Silence for any unfilled frames
      for (; pos < output.length; pos++) output[pos] = 0
    }

    outputProc.connect(pbCtx.destination)
  }, [])

  // ── connect ───────────────────────────────────────────────────────────────

  const connect = useCallback(async () => {
    setStatus('connecting')
    setError('')

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true },
      })
      streamRef.current = stream

      // Capture context at 16 kHz for Deepgram
      const captureCtx = new AudioContext({ sampleRate: 16000 })
      captureCtxRef.current = captureCtx

      const ws = new WebSocket(`${BACKEND_WS}/ws/deepgram/${sessionId}`)
      ws.binaryType = 'arraybuffer'
      wsRef.current = ws

      const source = captureCtx.createMediaStreamSource(stream)
      sourceRef.current = source
      const processor = captureCtx.createScriptProcessor(4096, 1, 1)
      processorRef.current = processor
      const silentGain = captureCtx.createGain()
      silentGain.gain.value = 0
      silentGainRef.current = silentGain

      // Send mic PCM to server
      processor.onaudioprocess = (e) => {
        if (ws.readyState !== WebSocket.OPEN || micMutedRef.current) return
        const f32 = e.inputBuffer.getChannelData(0)
        const i16 = new Int16Array(f32.length)
        for (let i = 0; i < f32.length; i++) {
          const s = Math.max(-1, Math.min(1, f32[i]))
          i16[i] = s < 0 ? s * 0x8000 : s * 0x7fff
        }
        ws.send(i16.buffer)
      }

      source.connect(processor)
      processor.connect(silentGain)
      silentGain.connect(captureCtx.destination)

      // ── WebSocket message handler ─────────────────────────────────────────

      ws.onmessage = async (event) => {
        // Binary = raw PCM chunk from TTS — add to play queue immediately
        if (event.data instanceof ArrayBuffer) {
          const pbCtx = playbackCtxRef.current
          if (!pbCtx) return
          const float32 = resample(event.data, ttsRateRef.current, pbCtx.sampleRate)
          pcmQueueRef.current.push(float32)
          return
        }

        let msg
        try { msg = JSON.parse(event.data) } catch { return }

        switch (msg.type) {

          case 'audio_start':
            pcmQueueRef.current = []
            if (!playbackCtxRef.current) {
              setupPlayback(msg.sampleRate || 24000)
            } else {
              // Resume if suspended (browser autoplay policy)
              if (playbackCtxRef.current.state === 'suspended') {
                await playbackCtxRef.current.resume()
              }
              ttsRateRef.current = msg.sampleRate || 24000
              pcmQueueRef.current = []
            }
            break

          case 'audio_end':
            break

          case 'clear_audio':
            // Barge-in: user interrupted — wipe the playback queue immediately
            pcmQueueRef.current = []
            break

          case 'agent_start_talking':
            setStatus('agent_talking')
            break

          case 'agent_stop_talking':
            setStatus('user_talking')
            break

          case 'user_turn':
            micMutedRef.current = false
            setStatus('user_talking')
            setInterimText('')
            break

          case 'mute_mic':
            // kept for protocol compatibility — not muting anymore (echo cancellation handles it)
            break

          case 'unmute_mic':
            break

          case 'processing':
            setStatus('processing')
            break

          case 'interim':
            setInterimText(msg.text)
            break

          case 'transcript':
            setInterimText('')
            setTranscript(prev => [...prev, { role: msg.role, text: msg.text }])
            break

          case 'interview_complete':
            setStatus('done')
            // Retry a few times — WS close and result finalisation can race
            ;(async () => {
              for (let i = 0; i < 5; i++) {
                await new Promise(r => setTimeout(r, 800))
                try {
                  const r = await fetch(`${BACKEND}/api/results/${sessionId}`)
                  if (r.ok) { setResults(await r.json()); break }
                } catch {}
              }
            })()
            break

          case 'error':
            setError(msg.message || 'An error occurred.')
            setStatus('error')
            break

          default: break
        }
      }

      ws.onopen = () => {
        setStatus('agent_talking') // server immediately starts generating opening
      }

      ws.onerror = () => {
        setError('Connection failed. Check your network and try again.')
        setStatus('error')
      }

      ws.onclose = () => {
        setStatus(prev => (prev === 'done' || prev === 'error') ? prev : 'done')
        cleanup()
      }

    } catch (err) {
      setError(
        err.name === 'NotAllowedError'
          ? 'Microphone access denied. Allow mic permission and reload.'
          : err.message || 'Failed to connect.'
      )
      setStatus('error')
    }
  }, [sessionId, cleanup, setupPlayback])

  const endCall = useCallback(() => {
    wsRef.current?.close()
    cleanup()
    setStatus('done')
  }, [cleanup])

  useEffect(() => {
    return () => {
      wsRef.current?.close()
      cleanup()
    }
  }, [cleanup])

  return { connect, endCall, status, transcript, interimText, results, error }
}
