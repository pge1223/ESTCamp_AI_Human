// frontend/src/components/AuthorPanel.jsx
import React, { useState, useEffect, useRef, useImperativeHandle, forwardRef } from 'react';
import {
  sendAuthorMessage, getMemos, saveMemos,
  getTasteRecommend, addGlossaryTerm, lyricApply,
} from '../lib/chatApi';
import { saveSentence } from '../lib/mypageApi';
import { getTaste, analyzeTaste } from '../lib/tasteApi';
import { applyReactionVideoVolume, REACTION_VIDEO_VOLUME_EVENT } from '../lib/videoVolume';

// "=", “=", "=” — LLM이 따옴표를 포함해서 보낼 때 제거
const stripOuterQuotes = s => s ? s.replace(/^["“”]+|["“”]+$/g, '').trim() : '';

const AUTHOR_IDS = [1, 2, 3, 4];
const AUTHOR_MAP = {
  1: { characterId: 'baekya', displayName: '백야', image: '/assets/author1/author1.png' },
  2: { characterId: 'charoun', displayName: '차로운', image: '/assets/author2/author2.png' },
  3: { characterId: 'hanyeoreum', displayName: '한여름', image: '/assets/author3/author3.png' },
  4: { characterId: 'kimdohyeon', displayName: '김도현', image: '/assets/author4/author4.png' },
};

const AUTHOR_TAGS_CHAT = [
  { label: '#세계관', prompt: null },
  { label: '#등장인물', prompt: null },
  { label: '#취향저격ai', prompt: null },
  { label: '#도움말', prompt: null },
];

const AUTHOR_TAGS_EDITOR = [
  { label: '#세계관', prompt: null },
  { label: '#등장인물', prompt: null },
  { label: '#취향저격ai', prompt: null },
];

const TASTE_LABELS = {
  fantasy: '판타지', growth: '성장', romance: '로맨스', action: '액션',
  sf: 'SF', mystery: '미스터리', horror: '호러', politics: '정치', slice_of_life: '일상',
};


