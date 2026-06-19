import React, { useState } from 'react';
import { TASTE_DATA, CATEGORY_LABELS, TAG_EMOJI } from '../../lib/tasteData';
import './TasteOnboarding.css';

const STEPS = ['book', 'movie', 'drama'];
const SELECT_COUNT = 3;

function PosterCard({ item, selected, onToggle, disabled }) {
  const [imgFailed, setImgFailed] = useState(false);

  return (
    <div
      className={`to-card${selected ? ' to-card--selected' : ''}${disabled ? ' to-card--disabled' : ''}`}
      onClick={!disabled || selected ? onToggle : undefined}
    >
      {item.img && !imgFailed ? (
        <img
          src={item.img}
          alt={item.title}
          className="to-card__img"
          onError={() => setImgFailed(true)}
        />
      ) : (
        <div
          className="to-card__fallback"
          style={{ background: `linear-gradient(155deg, ${item.color ?? '#2a2a2a'} 0%, #111 100%)` }}
        >
          <span className="to-card__fallback-icon">
            {TAG_EMOJI[item.tags?.[0]] ?? '📖'}
          </span>
          <span className="to-card__fallback-title">{item.title}</span>
        </div>
      )}
      <div className="to-card__gradient" />
      <span className="to-card__title">{item.title}</span>
      {selected && <div className="to-card__check">✓</div>}
    </div>
  );
}

export default function TasteOnboarding({ onComplete, onClose }) {
  const [stepIdx, setStepIdx] = useState(0);
  const [selections, setSelections] = useState({ book: [], movie: [], drama: [] });
  const [submitting, setSubmitting] = useState(false);

  const step = STEPS[stepIdx];
  const selected = selections[step];
  const isLast = stepIdx === STEPS.length - 1;
  const canProceed = selected.length === SELECT_COUNT;

  function toggle(id) {
    setSelections(prev => {
      const cur = prev[step];
      if (cur.includes(id)) return { ...prev, [step]: cur.filter(x => x !== id) };
      if (cur.length >= SELECT_COUNT) return prev;
      return { ...prev, [step]: [...cur, id] };
    });
  }

  async function handleNext() {
    if (!canProceed) return;
    if (!isLast) { setStepIdx(s => s + 1); return; }
    setSubmitting(true);
    const allSelected = STEPS.flatMap(s =>
      selections[s].map(id => {
        const item = TASTE_DATA[s].find(x => x.id === id);
        return item ? { id, title: item.title, category: s, tags: item.tags } : null;
      }).filter(Boolean)
    );
    await onComplete(allSelected);
    setSubmitting(false);
  }

  return (
    <div className="to-overlay" onClick={onClose}>
      <div className="to-modal" onClick={e => e.stopPropagation()}>
        <button className="to-close" onClick={onClose}>×</button>

        {/* 헤더 */}
        <div className="to-header">
          <h2 className="to-title">취향을 알려주세요</h2>
          <div className="to-steps">
            {STEPS.map((s, i) => (
              <span
                key={s}
                className={`to-step${i < stepIdx ? ' to-step--done' : ''}${i === stepIdx ? ' to-step--active' : ''}`}
              >
                {i < stepIdx ? '✓ ' : ''}{CATEGORY_LABELS[s]}
              </span>
            ))}
          </div>
          <p className="to-subtitle">
            좋아하는 <strong>{CATEGORY_LABELS[step]}</strong>을 3개 선택해주세요&nbsp;
            <span className="to-count">{selected.length} / {SELECT_COUNT}</span>
          </p>
        </div>

        {/* 포스터 그리드 */}
        <div className="to-grid">
          {TASTE_DATA[step].map(item => (
            <PosterCard
              key={item.id}
              item={item}
              selected={selected.includes(item.id)}
              disabled={selected.length >= SELECT_COUNT && !selected.includes(item.id)}
              onToggle={() => toggle(item.id)}
            />
          ))}
        </div>

        {/* 하단 */}
        <div className="to-footer">
          {stepIdx > 0 && (
            <button className="to-btn to-btn--back" onClick={() => setStepIdx(s => s - 1)}>← 이전</button>
          )}
          <button
            className="to-btn to-btn--next"
            onClick={handleNext}
            disabled={!canProceed || submitting}
          >
            {submitting ? '분석 중...' : isLast ? '완료' : `다음 → ${CATEGORY_LABELS[STEPS[stepIdx + 1]]}`}
          </button>
        </div>
      </div>
    </div>
  );
}
