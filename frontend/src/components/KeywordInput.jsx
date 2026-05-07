import { useState, useRef } from 'react'
import { DEFAULT_KEYWORDS } from '../utils/matcher'

export default function KeywordInput({ keywords, onChange }) {
  const [draft, setDraft] = useState('')
  const inputRef = useRef(null)

  function addKeyword(raw) {
    const kw = raw.trim()
    if (!kw || keywords.includes(kw)) return
    onChange([...keywords, kw])
    setDraft('')
  }

  function removeKeyword(kw) {
    onChange(keywords.filter(k => k !== kw))
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter' || e.key === ',') {
      e.preventDefault()
      addKeyword(draft)
    } else if (e.key === 'Backspace' && draft === '' && keywords.length) {
      onChange(keywords.slice(0, -1))
    }
  }

  function handleReset() {
    onChange([...DEFAULT_KEYWORDS])
    setDraft('')
    inputRef.current?.focus()
  }

  return (
    <div className="keyword-input-wrap">
      <div className="keyword-label">
        <span>คีย์เวิร์ด</span>
        <button
          type="button"
          className="btn-ghost btn-xs"
          onClick={handleReset}
          title="Reset to defaults"
        >
          รีเซ็ต
        </button>
      </div>

      <div
        className="keyword-tag-box"
        onClick={() => inputRef.current?.focus()}
      >
        {keywords.map(kw => (
          <span key={kw} className="kw-tag">
            {kw}
            <button
              type="button"
              className="kw-remove"
              onClick={e => { e.stopPropagation(); removeKeyword(kw) }}
              aria-label={`Remove ${kw}`}
            >
              ×
            </button>
          </span>
        ))}

        <input
          ref={inputRef}
          className="kw-input"
          value={draft}
          placeholder={keywords.length ? '' : 'พิมพ์คีย์เวิร์ด แล้วกด Enter…'}
          onChange={e => setDraft(e.target.value)}
          onKeyDown={handleKeyDown}
          onBlur={() => draft.trim() && addKeyword(draft)}
        />
      </div>

      <p className="keyword-hint">กด Enter หรือ , เพื่อเพิ่ม · Backspace เพื่อลบ</p>
    </div>
  )
}
