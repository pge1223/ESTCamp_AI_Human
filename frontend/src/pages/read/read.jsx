import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import { getNovel, generateNovel } from '../../lib/chatApi';
import { toast } from '../../lib/toast';
import { getSession, getWorld } from '../../lib/worldviewApi';
import { useAuthorTheme, resolveAuthorId } from '../../hooks/useAuthorTheme';
import LoadingVideo from '../../components/loadingVideo';
import { getIllustrationScenes, generateIllustration, generateIllustrationOpenAI, listIllustrations, createIllustration, removeIllustration } from '../../lib/illustrationApi';
import './read.css';

const CHAPTER_SIZE = 5;

const AUTHOR_NAME = {
  1: '백야',
  2: '차로운',
  3: '한여름',
  4: '김도현',
};

function parseChapters(content) {
  if (!content) return [];
  const paragraphs = content.split(/\n\n+/).filter(p => p.trim());
  const chapters = [];
  for (let i = 0; i < paragraphs.length; i += CHAPTER_SIZE) {
    const num = chapters.length + 1;
    chapters.push({
      idx: chapters.length,
      title: `제 ${num}장`,
      paragraphs: paragraphs.slice(i, i + CHAPTER_SIZE),
    });
  }
  if (chapters.length === 0 && paragraphs.length > 0) {
    chapters.push({ idx: 0, title: '제 1장', paragraphs });
  }
  return chapters;
}

function formatDate(iso) {
  const d = new Date(iso);
  return `${d.getFullYear()}. ${d.getMonth() + 1}. ${d.getDate()}.`;
}

const STYLE_OPTIONS = [
  { key: 'webtoon', label: '웹소설 표지풍' },
  { key: 'watercolor', label: '수채화풍' },
  { key: 'ink', label: '흑백 일러스트' },
  { key: 'realistic', label: '실사풍' },
  { key: 'pastel', label: '파스텔풍' },
];
const MOOD_OPTIONS = [
  { key: 'warm', label: '따뜻함' },
  { key: 'dark', label: '어두움' },
  { key: 'dreamy', label: '몽환적' },
  { key: 'tense', label: '긴장감' },
  { key: 'romantic', label: '로맨틱' },
];
const RATIO_OPTIONS = [
  { key: '1:1', label: '정사각형' },
  { key: '9:16', label: '세로형 (표지)' },
  { key: '16:9', label: '가로형' },
];

