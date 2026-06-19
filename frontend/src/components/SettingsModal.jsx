import { useState, useEffect } from 'react';
import { getGlobalVideoVolume, setGlobalVideoVolume, getReactionVideoVolume, setReactionVideoVolume } from '../lib/videoVolume';
import { bgmPlay, bgmPause } from '../lib/bgmController';

const S = {
  overlay: {
    position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.45)',
    zIndex: 10000, display: 'flex', alignItems: 'center', justifyContent: 'center',
    padding: 16,
  },
  card: {
    width: 360, maxWidth: '100%', boxSizing: 'border-box',
    background: 'var(--card-main, #fff)', color: 'var(--text-main, #222)',
    borderRadius: 18, padding: 24, boxShadow: '0 12px 44px rgba(0,0,0,0.28)',
  },
  title: { margin: '0 0 6px', fontSize: 18, fontWeight: 800 },
  block: { padding: '14px 0', borderTop: '1px solid rgba(0,0,0,0.08)' },
  head: { display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 },
  label: { fontSize: 14, fontWeight: 600 },
  range: {
    width: '100%', display: 'block', marginTop: 10, boxSizing: 'border-box',
    accentColor: 'var(--theme-color, #6b5bd2)',
  },
  toggle: (on) => ({
    border: 'none', borderRadius: 999, padding: '6px 0', cursor: 'pointer',
    fontSize: 12, fontWeight: 700, width: 64, flexShrink: 0, textAlign: 'center',
    background: on ? 'var(--theme-color, #6b5bd2)' : 'rgba(0,0,0,0.12)',
    color: on ? '#fff' : 'var(--text-sub, #888)',
  }),
  btns: {
    display: 'flex', gap: 10, marginTop: 18,
  },
  cancel: {
    flex: 1, border: '1px solid rgba(0,0,0,0.18)', borderRadius: 12, padding: '11px',
    background: 'none', color: 'var(--text-main, #222)', cursor: 'pointer',
    fontWeight: 700, fontSize: 15, boxSizing: 'border-box',
  },
  save: {
    flex: 1, border: 'none', borderRadius: 12, padding: '11px',
    background: 'var(--theme-color, #6b5bd2)', color: '#fff', cursor: 'pointer',
    fontWeight: 700, fontSize: 15, boxSizing: 'border-box',
  },
};

const readSaved = () => ({
  bgmOn: localStorage.getItem('bgm_playing') !== 'false',
  bgmVol: Number(localStorage.getItem('bgm_volume') ?? 0.2),
  videoVol: getGlobalVideoVolume(),
  reactionVideoVol: getReactionVideoVolume(),
  reactionOn: localStorage.getItem('voice_reaction') !== 'off',
});

export default function SettingsModal({ open, onClose }) {
  const [draft, setDraft] = useState(readSaved);

  // 열릴 때 현재 저장값으로 draft 초기화
  useEffect(() => {
    if (open) setDraft(readSaved());
  }, [open]);

  if (!open) return null;

  const set = (key) => (val) => setDraft((prev) => ({ ...prev, [key]: val }));

  const handleSave = () => {
    localStorage.setItem('bgm_playing', String(draft.bgmOn));
    localStorage.setItem('bgm_volume', String(draft.bgmVol));
    localStorage.setItem('voice_reaction', draft.reactionOn ? 'on' : 'off');
    setGlobalVideoVolume(draft.videoVol);
    setReactionVideoVolume(draft.reactionVideoVol);
    // 사용자 제스처(클릭) 컨텍스트에서 직접 제어 — dispatchEvent는 autoplay 차단됨
    if (draft.bgmOn) {
      bgmPlay().catch(() => {});
    } else {
      bgmPause();
    }
    window.dispatchEvent(new Event('bgm-volume-changed'));
    onClose();
  };

  const handleCancel = () => onClose();

  return (
    <div style={S.overlay} onClick={handleCancel}>
      <div style={S.card} onClick={(e) => e.stopPropagation()}>
        <h3 style={S.title}>환경설정</h3>

        {/* 배경음악 */}
        <div style={S.block}>
          <div style={S.head}>
            <span style={S.label}>배경음악 (BGM)</span>
            <button style={S.toggle(draft.bgmOn)} onClick={() => set('bgmOn')(!draft.bgmOn)}>
              {draft.bgmOn ? 'ON' : 'OFF'}
            </button>
          </div>
          <input
            style={S.range} type="range" min="0" max="1" step="0.01"
            value={draft.bgmVol} disabled={!draft.bgmOn}
            onChange={(e) => set('bgmVol')(Number(e.target.value))}
          />
        </div>

        {/* 로딩 영상 소리 */}
        <div style={S.block}>
          <div style={S.head}>
            <span style={S.label}>로딩 영상 소리</span>
            <button
              style={S.toggle(draft.videoVol > 0)}
              onClick={() => set('videoVol')(draft.videoVol > 0 ? 0 : 0.3)}
            >
              {draft.videoVol > 0 ? 'ON' : '음소거'}
            </button>
          </div>
          <input
            style={S.range} type="range" min="0" max="1" step="0.01"
            value={draft.videoVol}
            onChange={(e) => set('videoVol')(Number(e.target.value))}
          />
        </div>

        {/* 리액션 영상 소리 */}
        <div style={S.block}>
          <div style={S.head}>
            <span style={S.label}>리액션 영상 소리</span>
            <button
              style={S.toggle(draft.reactionVideoVol > 0)}
              onClick={() => set('reactionVideoVol')(draft.reactionVideoVol > 0 ? 0 : 0.3)}
            >
              {draft.reactionVideoVol > 0 ? 'ON' : '음소거'}
            </button>
          </div>
          <input
            style={S.range} type="range" min="0" max="1" step="0.01"
            value={draft.reactionVideoVol}
            onChange={(e) => set('reactionVideoVol')(Number(e.target.value))}
          />
        </div>

        {/* 작가 리액션 음성 */}
        <div style={S.block}>
          <div style={S.head}>
            <span style={S.label}>작가 리액션 음성</span>
            <button style={S.toggle(draft.reactionOn)} onClick={() => set('reactionOn')(!draft.reactionOn)}>
              {draft.reactionOn ? 'ON' : 'OFF'}
            </button>
          </div>
        </div>

        <div style={S.btns}>
          <button style={S.cancel} onClick={handleCancel}>취소</button>
          <button style={S.save} onClick={handleSave}>저장</button>
        </div>
      </div>
    </div>
  );
}
