// In dev: empty string → Vite proxy forwards /api → localhost:5000
// In prod: Render injects VITE_API_URL as a bare hostname (e.g. "fastwork-scraper-api.onrender.com")
//          or a full URL — normalise to https:// either way.
const _raw = import.meta.env.VITE_API_URL ?? ''
const BASE = _raw
  ? (_raw.startsWith('http') ? _raw.replace(/\/$/, '') : `https://${_raw}`)
  : ''

async function request(path, params = {}) {
  const qs = new URLSearchParams(params).toString()
  const url = `${BASE}${path}${qs ? `?${qs}` : ''}`
  const res = await fetch(url)
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText)
    throw new Error(`${res.status} – ${text}`)
  }
  return res.json()
}

export function fetchJobs({ page = 1, perPage = 100 } = {}) {
  return request('/api/jobs', { min_match: 0, page, per_page: perPage })
}

export function fetchHealth() {
  return request('/health')
}
