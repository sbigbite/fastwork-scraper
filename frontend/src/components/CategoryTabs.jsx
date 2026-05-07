const TABS = [
  { id: 'all',    label: 'ทั้งหมด',       min: -1,  max: 101 },
  { id: 'high',   label: 'สูง ≥50%',      min: 50,  max: 101 },
  { id: 'medium', label: 'กลาง 20–49%',   min: 20,  max: 49.9 },
  { id: 'low',    label: 'ต่ำ 1–19%',     min: 1,   max: 19.9 },
  { id: 'none',   label: 'ไม่ตรง',         min: -1,  max: 0.9 },
]

export default function CategoryTabs({ jobs, active, onChange }) {
  function countFor(tab) {
    if (tab.id === 'all') return jobs.length
    return jobs.filter(j => j.match_percentage >= tab.min && j.match_percentage <= tab.max).length
  }

  return (
    <div className="cat-tabs" role="tablist">
      {TABS.map(tab => {
        const count = countFor(tab)
        return (
          <button
            key={tab.id}
            role="tab"
            aria-selected={active === tab.id}
            className={`cat-tab ${active === tab.id ? 'cat-tab--active' : ''}`}
            onClick={() => onChange(tab.id)}
          >
            {tab.label}
            <span className="cat-badge">{count}</span>
          </button>
        )
      })}
    </div>
  )
}

export function filterByTab(jobs, tabId) {
  const tab = TABS.find(t => t.id === tabId)
  if (!tab || tabId === 'all') return jobs
  return jobs.filter(j => j.match_percentage >= tab.min && j.match_percentage <= tab.max)
}
