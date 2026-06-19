import React, { useEffect, useState, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { getSessions, deleteSession, getDialogues } from '../../lib/worldviewApi';
import { completeSession, generateNovel } from '../../lib/chatApi';
import { useAuthorTheme, resolveAuthorId } from '../../hooks/useAuthorTheme';
import { toast } from '../../lib/toast';
import './storylist.css';
import LoadingVideo from '../../components/loadingVideo';

const STATUS_LABEL = {
  active: '진행 중',
  paused: '일시정지',
  completed: '완료',
};

const AUTHOR_NAME = {
  1: '백야',
  2: '차로운',
  3: '한여름',
  4: '김도현',
};

function GenreTags({ genre }) {
  if (!genre) return null;
  const tags = genre.split(/[,/]/).map(t => t.trim()).filter(Boolean);
  return (
    <div className="storylist-card__tags">
      {tags.map(tag => <span key={tag} className="genre-tag">#{tag}</span>)}
    </div>
  );
}

function formatDate(iso) {
  const d = new Date(iso);
  return `${d.getFullYear()}.${String(d.getMonth() + 1).padStart(2, '0')}.${String(d.getDate()).padStart(2, '0')}`;
}

export default function StoryList() {
  const navigate = useNavigate();
  const [sessions, setSessions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showLoading, setShowLoading] = useState(true);
  const [loaded, setLoaded] = useState(false);   // 성공적으로 불러왔는지 — 에러/미인증과 '작품 없음'을 구분
  const [error, setError] = useState(false);
  const retriedRef = useRef(false);
  useAuthorTheme(null); // 목록 페이지는 작가 테마 변경 없음 — BGM 유지

  // 인증 미준비(null userId→422)·DB 콜드스타트(에러/지연)를 '작품 없음'으로 오인하지 않도록:
  // 실패하면 1회 자동 재시도(로딩 유지), 그래도 실패면 에러 안내(다시 시도) — 빈 상태는 '성공+0건'일 때만.
  const load = useCallback(async (isRetry = false) => {
    if (!isRetry) { setLoading(true); setError(false); }
    try {
      const data = await getSessions();
      setSessions(data);
      setLoaded(true);
      setLoading(false);
    } catch (e) {
      console.error(e);
      if (!retriedRef.current) {
        retriedRef.current = true;
        setTimeout(() => load(true), 1500);   // 로딩 유지한 채 1.5s 후 1회 재시도
      } else {
        setError(true);
        setLoading(false);
      }
    }
  }, []);

  const retry = () => { retriedRef.current = false; setError(false); load(); };

  useEffect(() => { load(); }, [load]);

  const handleResume = (session) => {
    if (session.status === 'completed') {
      navigate('/editor', { state: { chatId: session.id, authorId: session.author_id } });
      return;
    }
    const mode = localStorage.getItem(`session_mode_${session.id}`) ?? 'chat';
    const dest = mode === 'editor' ? '/editor' : '/chat';
    navigate(dest, { state: { chatId: session.id, authorId: session.author_id } });
  };

  const handleRead = (session) => {
    // 작가 테마 즉시 적용 위해 authorId 전달(없으면 read가 직전 작가 색으로 깜빡임)
    navigate(`/read/${session.id}`, { state: { authorId: session.author_id } });
  };

  const handleEditWorld = (session) => {
    navigate('/worldedit', {
      state: { worldId: session.world_id, chatId: session.id, authorId: session.author_id },
    });
  };

  const handleComplete = async (session) => {
    if (!window.confirm(`"${session.world_title}" 소설을 완결내시겠습니까?\n완결 후에는 이어쓰기가 불가합니다.`)) return;
    try {
      const dialogues = await getDialogues(session.id);
      if (!dialogues || dialogues.length === 0) {
        toast('대화 내용이 없어 완결할 수 없어요.', 'error');
        return;
      }
      await completeSession(session.id);
      try {
        await generateNovel(session.id);
        setSessions(prev => prev.map(s => s.id === session.id ? { ...s, status: 'completed', has_novel: true } : s));
        toast('완결되었습니다! 읽기를 눌러 감상해보세요 🎉');
      } catch {
        setSessions(prev => prev.map(s => s.id === session.id ? { ...s, status: 'completed' } : s));
        toast('완결됐지만 소설 생성에 실패했어요.', 'error');
      }
    } catch (err) {
      toast(`완결 처리 실패: ${err.message}`, 'error');
    }
  };

  const handleDelete = async (session) => {
    if (!window.confirm(`"${session.world_title}" 세션을 삭제할까요?\n이 작업은 되돌릴 수 없습니다.`)) return;
    try {
      await deleteSession(session.id);
      setSessions(prev => prev.filter(s => s.id !== session.id));
    } catch (err) {
      toast(`삭제 실패: ${err.message}`, "error");
    }
  };

  return (
    <div className="storylist-container">
      {showLoading && (
        <LoadingVideo
          loading={loading}
          onFinish={() => setShowLoading(false)}
        />
      )}

      <div className="storylist-wrapper">
        <header className="storylist-header">
          <button className="storylist-back-btn" onClick={() => (window.history.length > 1 ? navigate(-1) : navigate('/'))}>‹</button>
          <h2 className="storylist-title">내 소설 목록</h2>
          <div className="storylist-header__actions">
            <button className="back-btn" onClick={() => navigate('/')}>← 메인화면</button>
            <button className="back-btn storylist-mypage-btn" onClick={() => navigate('/mypage')}>📚 내 서재</button>
          </div>
        </header>

        {!loading && error && (
          <p className="storylist-empty">
            목록을 불러오지 못했어요.<br />
            <button className="back-btn" style={{ marginTop: 12 }} onClick={retry}>다시 시도</button>
          </p>
        )}

        {!loading && loaded && sessions.length === 0 && (
          <p className="storylist-empty">아직 작성한 소설이 없어요.<br />작가를 선택해 첫 세계관을 만들어보세요.</p>
        )}

        <div className="storylist-grid">
          {sessions.map((s) => (
            <div key={s.id} className="storylist-card">
              <div className="storylist-card__body">
                <h3 className="storylist-card__title">{s.world_title}</h3>
                <GenreTags genre={s.world_genre} />
                <div className="storylist-card__meta">
                  <span className={`status-badge status-badge--${s.status}`}>
                    {STATUS_LABEL[s.status] ?? s.status}
                  </span>
                  {s.author_id && (
                    <span className="storylist-card__author">✒ {AUTHOR_NAME[s.author_id]}</span>
                  )}
                  <span className="storylist-card__date">{formatDate(s.started_at)}</span>
                </div>
              </div>
              <div style={{ display: 'flex', gap: '8px' }}>
                <button className="storylist-card__btn" onClick={() => handleResume(s)}>
                  {s.status === 'completed' ? '수정하기' : '이어쓰기 →'}
                </button>
                {s.status === 'completed' && s.has_novel && (
                  <button className="storylist-card__btn storylist-card__btn--read" onClick={() => handleRead(s)}>
                    읽기
                  </button>
                )}
                {s.status !== 'completed' && (
                  <button className="storylist-card__btn storylist-card__btn--complete" onClick={() => handleComplete(s)}>
                    완결
                  </button>
                )}
                <button className="storylist-card__btn storylist-card__btn--delete" onClick={() => handleDelete(s)}>
                  삭제
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>

    </div>
  );
}
