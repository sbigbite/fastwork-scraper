export const DEFAULT_KEYWORDS = [
  'BOQ', 'AutoCAD', 'drawing',
  'ออกแบบบ้าน', 'โครงสร้าง', 'วิศวกร',
]

export function rescoreJobs(jobs, keywords) {
  if (!jobs?.length) return []
  const kws = keywords.filter(Boolean)

  return jobs
    .map(job => {
      if (!kws.length) {
        return { ...job, match_percentage: 0, matched_keywords: [] }
      }
      const text = `${job.title ?? ''} ${job.description ?? ''}`.toLowerCase()
      const matched = kws.filter(kw => text.includes(kw.toLowerCase()))
      const pct = Math.round((matched.length / kws.length) * 1000) / 10
      return { ...job, match_percentage: pct, matched_keywords: matched }
    })
    .sort((a, b) => b.match_percentage - a.match_percentage)
}

export function matchLevel(pct) {
  if (pct >= 50) return 'high'
  if (pct >= 20) return 'medium'
  if (pct >= 1)  return 'low'
  return 'none'
}

export function matchColor(pct) {
  if (pct >= 50) return 'var(--c-high)'
  if (pct >= 20) return 'var(--c-medium)'
  if (pct >= 1)  return 'var(--c-low)'
  return 'var(--c-none)'
}

export function formatTime(raw) {
  if (!raw || raw === 'ไม่ระบุ') return 'ไม่ระบุ'
  const d = new Date(raw)
  if (isNaN(d)) return raw
  const days = Math.floor((Date.now() - d) / 86_400_000)
  if (days === 0) return 'วันนี้'
  if (days === 1) return 'เมื่อวาน'
  if (days < 7)  return `${days} วันที่แล้ว`
  if (days < 30) return `${Math.floor(days / 7)} สัปดาห์ที่แล้ว`
  return d.toLocaleDateString('th-TH', { day: 'numeric', month: 'short', year: 'numeric' })
}
