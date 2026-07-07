export default function AudioVisualizer({ volumeLevel, status }) {
  const bars = 12
  const isActive = status === 'listening'

  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 4, height: 48 }}>
      {Array.from({ length: bars }).map((_, i) => {
        const base = 4
        const noise = isActive ? Math.random() * volumeLevel * 2 : 0
        const height = Math.min(48, base + noise + Math.sin(Date.now() / 200 + i) * (isActive ? 6 : 2))
        return (
          <div
            key={i}
            style={{
              width: 3,
              height: `${height}px`,
              borderRadius: 3,
              background: status === 'speaking'
                ? `rgba(59, 130, 246, ${0.4 + (i / bars) * 0.6})`
                : status === 'listening'
                ? `rgba(16, 185, 129, ${0.4 + (i / bars) * 0.6})`
                : 'rgba(100,116,139,0.4)',
              transition: 'height 0.05s ease'
            }}
          />
        )
      })}
    </div>
  )
}
