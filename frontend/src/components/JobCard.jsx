import { useState } from 'react'
import { matchColor, matchLevel, formatTime } from '../utils/matcher'

function MatchBar({ pct }) {
  const color = matchColor(pct)
  const level = matchLevel(pct)
  const labels = { high: 'สูง', medium: 'กลาง', low: 'ต่ำ', none: 'ไม่ตรง' }

  return (
    <div className="match-bar-wrap">
      <div className="match-bar-row">
        <span className="match-bar-label">Match</span>
        <span className="match-bar-pct" style={{ color }}>
          {pct.toFixed(1)}%
          <span className={`match-badge match-badge--${level}`}>{labels[level]}</span>
        </span>
      </div>
      <div className="match-bar-track">
        <div
          className="match-bar-fill"
          style={{ width: `${Math.min(pct, 100)}%`, background: color }}
        />
      </div>
    </div>
  )
}

export default function JobCard({ job }) {
  const [expanded, setExpanded] = useState(false)

  const hasDesc   = job.description && job.description.trim().length > 0
  const shortDesc = hasDesc ? job.description.slice(0, 160) : null
  const isLong    = hasDesc && job.description.length > 160

  return (
    <article className={`job-card ${expanded ? 'job-card--open' : ''}`}>
      {/* Header row */}
      <div className="job-card-header">
        <div className="job-card-title-wrap">
          <h3 className="job-card-title">{job.title || 'ไม่มีชื่อ'}</h3>
          <div className="job-card-meta">
            <span className="job-meta-chip job-meta-chip--budget">
              💰 {job.budget || 'ไม่ระบุ'}
            </span>
            <span className="job-meta-chip">
              🕐 {formatTime(job.posted_time)}
            </span>
          </div>
        </div>
      </div>

      {/* Match bar */}
      <MatchBar pct={job.match_percentage} />

      {/* Matched keywords */}
      {job.matched_keywords?.length > 0 && (
        <div className="job-keywords">
          <span className="job-keywords-label">ตรงกับ:</span>
          {job.matched_keywords.map(kw => (
            <span key={kw} className="kw-match-tag">{kw}</span>
          ))}
        </div>
      )}

      {/* Expandable description */}
      {hasDesc && (
        <div className="job-desc-wrap">
          <p className="job-desc">
            {expanded || !isLong ? job.description : `${shortDesc}…`}
          </p>
          {isLong && (
            <button
              type="button"
              className="btn-ghost btn-xs job-expand-btn"
              onClick={() => setExpanded(v => !v)}
            >
              {expanded ? '▲ ย่อลง' : '▼ ดูเพิ่มเติม'}
            </button>
          )}
        </div>
      )}

      {/* Footer */}
      <div className="job-card-footer">
        <a
          href={job.job_url || '#'}
          target="_blank"
          rel="noopener noreferrer"
          className={`btn-primary ${!job.job_url ? 'btn-disabled' : ''}`}
          onClick={e => !job.job_url && e.preventDefault()}
        >
          ดูงานบน FastWork ↗
        </a>
      </div>
    </article>
  )
}
