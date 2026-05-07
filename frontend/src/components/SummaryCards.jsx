export default function SummaryCards({ jobs, source }) {
  const total    = jobs.length
  const matched  = jobs.filter(j => j.match_percentage > 0).length
  const high     = jobs.filter(j => j.match_percentage >= 50).length
  const topScore = jobs.length ? Math.round(jobs[0].match_percentage) : 0

  const cards = [
    {
      label: 'งานทั้งหมด',
      value: total,
      sub: `แหล่ง: ${source === 'api' ? 'JSON API' : 'HTML scrape'}`,
      accent: 'var(--c-accent)',
      icon: '📋',
    },
    {
      label: 'ตรงคีย์เวิร์ด',
      value: matched,
      sub: `${total ? Math.round((matched / total) * 100) : 0}% ของงานทั้งหมด`,
      accent: 'var(--c-medium)',
      icon: '🔍',
    },
    {
      label: 'Match สูง ≥50%',
      value: high,
      sub: `Top score: ${topScore}%`,
      accent: 'var(--c-high)',
      icon: '🏆',
    },
  ]

  return (
    <div className="summary-cards">
      {cards.map(c => (
        <div key={c.label} className="summary-card" style={{ '--card-accent': c.accent }}>
          <span className="summary-icon">{c.icon}</span>
          <div className="summary-body">
            <div className="summary-value" style={{ color: c.accent }}>{c.value}</div>
            <div className="summary-label">{c.label}</div>
            <div className="summary-sub">{c.sub}</div>
          </div>
        </div>
      ))}
    </div>
  )
}
