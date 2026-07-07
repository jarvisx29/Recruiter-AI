import { useRef, useState, useCallback, useEffect } from 'react'
import { RetellWebClient } from 'retell-client-js-sdk'
import { BACKEND } from '../config'

export function useInterview(sessionId) {
  const clientRef = useRef(null)

  const [status, setStatus] = useState('idle') // idle | connecting | agent_talking | user_talking | processing | done | error
  const [transcript, setTranscript] = useState([])
  const [topicInfo, setTopicInfo] = useState({ topic: '', depth: 1, score: 0, done: 0, total: 4 })
  const [results, setResults] = useState(null)
  const [error, setError] = useState('')

  const connect = useCallback(async () => {
    setStatus('connecting')
    setError('')

    try {
      // Get Retell access token from our backend
      const res = await fetch(`${BACKEND}/api/start-interview/${sessionId}`, { method: 'POST' })
      if (!res.ok) throw new Error('Failed to start interview session')
      const { access_token, call_id } = await res.json()

      const client = new RetellWebClient()
      clientRef.current = client

      client.on('call_started', () => setStatus('agent_talking'))
      client.on('call_ended', async () => {
        setStatus('done')
        // Fetch final results from backend
        try {
          const r = await fetch(`${BACKEND}/api/results/${sessionId}`)
          if (r.ok) setResults(await r.json())
        } catch { /* results may not be ready */ }
      })

      client.on('agent_start_talking', () => setStatus('agent_talking'))
      client.on('agent_stop_talking', () => setStatus('user_talking'))

      client.on('update', (update) => {
        if (update.transcript) {
          setTranscript(update.transcript.map(t => ({
            role: t.role === 'agent' ? 'ai' : 'candidate',
            text: t.content
          })))
        }
      })

      client.on('error', (err) => {
        setError(err?.message || 'Call error')
        setStatus('error')
      })

      await client.startCall({ accessToken: access_token })

    } catch (err) {
      setError(err.message || 'Failed to connect')
      setStatus('error')
    }
  }, [sessionId])

  const endCall = useCallback(() => {
    clientRef.current?.stopCall()
  }, [])

  useEffect(() => {
    return () => { clientRef.current?.stopCall() }
  }, [])

  return { connect, endCall, status, transcript, topicInfo, results, error }
}
