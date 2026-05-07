import { useState, useCallback } from 'react'
import { fetchJobs } from './api/client'
import { DEFAULT_KEYWORDS, rescoreJobs } from './utils/matcher'
import KeywordInput from './components/KeywordInput'
import SummaryCards from './components/SummaryCards'
import CategoryTabs, { filterByTab } from './components/CategoryTabs'
import JobCard from './components/JobCard'

export default function App() {
  const [keywords, setKeywords]   = useState([...DEFAULT_KEYWORDS])
  const [rawJobs, setRawJobs]     = useState([])
  const [jobs, setJobs]           = useState([])
  const [source, setSource]       = useState('')
  const [activeTab, setActiveTab] = useState('all')
  const [loading, setLoading]     = useState(false)
  const [error, setError]         = useState(null)
  const [scraped, setScraped]     = useState(false)

  // Re-score whenever keywords change after first scrape
  const applyKeywords = useCallback((kws, raw) => {
    const scored = rescoreJobs(raw, kws)
    setJobs(scored)
  }, [])

  function handleKeywordsChange(kws) {
    setKeywords(kws)
    if (scraped) applyKeywords(kws, rawJobs)
  }

  async function handleScrape() {
    if (loading) return
    setLoading(true)
    setError(null)

    try {
      const data = await fetchJobs({ perPage: 100 })
      const raw  = data.jobs ?? []
      setRawJobs(raw)
      setSource(data.source ?? '')
      applyKeywords(keywords, raw)
      setScraped(true)
      setActiveTab('all')
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const visible = filterByTab(jobs, activeTab)

  return (
    <div className="app">
      {/* ── Header ── */}
      <header className="app-header">
        <div className="header-inner">
          <div className="header-brand">
            <span className="header-icon">🏗️</span>
            <div>
              <h1 className="header-title">FastWork Civil Finder</h1>
              <p className="header-sub">ค้นหางานวิศวกรรมโยธาจาก FastWork</p>
            </div>
          </div>
        </div>
      </header>

      {/* ── Search panel ── */}
      <main className="app-main">
        <section className="search-panel">
          <KeywordInput keywords={keywords} onChange={handleKeywordsChange} />

          <button
            type="button"
            className={`btn-scrape ${loading ? 'btn-scrape--loading' : ''}`}
            onClick={handleScrape}
            disabled={loading || keywords.length === 0}
          >
            {loading ? (
              <>
                <span className="spinner" aria-hidden="true" />
                กำลังดึงข้อมูล…
              </>
            ) : (
              <>🔎 ค้นหางาน</>
            )}
          </button>

          {error && (
            <div className="error-banner" role="alert">
              <strong>เกิดข้อผิดพลาด:</strong> {error}
              <br />
              <small>ตรวจสอบว่า Flask backend รันอยู่ที่ <code>localhost:5000</code></small>
            </div>
          )}
        </section>

        {/* ── Results ── */}
        {scraped && !loading && (
          <section className="results-panel">
            <SummaryCards jobs={jobs} source={source} />

            <div className="results-filter-row">
              <CategoryTabs jobs={jobs} active={activeTab} onChange={setActiveTab} />
              <span className="results-count">
                แสดง {visible.length} รายการ
              </span>
            </div>

            {visible.length === 0 ? (
              <div className="empty-state">
                <span className="empty-icon">🔍</span>
                <p>ไม่พบงานในหมวดนี้</p>
              </div>
            ) : (
              <div className="job-list">
                {visible.map((job, i) => (
                  <JobCard key={job.job_url || i} job={job} />
                ))}
              </div>
            )}
          </section>
        )}

        {/* ── Empty / landing state ── */}
        {!scraped && !loading && (
          <div className="landing-state">
            <div className="landing-icon">🏗️</div>
            <h2 className="landing-title">พร้อมค้นหางานวิศวกรรมโยธา</h2>
            <p className="landing-body">
              กด <strong>ค้นหางาน</strong> เพื่อดึงรายการงานจาก FastWork
              และกรองตามคีย์เวิร์ดที่เลือก
            </p>
          </div>
        )}
      </main>
    </div>
  )
}