export default function ReadNovel() {
  const { storyId } = useParams();
  const navigate = useNavigate();
  const location = useLocation();

  const [novel, setNovel] = useState(null);
  const [session, setSession] = useState(null);
  const [world, setWorld] = useState(null);
  const [error, setError] = useState(null);
  const [fontSize, setFontSize] = useState(16);
  const [fontPanelOpen, setFontPanelOpen] = useState(false);
  const [bookmarked, setBookmarked] = useState(false);
  const [progress, setProgress] = useState(0);
  const [showScrollTop, setShowScrollTop] = useState(false);
  const [activeChapter, setActiveChapter] = useState(0);
  const [loading, setLoading] = useState(true);
  const [showLoading, setShowLoading] = useState(true);
  const [regenerating, setRegenerating] = useState(false);

  // ── 저장된 삽화(이 소설) — DB 영속(기기/계정 무관) ────────────────
  const [savedIllus, setSavedIllus] = useState([]);   // [{id, image_url, caption, created_at}]
  const [savingIllus, setSavingIllus] = useState(false);   // 저장 중 표시(base64 업로드 지연)
  const [lightbox, setLightbox] = useState(null);     // {url, caption} | null

  useEffect(() => {
    if (!storyId) return;
    listIllustrations(storyId).then(d => setSavedIllus(d.illustrations || [])).catch(() => { });
  }, [storyId]);

  async function saveIllustration(url, caption) {
    if (!url || savingIllus) return;
    setSavingIllus(true);
    try {
      const saved = await createIllustration(storyId, { image_url: url, caption: caption || '' });
      setSavedIllus(prev => [saved, ...prev]);
      toast('내 삽화에 저장했어요.', 'success');
      setIllusOpen(false);   // 저장 완료 후 모달 닫기
    } catch {
      toast('삽화 저장에 실패했어요.', 'error');
    } finally {
      setSavingIllus(false);
    }
  }

  async function deleteIllustration(id) {
    setSavedIllus(prev => prev.filter(it => it.id !== id));
    try { await removeIllustration(storyId, id); } catch { }
  }

  // ── 삽화 생성 모달 상태 ───────────────────────────────────────────
  const [illusOpen, setIllusOpen] = useState(false);
  const [illusStep, setIllusStep] = useState('mode'); // mode|direct|recommend|style|generating|result|refine|blocked
  const [sceneInput, setSceneInput] = useState('');
  const [illusStyle, setIllusStyle] = useState('webtoon');
  const [illusMood, setIllusMood] = useState('warm');
  const [illusRatio, setIllusRatio] = useState('1:1');
  const [illusScenes, setIllusScenes] = useState([]);
  const [scenesLoading, setScenesLoading] = useState(false);
  const [selectedScene, setSelectedScene] = useState(null);
  const [illusResult, setIllusResult] = useState(null);

  function openIllus() {
    setIllusStep('mode'); setSceneInput(''); setSelectedScene(null);
    setIllusResult(null); setIllusScenes([]); setIllusOpen(true);
  }

  async function loadScenes() {
    setScenesLoading(true);
    try {
      const data = await getIllustrationScenes(storyId);
      setIllusScenes(data.scenes ?? []);
    } finally {
      setScenesLoading(false);
    }
  }

  const STYLE_TO_OPENAI = {
    webtoon: ['webtoon'], watercolor: ['watercolor'],
    ink: ['webtoon'], realistic: ['webtoon'], pastel: ['watercolor'],
  };
  const MOOD_TO_OPENAI = {
    warm: [], dark: ['fantasy'], dreamy: [], tense: ['fantasy'], romantic: ['romance'],
  };

  async function handleGenerateOpenAI(sceneDesc) {
    setIllusStep('generating');
    try {
      const styleNames = [...new Set([
        ...(STYLE_TO_OPENAI[illusStyle] ?? ['webtoon']),
        ...(MOOD_TO_OPENAI[illusMood] ?? []),
      ])];
      const data = await generateIllustrationOpenAI(storyId, styleNames, sceneDesc);
      setIllusResult({ status: 'generated', image_url: data.image_url });
      setIllusStep('result');
    } catch (err) {
      setIllusStep('blocked');
      setIllusResult({ block_reason: `[OpenAI] ${err.message || '이미지 생성 중 오류가 발생했어요.'}` });
    }
  }

  async function handleGenerate(sceneDesc, skipFilter = false) {
    setIllusStep('generating');
    try {
      const result = await generateIllustration(storyId, {
        scene_description: sceneDesc,
        style: illusStyle,
        mood: illusMood,
        ratio: illusRatio,
        skip_filter: skipFilter,
      });
      setIllusResult(result);
      if (result.status === 'generated') setIllusStep('result');
      else if (result.status === 'refine_needed') setIllusStep('refine');
      else setIllusStep('blocked');
    } catch {
      setIllusStep('blocked');
      setIllusResult({ block_reason: '이미지 생성 중 오류가 발생했어요. 다시 시도해주세요.' });
    }
  }

  const chapterRefs = useRef([]);

  // 작가별 테마: 세션 로드 후 session.author_id(진짜 값), 그 전엔 네비게이션으로 받은 authorId,
  // 둘 다 없을 때만 localStorage 폴백 → 직전 작가 색 깜빡임 방지
  useAuthorTheme(session?.author_id ?? location.state?.authorId ?? resolveAuthorId(null));

  useEffect(() => {
    async function load() {
      try {
        let novelData;
        try {
          novelData = await getNovel(storyId);
        } catch (err) {
          if (err.status === 404) {
            toast('소설을 생성하고 있어요...', 'info');
            try {
              await generateNovel(storyId);
              novelData = await getNovel(storyId);
            } catch (genErr) {
              throw new Error(genErr.message || '소설을 생성할 수 없어요.');
            }
          } else {
            throw err;
          }
        }
        const sessionData = await getSession(storyId);
        setNovel(novelData);
        setSession(sessionData);
        const worldData = await getWorld(sessionData.world_id);
        setWorld(worldData);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [storyId]);

  useEffect(() => {
    const saved = localStorage.getItem(`bookmark_${storyId}`);
    setBookmarked(saved === 'true');
  }, [storyId]);

  const handleScroll = useCallback(() => {
    const scrollTop = window.scrollY;
    const docH = document.documentElement.scrollHeight - window.innerHeight;
    const pct = docH > 0 ? Math.round((scrollTop / docH) * 100) : 0;
    setProgress(pct);
    setShowScrollTop(scrollTop > 300);
    chapterRefs.current.forEach((el, i) => {
      if (el && el.getBoundingClientRect().top < 120) setActiveChapter(i);
    });
  }, []);

  useEffect(() => {
    window.addEventListener('scroll', handleScroll);
    return () => window.removeEventListener('scroll', handleScroll);
  }, [handleScroll]);

  const scrollToChapter = (idx) => {
    chapterRefs.current[idx]?.scrollIntoView({ behavior: 'smooth' });
    setActiveChapter(idx);
  };

  const scrollToTop = () => window.scrollTo({ top: 0, behavior: 'smooth' });

  const handleRegenerate = async () => {
    setRegenerating(true);
    try {
      const fresh = await generateNovel(storyId);
      setNovel(fresh);
      if (!(fresh?.content || '').trim()) {
        toast('대화가 짧아 변환할 내용이 부족해요. 이어쓰기로 대화를 더 진행해보세요.', 'info');
      } else {
        toast('소설로 변환했어요.', 'success');
      }
    } catch {
      toast('소설 변환에 실패했어요. 잠시 후 다시 시도해주세요.', 'error');
    } finally {
      setRegenerating(false);
    }
  };

  const handleExport = () => {
    if (!novel) return;
    const blob = new Blob([novel.content], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${novel.title}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  };

  if (!loading && (error || !novel)) {
    return (
      <div className="read-page">
        <div className="read-empty">
          <p>{error ?? '소설을 찾을 수 없습니다.'}</p>
          <button onClick={() => navigate('/storylist')}>목록으로</button>
        </div>
      </div>
    );
  }

  const savedOpening = localStorage.getItem('opening_' + storyId) || '';
  const novelBody = novel?.content ?? '';
  const content = (savedOpening && novelBody.trim())
    ? savedOpening + '\n\n' + novelBody
    : novelBody;
  if (!loading && novel && !content.trim()) {
    return (
      <div className="read-page">
        <div className="read-empty">
          <p>아직 변환된 소설 본문이 없어요.</p>
          <p className="read-empty__sub">대화를 조금 더 진행하거나 다시 변환해보세요.</p>
          <div className="read-empty__actions">
            <button className="read-empty__btn read-empty__btn--primary" onClick={handleRegenerate} disabled={regenerating}>
              {regenerating ? '변환 중…' : '다시 변환'}
            </button>
            <button className="read-empty__btn" onClick={() => navigate('/chat', { state: { chatId: storyId } })}>
              이어쓰기
            </button>
            <button className="read-empty__btn" onClick={() => navigate('/storylist')}>
              목록으로
            </button>
          </div>
        </div>
      </div>
    );
  }
  const chapters = parseChapters(content);
  const singleMode = chapters.length <= 1;   // 장이 하나뿐(단락 ≤5)이면 장 구분/목차 숨기고 본문만
  const wordCount = content.replace(/\s+/g, '').length;
  const readingMins = Math.max(1, Math.ceil(wordCount / 350));

  // ── 삽화 모달 렌더 ──────────────────────────────────────────────────
  const illusModal = illusOpen && (
    <div className="illus-overlay" onClick={() => setIllusOpen(false)}>
      <div className="illus-modal" onClick={e => e.stopPropagation()}>

        {/* 모드 선택 */}
        {illusStep === 'mode' && (
          <>
            <h2 className="illus-title">✨ 삽화 생성</h2>
            <p className="illus-desc">소설 속 장면을 이미지로 만들어 드려요.</p>
            <div className="illus-mode-row">
              <button className="illus-mode-card" onClick={() => setIllusStep('direct')}>
                <span className="illus-mode-icon">✏️</span>
                <strong>직접 입력</strong>
                <span>원하는 장면을 직접 설명하기</span>
              </button>
              <button className="illus-mode-card" onClick={() => { setIllusStep('recommend'); loadScenes(); }}>
                <span className="illus-mode-icon">🔮</span>
                <strong>AI 추천</strong>
                <span>소설에서 어울리는 장면 추천받기</span>
              </button>
            </div>
            <button className="illus-close-btn" onClick={() => setIllusOpen(false)}>닫기</button>
          </>
        )}

        {/* 직접 입력 */}
        {illusStep === 'direct' && (
          <>
            <button className="illus-back" onClick={() => setIllusStep('mode')}>← 뒤로</button>
            <h2 className="illus-title">원하는 장면을 설명해주세요</h2>
            <textarea
              className="illus-textarea"
              placeholder={"예) 비 오는 골목에서 주인공이 혼자 우산을 들고 서 있는 장면\n예) 남주가 여주 몰래 편지를 숨기는 장면"}
              value={sceneInput}
              onChange={e => setSceneInput(e.target.value)}
              rows={4}
            />
            <StylePicker
              style={illusStyle} setStyle={setIllusStyle}
              mood={illusMood} setMood={setIllusMood}
              ratio={illusRatio} setRatio={setIllusRatio}
            />
            <div className="illus-generate-row">
              <button
                className="illus-btn-primary"
                disabled={!sceneInput.trim()}
                onClick={() => handleGenerate(sceneInput.trim())}
              >Gemini로 생성</button>
              <button
                className="illus-btn-openai"
                disabled={!sceneInput.trim()}
                onClick={() => handleGenerateOpenAI(sceneInput.trim())}
              >OpenAI로 생성</button>
            </div>
          </>
        )}

        {/* AI 추천 — 장면 목록 */}
        {illusStep === 'recommend' && (
          <>
            <button className="illus-back" onClick={() => setIllusStep('mode')}>← 뒤로</button>
            <h2 className="illus-title">삽화 후보 장면</h2>
            {scenesLoading ? (
              <p className="illus-loading">소설을 분석하고 있어요...</p>
            ) : (
              <div className="illus-scene-list">
                {illusScenes.map((sc, i) => (
                  <button
                    key={i}
                    className={`illus-scene-card${selectedScene === i ? ' active' : ''}`}
                    onClick={() => { setSelectedScene(i); setSceneInput(sc.description); setIllusStep('style'); }}
                  >
                    <span className="illus-scene-label">{sc.label}</span>
                    <p className="illus-scene-desc">{sc.description}</p>
                    {sc.visual && <p className="illus-scene-visual">{sc.visual}</p>}
                  </button>
                ))}
                {!scenesLoading && illusScenes.length === 0 && (
                  <p className="illus-empty">소설 내용을 불러올 수 없어요.</p>
                )}
              </div>
            )}
          </>
        )}

        {/* 스타일 선택 (추천 모드에서 장면 고른 후) */}
        {illusStep === 'style' && (
          <>
            <button className="illus-back" onClick={() => setIllusStep('recommend')}>← 뒤로</button>
            <h2 className="illus-title">스타일을 선택해주세요</h2>
            <p className="illus-selected-scene">{sceneInput}</p>
            <StylePicker
              style={illusStyle} setStyle={setIllusStyle}
              mood={illusMood} setMood={setIllusMood}
              ratio={illusRatio} setRatio={setIllusRatio}
            />
            <div className="illus-generate-row">
              <button
                className="illus-btn-primary"
                onClick={() => handleGenerate(sceneInput, true)}
              >Gemini로 생성</button>
              <button
                className="illus-btn-openai"
                onClick={() => handleGenerateOpenAI(sceneInput)}
              >OpenAI로 생성</button>
            </div>
          </>
        )}

        {/* 생성 중 */}
        {illusStep === 'generating' && (
          <div className="illus-generating">
            <div className="illus-spinner" />
            <p>이미지를 그리고 있어요...</p>
            <span>잠시만 기다려 주세요 (10~30초)</span>
          </div>
        )}

        {/* 결과 */}
        {illusStep === 'result' && illusResult && (
          <>
            <h2 className="illus-title">✨ 삽화 완성!</h2>
            <img className="illus-result-img" src={illusResult.image_url} alt="생성된 삽화" />
            <div className="illus-result-actions">
              <button
                className="illus-btn-primary"
                onClick={() => saveIllustration(illusResult.image_url, sceneInput)}
                disabled={savingIllus}
              >{savingIllus ? '삽화 저장 중…' : '저장하기'}</button>
              <button className="illus-btn-secondary" onClick={() => setIllusStep('mode')} disabled={savingIllus}>다시 만들기</button>
              <button className="illus-btn-secondary" onClick={() => setIllusOpen(false)} disabled={savingIllus}>닫기</button>
            </div>
          </>
        )}

        {/* 수정 제안 */}
        {illusStep === 'refine' && illusResult && (
          <>
            <h2 className="illus-title">⚠ 장면을 조금 수정했어요</h2>
            <p className="illus-refine-text">{illusResult.suggestion}</p>
            <div className="illus-result-actions">
              <button
                className="illus-btn-primary"
                onClick={() => handleGenerate(illusResult.refined_prompt, true)}
              >수정안으로 생성하기</button>
              <button className="illus-btn-secondary" onClick={() => setIllusStep('mode')}>다시 입력</button>
            </div>
          </>
        )}

        {/* 차단 */}
        {illusStep === 'blocked' && illusResult && (
          <>
            <h2 className="illus-title">🚫 생성할 수 없어요</h2>
            <p className="illus-block-text">{illusResult.block_reason ?? '이 장면으로는 삽화를 만들기 어려워요.'}</p>
            <button className="illus-btn-secondary" onClick={() => setIllusStep('mode')}>다시 시도</button>
          </>
        )}

      </div>
    </div>
  );

  return (
    <div className="read-page" onClick={() => setFontPanelOpen(false)}>
      {showLoading && (
        <LoadingVideo
          loading={loading}
          onFinish={() => setShowLoading(false)}
        />
      )}

      <div className="read-top-bar">
        <div className="read-top-bar__left">
          <button className="read-back-btn" onClick={() => (window.history.length > 1 ? navigate(-1) : navigate('/storylist'))}>
            ← 돌아가기
          </button>
          <span className="read-doc-title">{novel?.title ?? ''}</span>
        </div>
        <div className="read-top-bar__right" onClick={e => e.stopPropagation()}>
          <div style={{ position: 'relative' }}>
            <button
              className="read-icon-btn"
              title="글자 크기"
              onClick={() => setFontPanelOpen(p => !p)}
            >
              Aa
            </button>
            {fontPanelOpen && (
              <div className="read-font-panel">
                <div className="read-font-panel__label">글자 크기</div>
                <div className="read-font-size-row">
                  <button
                    className="read-fs-btn"
                    style={{ fontSize: '13px' }}
                    onClick={() => setFontSize(f => Math.max(14, f - 1))}
                  >A</button>
                  <span className="read-fs-val">{fontSize}px</span>
                  <button
                    className="read-fs-btn"
                    style={{ fontSize: '18px' }}
                    onClick={() => setFontSize(f => Math.min(20, f + 1))}
                  >A</button>
                </div>
              </div>
            )}
          </div>
          <button
            className={`read-icon-btn${bookmarked ? ' read-icon-btn--active' : ''}`}
            title="북마크"
            onClick={() => {
              const next = !bookmarked;
              setBookmarked(next);
              localStorage.setItem(`bookmark_${storyId}`, String(next));
            }}
          >
            {bookmarked ? '★' : '☆'}
          </button>
          <button className="read-export-btn" onClick={handleExport}>
            ↓ 내보내기
          </button>
          <button className="read-illus-btn" onClick={openIllus}>
            ✨ 삽화 생성
          </button>
        </div>
      </div>

      {/* 읽기 진행률 — position:fixed 로 뷰포트 최상단 고정(상위 overflow-x:hidden 으로 sticky가 깨져 fixed 사용). 스크롤해도 항상 보임 */}
      <div className="read-progress-fixed">
        <div className="read-progress-fixed__fill" style={{ width: `${progress}%` }} />
      </div>

      <div className="read-layout">
        <aside className="read-sidebar">
          {!singleMode && (
            <>
              <div className="read-sidebar__label">목차</div>
              {chapters.map((ch, i) => (
                <div
                  key={i}
                  className={`read-toc-item${activeChapter === i ? ' read-toc-item--active' : ''}`}
                  onClick={() => scrollToChapter(i)}
                >
                  <span className="read-toc-num">{i + 1}</span>
                  <span className="read-toc-text">{ch.title}</span>
                </div>
              ))}

              <div className="read-sidebar__divider" />
            </>
          )}

          <div className="read-sidebar__label">작품 정보</div>
          <div className="read-meta-row">
            <span>AI 작가</span>
            <span className="read-meta-val">{AUTHOR_NAME[session?.author_id] ?? '—'}</span>
          </div>
          <div className="read-meta-row">
            <span>장르</span>
            <span className="read-meta-val">{world?.genre ?? '—'}</span>
          </div>
          <div className="read-meta-row">
            <span>총 글자</span>
            <span className="read-meta-val">{wordCount.toLocaleString()}자</span>
          </div>
          <div className="read-meta-row">
            <span>예상 읽기</span>
            <span className="read-meta-val">약 {readingMins}분</span>
          </div>
          <div className="read-meta-row">
            <span>작성일</span>
            <span className="read-meta-val">{novel?.created_at ? formatDate(novel.created_at) : '—'}</span>
          </div>
        </aside>

        <main className="read-main-content">
          <div className="read-novel-cover">
            <div className="read-persona-badge">
              <span className="read-persona-badge__dot" />
              AI 작가 {AUTHOR_NAME[session?.author_id] ?? 'AI'}
            </div>
            <h1 className="read-novel-title">{novel?.title ?? ''}</h1>
            {world?.description && (
              <p className="read-novel-subtitle">
                {world.description.length > 60
                  ? world.description.slice(0, 60) + '…'
                  : world.description}
              </p>
            )}
            <div className="read-cover-meta">
              {world?.genre && <><span>{world.genre}</span><span className="read-cover-meta__div">·</span></>}
              <span>단편</span>
              <span className="read-cover-meta__div">·</span>
              <span>{wordCount.toLocaleString()}자</span>
            </div>
            <div className="read-progress-wrap">
              <div className="read-progress-fill" style={{ width: `${progress}%` }} />
            </div>
            <div className="read-progress-label">{progress}% 읽음</div>
          </div>

          {singleMode ? (
            <div
              className="read-chapter read-chapter--single"
              ref={el => { chapterRefs.current[0] = el; }}
            >
              <div className="read-chapter__body" style={{ fontSize: `${fontSize}px` }}>
                {(chapters[0]?.paragraphs ?? []).map((para, j) => (
                  <p key={j}>{para}</p>
                ))}
              </div>
            </div>
          ) : (
            chapters.map((ch, i) => (
              <div
                key={i}
                className="read-chapter"
                id={`ch-${i}`}
                ref={el => { chapterRefs.current[i] = el; }}
              >
                <div className="read-chapter__header">
                  <div className="read-chapter__num">Chapter {String(i + 1).padStart(2, '0')}</div>
                  <h2 className="read-chapter__title">{ch.title}</h2>
                  <div className="read-chapter__divider" />
                </div>
                <div className="read-chapter__body" style={{ fontSize: `${fontSize}px` }}>
                  {ch.paragraphs.map((para, j) => (
                    <p key={j}>{para}</p>
                  ))}
                </div>
              </div>
            ))
          )}

          <div className="read-end-card">
            <div className="read-end-symbol">— 끝 —</div>
            <p className="read-end-text">
              이 소설은 AI 작가 <strong>{AUTHOR_NAME[session?.author_id] ?? 'AI'}</strong>와 함께 작성되었습니다.
            </p>
            <div className="read-end-actions">
              <button
                className="read-end-btn read-end-btn--primary"
                onClick={() => navigate('/chat', { state: { chatId: storyId } })}
              >
                이어쓰기
              </button>
              <button
                className="read-end-btn read-end-btn--secondary"
                onClick={() => navigate('/')}
              >
                새 소설 시작
              </button>
            </div>
          </div>
        </main>

        <aside className="read-illus-panel">
          <div className="read-illus-panel__head">
            <span className="read-sidebar__label">삽화</span>
            {savedIllus.length > 0 && <span className="read-illus-count">{savedIllus.length}</span>}
          </div>
          {savedIllus.length === 0 ? (
            <p className="read-illus-empty">아직 삽화가 없어요.<br />상단 <b>✨ 삽화 생성</b>으로<br />장면을 그려보세요.</p>
          ) : (
            <div className="read-illus-list">
              {savedIllus.map(it => (
                <div className="read-illus-item" key={it.id}>
                  <img
                    src={it.image_url}
                    alt={it.caption || '삽화'}
                    onClick={() => setLightbox({ url: it.image_url, caption: it.caption })}
                  />
                  <button className="read-illus-del" title="삭제" onClick={() => deleteIllustration(it.id)}>✕</button>
                </div>
              ))}
            </div>
          )}
        </aside>
      </div>

      {lightbox && (
        <div className="read-lightbox" onClick={() => setLightbox(null)}>
          <div className="read-lightbox__inner" onClick={e => e.stopPropagation()}>
            <img src={lightbox.url} alt="삽화 확대" />
            {lightbox.caption && <p className="read-lightbox__caption">{lightbox.caption}</p>}
          </div>
          <button className="read-lightbox__close" onClick={() => setLightbox(null)}>✕</button>
        </div>
      )}
      {showScrollTop && (
        <button
          className="read-scroll-top"
          onClick={(e) => { e.stopPropagation(); scrollToTop(); }}
          title="맨 위로"
          aria-label="맨 위로"
        >↑</button>
      )}
      {illusModal}
    </div>
  );
}

function StylePicker({ style, setStyle, mood, setMood, ratio, setRatio }) {
  return (
    <div className="illus-style-picker">
      <div className="illus-picker-row">
        <span className="illus-picker-label">그림체</span>
        <div className="illus-chip-group">
          {STYLE_OPTIONS.map(o => (
            <button key={o.key} className={`illus-chip${style === o.key ? ' active' : ''}`} onClick={() => setStyle(o.key)}>{o.label}</button>
          ))}
        </div>
      </div>
      <div className="illus-picker-row">
        <span className="illus-picker-label">분위기</span>
        <div className="illus-chip-group">
          {MOOD_OPTIONS.map(o => (
            <button key={o.key} className={`illus-chip${mood === o.key ? ' active' : ''}`} onClick={() => setMood(o.key)}>{o.label}</button>
          ))}
        </div>
      </div>
      <div className="illus-picker-row">
        <span className="illus-picker-label">비율</span>
        <div className="illus-chip-group">
          {RATIO_OPTIONS.map(o => (
            <button key={o.key} className={`illus-chip${ratio === o.key ? ' active' : ''}`} onClick={() => setRatio(o.key)}>{o.label}</button>
          ))}
        </div>
      </div>
    </div>
  );
}