const AuthorPanel = forwardRef(function AuthorPanel({
  chatId,
  userId,
  world,
  dbCharacters = [],
  mode = 'chat',
  // Author switcher — controlled by parent
  currentAuthorIdx = 0,
  onAuthorChange,
  // Controlled by parent
  autoFeedback = false,
  onAutoFeedbackChange,
  realtimeProof = false,
  onRealtimeProofChange,
  memos = [],
  onMemosChange,
  // Text insertion into main content area
  onApplyText,
  // Feedback button
  getFeedbackText,
  isFeedbackDisabled = false,
  // Chat-specific
  reaction = '',
  reactionEmotion = null,
  onReactionEnd,
  selectedMsgId = null,
  onSelectedMsgIdChange,
  onMemoClick,
  // Editor-specific
  corrections = [],
  proofMemo = '',
  onApplyCorrection,
  onSkipCorrection,
  onClearCorrections,
  hasSelection = false,
  onWorldEdit,
  onShouldRecommend,
}, ref) {
  const currentAuthor = AUTHOR_MAP[AUTHOR_IDS[currentAuthorIdx]];

  const [panelRatio, setPanelRatio] = useState(0.45);
  const [isResizing, setIsResizing] = useState(false);
  const [authorLoading, setAuthorLoading] = useState(false);
  const [videoError, setVideoError] = useState(false);
  const [panelView, setPanelView] = useState('author');
  const [authorMessages, setAuthorMessages] = useState([]);
  const [authorInput, setAuthorInput] = useState('');
  const [showWorldInfo, setShowWorldInfo] = useState(false);
  const [showCharInfo, setShowCharInfo] = useState(false);
  const [showHelpInfo, setShowHelpInfo] = useState(false);
  const [savedMsgId, setSavedMsgId] = useState(null);
  const [showTastePanel, setShowTastePanel] = useState(false);
  const [tasteWorks, setTasteWorks] = useState([]);
  const [tasteInput, setTasteInput] = useState('');
  const [tasteProfile, setTasteProfile] = useState(null);
  const [tasteAnalyzing, setTasteAnalyzing] = useState(false);
  const [tasteRecommending, setTasteRecommending] = useState(false);
  const [memoInput, setMemoInput] = useState('');
  const [editingMemoId, setEditingMemoId] = useState(null);
  const [bookmarkMode, setBookmarkMode] = useState(false);
  const [recContextMenu, setRecContextMenu] = useState({ visible: false, x: 0, y: 0, content: '' });
  const [lyricQuery, setLyricQuery] = useState('');
  const [lyricLoading, setLyricLoading] = useState(false);
  const [lyricResult, setLyricResult] = useState(null); // { extracted, scene }

  const authorBottomRef = useRef(null);
  const memoInputRef = useRef(null);
  const authorVideoRef = useRef(null);
  const memosLoadedRef = useRef(false);

  const AUTHOR_TAGS = mode === 'chat' ? AUTHOR_TAGS_CHAT : AUTHOR_TAGS_EDITOR;

  useImperativeHandle(ref, () => ({
    openMemoFor(msgId) {
      const existing = memos.find(m => m.msgId === msgId);
      setEditingMemoId(existing ? existing.id : null);
      setMemoInput(existing ? existing.text : '');
      onSelectedMsgIdChange?.(msgId);
      setBookmarkMode(true);
      setPanelView('memo');
      setTimeout(() => memoInputRef.current?.focus(), 80);
    },
    triggerFeedback(text) {
      setPanelView('author');
      handleSendAuthorMessage(text, { mode: 'feedback', hideUser: mode === 'chat' });
    },
    showProofView() { setPanelView('proof'); },
    isLoading: () => authorLoading,
  }));

  // ── 취향 복원 ────────────────────────────────────────────
  useEffect(() => {
    if (!userId || !chatId) return;
    getTaste(chatId, userId).then(data => {
      if (data.works?.length) setTasteWorks(data.works);
      if (data.taste_profile && Object.keys(data.taste_profile).length) setTasteProfile(data.taste_profile);
    }).catch(() => { });
  }, [userId, chatId]);

  // ── 메모 Redis 로드 ───────────────────────────────────────
  useEffect(() => {
    if (!chatId) return;
    getMemos(chatId).then(({ memos: loaded }) => {
      onMemosChange(loaded ?? []);
      memosLoadedRef.current = true;
    });
  }, [chatId]);

  // ── 메모 Redis 저장 ───────────────────────────────────────
  useEffect(() => {
    if (!memosLoadedRef.current) return;
    saveMemos(chatId, memos);
  }, [memos]);

  useEffect(() => { setVideoError(false); }, [currentAuthorIdx]);

  useEffect(() => {
    authorBottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [authorMessages, authorLoading]);

  // ── 패널 리사이즈
  useEffect(() => {
    if (!isResizing) return;
    function onMove(e) {
      setPanelRatio(Math.min(0.6, Math.max(0.28, (window.innerWidth - e.clientX) / window.innerWidth)));
    }
    function onUp() { setIsResizing(false); }
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
    return () => { window.removeEventListener('mousemove', onMove); window.removeEventListener('mouseup', onUp); };
  }, [isResizing]);

  // ── 추천 컨텍스트 메뉴 닫기 ──────────────────────────────
  useEffect(() => {
    if (!recContextMenu.visible) return;
    const close = () => setRecContextMenu(m => ({ ...m, visible: false }));
    window.addEventListener('click', close);
    return () => window.removeEventListener('click', close);
  }, [recContextMenu.visible]);

  // ── 볼륨 (chat only) ─────────────────────────────────────
  useEffect(() => {
    if (mode !== 'chat') return;
    const video = authorVideoRef.current;
    if (!video) return;
    applyReactionVideoVolume(video);
    const handleVolumeChange = () => applyReactionVideoVolume(authorVideoRef.current);
    window.addEventListener(REACTION_VIDEO_VOLUME_EVENT, handleVolumeChange);
    return () => window.removeEventListener(REACTION_VIDEO_VOLUME_EVENT, handleVolumeChange);
  }, [mode, currentAuthorIdx, reactionEmotion]);

  // ── 작가 전환 ─────────────────────────────────────────────
  function prevAuthor() { onAuthorChange?.((currentAuthorIdx - 1 + AUTHOR_IDS.length) % AUTHOR_IDS.length); }
  function nextAuthor() { onAuthorChange?.((currentAuthorIdx + 1) % AUTHOR_IDS.length); }

  const REC_KEYWORDS = /추천해줘|문장 추천|다음 문장|이어서 써줘|추천 해줘/;

  async function handleSendAuthorMessage(overrideText, { mode: msgMode = 'chat', hideUser = false } = {}) {
    const text = (overrideText ?? authorInput).trim();
    if (!text || authorLoading) return;
    if (!overrideText) setAuthorInput('');
    if (!hideUser) setAuthorMessages(prev => [...prev, { id: `au_${Date.now()}`, role: 'user', content: text }]);
    setAuthorLoading(true);

    const isRecRequest = mode === 'chat' && msgMode === 'chat' && REC_KEYWORDS.test(text);

    try {
      if (isRecRequest) {
        // 3번 병렬 호출 → 각각 독립 추천 버블
        const opening_narration = localStorage.getItem('opening_' + chatId) || '';
        const results = await Promise.allSettled(
          [0, 1, 2].map(() => sendAuthorMessage(chatId, {
            content: text,
            author_id: currentAuthor.characterId,
            mode: msgMode,
            opening_narration,
          }))
        );
        const recMsgs = results
          .filter(r => r.status === 'fulfilled')
          .map((r, i) => ({
            id: `${r.value.messageId}_rec_${i}`, role: 'ai', type: 'feedback',
            content: r.value.content, isRecommend: true,
          }));
        setAuthorMessages(prev => [...prev, ...recMsgs]);
      } else {
        const data = await sendAuthorMessage(chatId, {
          content: text,
          author_id: currentAuthor.characterId,
          mode: msgMode,
          opening_narration: localStorage.getItem('opening_' + chatId) || '',
        });
        setAuthorMessages(prev => [...prev, {
          id: data.messageId, role: 'ai', type: 'feedback', content: data.content,
          isRecommend: !!data.shouldRecommend,
        }]);
      }
    } catch (err) {
      console.error('작가 AI 오류:', err);
    } finally {
      setAuthorLoading(false);
    }
  }

  async function runTasteAnalysis(works) {
    if (!userId || !chatId) return;
    setTasteAnalyzing(true);
    try {
      const data = await analyzeTaste(chatId, { user_id: userId, works });
      setTasteProfile(data.taste_profile);
    } catch (e) { console.error('취향 분석 실패', e); }
    finally { setTasteAnalyzing(false); }
  }

  async function handleTasteRecommend() {
    if (!userId || !chatId || tasteRecommending) return;
    setTasteRecommending(true);
    const loadingId = `tr_${Date.now()}`;
    setAuthorMessages(prev => [...prev, { id: loadingId, role: 'ai', type: 'taste-recommend', loading: true, recommendations: [] }]);
    try {
      const data = await getTasteRecommend(chatId, userId, currentAuthor.characterId);
      setAuthorMessages(prev => prev.map(m => m.id === loadingId ? { ...m, loading: false, ...data } : m));
    } catch (e) {
      console.error('취향저격 오류', e);
      setAuthorMessages(prev => prev.filter(m => m.id !== loadingId));
    } finally { setTasteRecommending(false); }
  }

  async function handleTasteInputKeyDown(e) {
    if (e.key !== 'Enter' || !tasteInput.trim()) return;
    e.preventDefault();
    const newWorks = [...tasteWorks, tasteInput.trim()];
    setTasteWorks(newWorks);
    setTasteInput('');
    await runTasteAnalysis(newWorks);
  }

  async function handleRemoveTasteWork(idx) {
    const newWorks = tasteWorks.filter((_, i) => i !== idx);
    setTasteWorks(newWorks);
    if (newWorks.length > 0) {
      await runTasteAnalysis(newWorks);
    } else {
      setTasteProfile(null);
      if (userId && chatId) analyzeTaste(chatId, { user_id: userId, works: [] }).catch(() => { });
    }
  }

  function handleTagClick(tag) {
    if (authorLoading) return;
    if (tag.label === '#세계관') { setShowWorldInfo(prev => !prev); setShowCharInfo(false); setShowHelpInfo(false); return; }
    if (tag.label === '#등장인물') { setShowCharInfo(prev => !prev); setShowWorldInfo(false); setShowHelpInfo(false); return; }
    if (tag.label === '#가사적용ai') {
      setShowWorldInfo(false); setShowCharInfo(false); setShowHelpInfo(false);
      setPanelView('lyric'); return;
    }
    if (tag.label === '#취향저격ai') {
      setShowWorldInfo(false); setShowCharInfo(false); setShowHelpInfo(false);
      setPanelView('author'); handleTasteRecommend(); return;
    }
    if (tag.label === '#도움말') { setShowHelpInfo(prev => !prev); setShowWorldInfo(false); setShowCharInfo(false); return; }
    setShowWorldInfo(false); setShowCharInfo(false); setShowHelpInfo(false);
    setPanelView('author');
    handleSendAuthorMessage(tag.prompt);
  }

  function handleFeedback() {
    const text = getFeedbackText?.();
    if (!text) return;
    setPanelView('author');
    handleSendAuthorMessage(text, { mode: 'feedback', hideUser: mode === 'chat' });
  }

  async function handleSaveSentence(msgId, content) {
    if (!userId) return;
    try {
      await saveSentence({ userId, content, sessionId: chatId ?? null });
      setSavedMsgId(msgId);
      setTimeout(() => setSavedMsgId(null), 1500);
    } catch (e) { console.error(e); }
  }

  function handleAddMemo() {
    if (!memoInput.trim()) return;
    if (editingMemoId) {
      onMemosChange(memos.map(m => m.id === editingMemoId ? { ...m, text: memoInput } : m));
    } else {
      onMemosChange([...memos, { id: Date.now(), type: 'manual', text: memoInput, msgId: selectedMsgId || null }]);
    }
    setMemoInput('');
    setEditingMemoId(null);
    setBookmarkMode(false);
    onSelectedMsgIdChange?.(null);
  }

  // ── 렌더 ─────────────────────────────────────────────────
  return (
    <div className="author-panel-wrapper">
      <div
        className={`author-panel-resizer${isResizing ? ' author-panel-resizer--active' : ''}`}
        onMouseDown={e => { e.preventDefault(); setIsResizing(true); }}
        title="드래그하여 패널 너비 조절"
      />
      <div
        className="author-panel-slide"
        style={{ width: `${panelRatio * 100}vw`, transition: isResizing ? 'none' : undefined }}
      >
        <div className="author-panel">

          {panelView === 'author' ? (
            <>
              {/* 작가 이미지 + 스위처 */}
              <div className="author-panel__image">
                {!videoError ? (
                  <video
                    ref={authorVideoRef}
                    key={`${AUTHOR_IDS[currentAuthorIdx]}-${reactionEmotion ?? 'default'}`}
                    src={
                      mode === 'chat' && reactionEmotion
                        ? `/assets/author${AUTHOR_IDS[currentAuthorIdx]}/${reactionEmotion}.mp4`
                        : `/assets/author${AUTHOR_IDS[currentAuthorIdx]}/default.mp4`
                    }
                    autoPlay
                    loop={mode === 'editor' || !reactionEmotion}
                    playsInline
                    onEnded={mode === 'chat' ? onReactionEnd : undefined}
                    onError={() => setVideoError(true)}
                  />
                ) : (
                  <img src={currentAuthor.image} alt={currentAuthor.displayName} />
                )}
                {mode === 'chat' && reaction && (
                  <div className="author-reaction-subtitle" key={reaction}>- {reaction}</div>
                )}
                <div className="author-switcher author-panel__switcher-overlay">
                  <button className="author-switch-btn" onClick={prevAuthor}>‹</button>
                  <span className="author-name-badge">{currentAuthor.displayName}</span>
                  <button className="author-switch-btn" onClick={nextAuthor}>›</button>
                </div>
              </div>

              {/* 태그 바 */}
              <div className="author-tag-bar">
                {AUTHOR_TAGS.map(tag => (
                  <button
                    key={tag.label}
                    className={`author-tag${(tag.label === '#세계관' && showWorldInfo) ||
                      (tag.label === '#등장인물' && showCharInfo) ||
                      (tag.label === '#도움말' && showHelpInfo)
                      ? ' author-tag--active' : ''
                      }${tag.label === '#취향저격ai' ? ' author-tag--accent' : ''}${tag.label === '#가사적용ai' ? ' author-tag--accent' : ''
                      }${tag.label === '#가사적용ai' && panelView === 'lyric' ? ' author-tag--active' : ''
                      }`}
                    onClick={() => handleTagClick(tag)}
                    disabled={authorLoading || (tag.label === '#취향저격ai' && tasteRecommending)}
                  >{tag.label === '#취향저격ai' && tasteRecommending ? '추천 중...' : tag.label}</button>
                ))}
                <button
                  className={`memo-view-btn author-tag-bar__memo${panelView === 'memo' ? ' memo-view-btn--active' : ''}`}
                  onClick={() => setPanelView('memo')}
                >
                  🗒️ 메모
                  {memos.length > 0 && <span className="memo-count">{memos.length}</span>}
                </button>
                <button
                  className={`memo-view-btn author-tag-bar__memo${panelView === 'proof' ? ' memo-view-btn--active' : ''}`}
                  onClick={() => setPanelView('proof')}
                >
                  ✏️ 교정
                  {mode === 'chat'
                    ? corrections.reduce((n, c) => n + c.errors.length, 0) > 0 &&
                    <span className="memo-count memo-count--proof">{corrections.reduce((n, c) => n + c.errors.length, 0)}</span>
                    : corrections.filter(e => !e.applied).length > 0 &&
                    <span className="memo-count memo-count--proof">{corrections.filter(e => !e.applied).length}</span>
                  }
                </button>
              </div>

              {/* 자동 피드백 토글 */}
              <div className="auto-feedback-bar">
                <span className="auto-feedback-bar__label">자동 피드백</span>
                <button
                  className={`auto-feedback-toggle${autoFeedback ? ' auto-feedback-toggle--on' : ''}`}
                  onClick={() => onAutoFeedbackChange?.(!autoFeedback)}
                >
                  {autoFeedback ? 'ON' : 'OFF'}
                </button>
                <span className="auto-feedback-bar__label auto-feedback-bar__label--proof">실시간 교정</span>
                <button
                  className={`auto-feedback-toggle${realtimeProof ? ' auto-feedback-toggle--on' : ''}`}
                  onClick={() => onRealtimeProofChange?.(!realtimeProof)}
                >
                  {realtimeProof ? 'ON' : 'OFF'}
                </button>
                {!autoFeedback && (
                  <button
                    className={`feedback-btn${mode === 'editor' && hasSelection ? ' feedback-btn--selection' : ''}`}
                    onClick={handleFeedback}
                    disabled={authorLoading || isFeedbackDisabled}
                    title={mode === 'editor' && hasSelection ? '선택한 구간만 피드백' : undefined}
                  >
                    {mode === 'editor' && hasSelection ? '선택 구간 피드백' : '피드백 받기'}
                  </button>
                )}
              </div>

              {/* 세계관 카드 */}
              {showWorldInfo && world && (
                <div className="world-info-card">
                  {onWorldEdit && (
                    <div className="world-info-card__edit-row">
                      <button className="world-info-card__edit-btn" onClick={onWorldEdit}>✎ 세계관 수정</button>
                    </div>
                  )}
                  {world.title && <div className="world-info-card__row"><span className="world-info-card__label">제목</span>{world.title}</div>}
                  {world.genre && <div className="world-info-card__row"><span className="world-info-card__label">장르</span>{world.genre}</div>}
                  {world.description && <div className="world-info-card__row"><span className="world-info-card__label">배경</span>{world.description}</div>}
                  {world.setting && <div className="world-info-card__row"><span className="world-info-card__label">공간</span>{world.setting}</div>}
                  {world.rules && <div className="world-info-card__row"><span className="world-info-card__label">규칙</span>{world.rules}</div>}
                </div>
              )}

              {/* 등장인물 카드 */}
              {showCharInfo && dbCharacters.length > 0 && (
                <div className="world-info-card">
                  {dbCharacters.map(c => (
                    <div key={c.id ?? c.name} className="world-info-card__char-row">
                      <span className="world-info-card__char-name">{c.name}</span>
                      <span className="world-info-card__char-role">{c.role === 'protagonist' ? '주인공' : '조연'}</span>
                      {c.personality && <span className="world-info-card__char-desc">{c.personality}</span>}
                      {c.prompt && (
                        <span className="world-info-card__char-prompt">
                          <span className="world-info-card__char-role">특성</span>
                          {c.prompt}
                        </span>
                      )}
                    </div>
                  ))}
                </div>
              )}

              {/* 도움말 카드 (chat only) */}
              {mode === 'chat' && showHelpInfo && (
                <div className="world-info-card world-info-card--help">
                  <div className="world-info-card__row">
                    <span className="world-info-card__label">대사</span>
                    큰따옴표 안에 쓰세요<br />
                    <span style={{ color: 'var(--color-text-muted, #888)', fontSize: '0.85em' }}>예) "왜 그러는 거야?"</span>
                  </div>
                  <div className="world-info-card__row">
                    <span className="world-info-card__label">독백·속마음</span>
                    작은따옴표 안에 쓰세요<br />
                    <span style={{ color: 'var(--color-text-muted, #888)', fontSize: '0.85em' }}>예) '이 사람, 뭔가 숨기고 있어.'</span>
                  </div>
                  <div className="world-info-card__row">
                    <span className="world-info-card__label">행동·서술</span>
                    따옴표 없이 그냥 쓰세요<br />
                    <span style={{ color: 'var(--color-text-muted, #888)', fontSize: '0.85em' }}>예) 스카프를 건네며 고개를 돌린다</span>
                  </div>
                  <div className="world-info-card__row">
                    <span className="world-info-card__label">@등장인물</span>
                    특정 인물 시점으로 전환<br />
                    <span style={{ color: 'var(--color-text-muted, #888)', fontSize: '0.85em' }}>예) @에드워드 "무슨 일이야?"</span>
                  </div>
                </div>
              )}

              {/* 작가 AI 채팅 */}
              <div className="author-chat">
                <div className="author-chat__messages">
                  {authorMessages.length === 0 && !authorLoading && (
                    <p className="author-chat__empty">
                      {currentAuthor.displayName}에게<br />
                      {mode === 'chat' ? '소설에 대해 물어보세요' : '원고 피드백을 받아보세요'}
                    </p>
                  )}
                  {authorMessages.map(msg => {
                    if (msg.role === 'user') return (
                      <div key={msg.id} className="author-msg author-msg--user">{msg.content}</div>
                    );
                    if (msg.type === 'taste-recommend') return (
                      <div key={msg.id} className="author-msg-group">
                        <span className="author-msg__name author-msg__name--rec">✨ 취향저격 추천</span>
                        {msg.loading ? (
                          <div className="author-msg author-msg--taste-rec">
                            <div className="typing-dots"><span /><span /><span /></div>
                          </div>
                        ) : (
                          <div className="author-msg--taste-rec-list">
                            {(msg.recommendations || []).map((rec, i) => (
                              <div key={i} className="author-msg author-msg--taste-rec taste-rec__card">
                                {rec.type && <span className="taste-rec__type-badge">{rec.type}</span>}
                                {rec.narration && <p className="taste-rec__narration">{rec.narration}</p>}
                                {rec.dialogue && <p className="taste-rec__dialogue">&ldquo;{stripOuterQuotes(rec.dialogue)}&rdquo;</p>}
                                {rec.reason && <p className="taste-rec__reason">💡 {rec.reason}</p>}
                                <button
                                  className="taste-rec__use-btn"
                                  onClick={() => {
                                    const clean = stripOuterQuotes(rec.dialogue);
                                    const parts = [rec.narration, clean ? `"${clean}"` : ''].filter(Boolean);
                                    onApplyText?.(parts.join('\n'));
                                  }}
                                >이 문장 사용하기 →</button>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    );
                    // feedback message
                    return (
                      <div key={msg.id} className="author-msg-group">
                        <div className="author-msg-group__top">
                          <span className="author-msg__name">작가 {currentAuthor.displayName}</span>
                          <button
                            className={`save-sentence-btn${savedMsgId === msg.id ? ' save-sentence-btn--saved' : ''}`}
                            onClick={() => handleSaveSentence(msg.id, msg.content)}
                            title="문장 보관함에 저장"
                          >
                            {savedMsgId === msg.id ? '✓' : '💾'}
                          </button>
                        </div>
                        <div
                          className={`author-msg author-msg--ai${msg.isRecommend && mode === 'chat' ? ' author-msg--rec' : ''}`}
                          onClick={msg.isRecommend && mode === 'chat' ? () => onApplyText?.(msg.content) : undefined}
                          title={msg.isRecommend && mode === 'chat' ? '클릭하면 입력창에 삽입' : undefined}
                          onContextMenu={mode === 'chat' ? e => {
                            e.preventDefault();
                            setRecContextMenu({ visible: true, x: e.clientX, y: e.clientY, content: msg.content, copyOnly: true });
                          } : undefined}
                        >
                          {msg.content}
                        </div>
                      </div>
                    );
                  })}
                  {authorLoading && (
                    <div className="author-msg-group">
                      <span className="author-msg__name">작가 {currentAuthor.displayName}</span>
                      <div className="author-msg author-msg--ai">
                        <div className="typing-dots"><span /><span /><span /></div>
                      </div>
                    </div>
                  )}
                  <div ref={authorBottomRef} />
                </div>

                {/* 취향 패널 */}
                {showTastePanel && (
                  <div className="taste-panel">
                    <div className="taste-panel__header">
                      <span className="taste-panel__title">좋아하는 작품을 입력해주세요 ({tasteWorks.length}/5)</span>
                      <button className="taste-panel__close" onClick={() => setShowTastePanel(false)}>×</button>
                    </div>
                    <div className="taste-panel__chips">
                      {tasteWorks.map((w, i) => (
                        <span key={i} className="taste-chip">
                          {w}
                          <button className="taste-chip__remove" onClick={() => handleRemoveTasteWork(i)}>×</button>
                        </span>
                      ))}
                    </div>
                    {tasteWorks.length < 5 && (
                      <input
                        className="taste-panel__input"
                        placeholder="작품명 입력 후 엔터..."
                        value={tasteInput}
                        onChange={e => setTasteInput(e.target.value)}
                        onKeyDown={handleTasteInputKeyDown}
                        autoFocus
                      />
                    )}
                    {tasteAnalyzing && <div className="taste-panel__analyzing">분석 중...</div>}
                    {tasteProfile && Object.keys(tasteProfile).length > 0 && (
                      <div className="taste-panel__result">
                        {Object.entries(tasteProfile)
                          .sort(([, a], [, b]) => b - a)
                          .slice(0, 5)
                          .map(([key, val]) => (
                            <div key={key} className="taste-bar">
                              <span className="taste-bar__label">{TASTE_LABELS[key] ?? key}</span>
                              <div className="taste-bar__track">
                                <div className="taste-bar__fill" style={{ width: `${Math.round(val * 100)}%` }} />
                              </div>
                              <span className="taste-bar__val">{Math.round(val * 100)}%</span>
                            </div>
                          ))
                        }
                      </div>
                    )}
                  </div>
                )}

                <div className="author-chat__input-bar">
                  <textarea
                    className="author-chat__input"
                    placeholder={`${currentAuthor.displayName}에게 물어보기...`}
                    value={authorInput}
                    rows={2}
                    disabled={authorLoading}
                    onChange={e => setAuthorInput(e.target.value)}
                    onKeyDown={e => {
                      if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); handleSendAuthorMessage(); }
                    }}
                  />
                  <button className="author-chat__send" onClick={() => handleSendAuthorMessage()} disabled={authorLoading}>→</button>
                </div>
              </div>
            </>
          ) : panelView === 'lyric' ? (
            <div className="lyric-panel">
              <div className="memo-view__header">
                <span>🎵 가사적용 AI</span>
                <button className="memo-view__back" onClick={() => { setPanelView('author'); setLyricResult(null); }}>← 돌아가기</button>
              </div>

              <div className="lyric-panel__desc">
                노래 제목이나 분위기를 입력하면<br />
                감정을 현재 이야기에 녹여드립니다.
              </div>

              <textarea
                className="lyric-panel__input"
                placeholder={"예) NewJeans - Hype Boy\n예) 기다림, 새벽, 고독한 느낌"}
                value={lyricQuery}
                rows={3}
                onChange={e => setLyricQuery(e.target.value)}
                disabled={lyricLoading}
              />

              <div className="lyric-panel__actions">
                <button
                  className="lyric-panel__btn lyric-panel__btn--transform"
                  disabled={lyricLoading || !lyricQuery.trim()}
                  onClick={async () => {
                    setLyricLoading(true);
                    setLyricResult(null);
                    try {
                      const data = await lyricApply(chatId, lyricQuery.trim(), 'transform');
                      setLyricResult(data);
                    } catch { /* silent */ }
                    finally { setLyricLoading(false); }
                  }}
                >✏️ 현재 장면 변환</button>
                <button
                  className="lyric-panel__btn lyric-panel__btn--recommend"
                  disabled={lyricLoading || !lyricQuery.trim()}
                  onClick={async () => {
                    setLyricLoading(true);
                    setLyricResult(null);
                    try {
                      const data = await lyricApply(chatId, lyricQuery.trim(), 'recommend');
                      setLyricResult(data);
                    } catch { /* silent */ }
                    finally { setLyricLoading(false); }
                  }}
                >💡 어울리는 장면 추천</button>
              </div>

              {lyricLoading && (
                <div className="lyric-panel__loading">
                  <div className="typing-dots"><span /><span /><span /></div>
                  <span>감정 분석 중...</span>
                </div>
              )}

              {lyricResult && !lyricLoading && (
                <div className="lyric-panel__result">
                  <div className="lyric-panel__tags">
                    {lyricResult.extracted?.emotion && <span className="lyric-tag">💭 {lyricResult.extracted.emotion}</span>}
                    {lyricResult.extracted?.mood && <span className="lyric-tag">🌙 {lyricResult.extracted.mood}</span>}
                    {lyricResult.extracted?.theme && <span className="lyric-tag">📖 {lyricResult.extracted.theme}</span>}
                  </div>
                  <div className="lyric-panel__scene">{lyricResult.scene}</div>
                  <button
                    className="lyric-panel__use-btn"
                    onClick={() => onApplyText?.(lyricResult.scene)}
                  >이 장면 사용하기 →</button>
                </div>
              )}
            </div>
          ) : panelView === 'proof' ? (
            <div className="memo-view">
              <div className="memo-view__header">
                <span>{currentAuthor.displayName}의 교정</span>
                {mode === 'editor' ? (
                  <div className="memo-proof__head-actions">
                    {corrections.length > 0 && (
                      <button className="memo-view__back" onClick={onClearCorrections}>비우기</button>
                    )}
                    <button className="memo-view__back" onClick={() => setPanelView('author')}>← 돌아가기</button>
                  </div>
                ) : (
                  <button className="memo-view__back" onClick={() => setPanelView('author')}>← 돌아가기</button>
                )}
              </div>
              {mode === 'editor' && proofMemo && <p className="memo-proof__memo">"{proofMemo}"</p>}
              <div className="memo-view__list">
                {corrections.length === 0 && (
                  <p className="author-chat__empty">
                    맞춤법 오류가 없어요 ✨<br />
                    {mode === 'chat' ? '대화하면 작가가 봐줍니다' : '글을 쓰면 작가가 봐줍니다'}
                  </p>
                )}
                {mode === 'chat' ? (
                  corrections.map(c => (
                    <div key={c.id} className="memo-proof__card">
                      {c.memo && <p className="memo-proof__memo">"{c.memo}"</p>}
                      <ul className="memo-proof__list">
                        {c.errors.map((e, i) => (
                          <li key={i} className={`memo-proof__err${e.frequent ? ' memo-proof__err--frequent' : ''}`}>
                            <span className="memo-proof__wrong">{e.original}</span>
                            <span className="memo-proof__arrow">→</span>
                            <span className="memo-proof__right">{e.corrected}</span>
                            <span className="memo-proof__type">{e.type}</span>
                            {e.frequent && <span className="memo-proof__freq">자주 틀림 {e.count}회</span>}
                          </li>
                        ))}
                      </ul>
                      <button
                        className="memo-proof__dismiss"
                        title="이 단어들을 맞는 표기로 등록(다음부터 교정 제외)"
                        onClick={() => {
                          c.errors.forEach(e => { if (chatId) addGlossaryTerm(chatId, e.original).catch(() => { }); });
                          onSkipCorrection?.(c.id);
                        }}
                      >넘기기</button>
                    </div>
                  ))
                ) : (
                  corrections.map(e => (
                    <div key={e.key} className={`memo-proof__card${e.applied ? ' memo-proof__card--applied' : ''}`}>
                      <div className={`memo-proof__err${e.frequent ? ' memo-proof__err--frequent' : ''}`}>
                        <span className="memo-proof__wrong">{e.original}</span>
                        <span className="memo-proof__arrow">→</span>
                        <span className="memo-proof__right">{e.corrected}</span>
                        <span className="memo-proof__type">{e.type}</span>
                        {e.frequent && <span className="memo-proof__freq">자주 틀림 {e.count}회</span>}
                      </div>
                      <div className="memo-proof__actions">
                        {e.applied ? (
                          <span className="memo-proof__done">✓ 적용완료</span>
                        ) : (
                          <>
                            <button className="memo-proof__apply" onClick={() => onApplyCorrection?.(e.key, e.original, e.corrected)}>적용</button>
                            <button
                              className="memo-proof__skip"
                              title="이 단어를 맞는 표기로 등록(다음부터 교정 제외)"
                              onClick={() => { if (chatId) addGlossaryTerm(chatId, e.original).catch(() => { }); onSkipCorrection?.(e.key); }}
                            >넘기기</button>
                          </>
                        )}
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          ) : (
            /* 메모 뷰 */
            <div className="memo-view">
              <div className="memo-view__header">
                <span>🗒️ 메모</span>
                <button className="memo-view__back" onClick={() => setPanelView('author')}>← 돌아가기</button>
              </div>

              {/* chat: 책갈피 입력 (말풍선 우클릭 → openMemoFor로만 열림) */}
              {mode === 'chat' && selectedMsgId && bookmarkMode && (
                <div className="memo-context">
                  <div className="memo-context__header">
                    <span className="memo-context__label">🔖 책갈피</span>
                    <button className="memo-context__clear" onClick={() => { onSelectedMsgIdChange?.(null); setEditingMemoId(null); setMemoInput(''); setBookmarkMode(false); }}>×</button>
                  </div>
                  <textarea
                    ref={memoInputRef}
                    className="memo-input memo-context__input"
                    placeholder="메모 작성..."
                    value={memoInput}
                    rows={3}
                    onChange={e => setMemoInput(e.target.value)}
                    onKeyDown={e => {
                      if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); handleAddMemo(); }
                    }}
                  />
                  <button className="memo-context__save" onClick={handleAddMemo}>
                    {editingMemoId ? '수정' : '저장'}
                  </button>
                </div>
              )}

              <div className="memo-view__list">
                {memos.length === 0 && (
                  <p className="author-chat__empty">
                    메모가 없어요<br />
                    {mode === 'chat' ? '말풍선을 우클릭해 추가하세요' : ''}
                  </p>
                )}
                {memos.map(memo => (
                  <div
                    key={memo.id}
                    className={`memo-item memo-item--${memo.type}${memo.msgId ? ' memo-item--bookmark' : ''}${editingMemoId === memo.id ? ' memo-item--editing' : ''}`}
                    onClick={memo.msgId ? () => onMemoClick?.(memo) : undefined}
                  >
                    {memo.msgId && <p className="memo-item__ref">🔖 책갈피</p>}
                    <div className="memo-item__body">
                      <span>{memo.text}</span>
                      <button
                        className="memo-item__edit"
                        onClick={e => {
                          e.stopPropagation();
                          setEditingMemoId(memo.id);
                          setMemoInput(memo.text);
                          onSelectedMsgIdChange?.(null);
                          setTimeout(() => memoInputRef.current?.focus(), 80);
                        }}
                      >✎</button>
                      <button
                        className="memo-item__delete"
                        onClick={e => { e.stopPropagation(); onMemosChange(memos.filter(m => m.id !== memo.id)); }}
                      >×</button>
                    </div>
                  </div>
                ))}
              </div>

              {/* editor: 단순 메모 추가 / chat: selectedMsgId 없을 때 추가 */}
              {(mode === 'editor' || !selectedMsgId) && (
                <div className="memo-add">
                  <textarea
                    ref={memoInputRef}
                    className="memo-input"
                    placeholder={editingMemoId ? '메모 수정...' : '메모 추가...'}
                    value={memoInput}
                    rows={2}
                    onChange={e => setMemoInput(e.target.value)}
                    onKeyDown={e => {
                      if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); handleAddMemo(); }
                    }}
                  />
                  {editingMemoId && (
                    <button className="memo-add-btn memo-add-btn--cancel" onClick={() => { setEditingMemoId(null); setMemoInput(''); }}>취소</button>
                  )}
                  <button className="memo-add-btn" onClick={handleAddMemo}>{editingMemoId ? '수정' : '+'}</button>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* 추천/피드백 컨텍스트 메뉴 */}
      {recContextMenu.visible && (
        <div
          className={mode === 'chat' ? 'context-menu' : 'rec-context-menu'}
          style={{ top: recContextMenu.y, left: recContextMenu.x }}
          onClick={e => e.stopPropagation()}
        >
          {!recContextMenu.copyOnly && (
            <button
              className={mode === 'chat' ? 'context-menu__item' : 'rec-context-menu__item'}
              onClick={() => { onApplyText?.(recContextMenu.content); setRecContextMenu(m => ({ ...m, visible: false })); }}
            >적용하기</button>
          )}
          {mode === 'chat' && (
            <button
              className="context-menu__item"
              onClick={() => { navigator.clipboard.writeText(recContextMenu.content); setRecContextMenu(m => ({ ...m, visible: false })); }}
            >복사</button>
          )}
        </div>
      )}
    </div>
  );
});

export default AuthorPanel;
