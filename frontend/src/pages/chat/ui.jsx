// frontend/src/pages/chat/ui.jsx
import React, { useState, useEffect, useRef } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import ReactMarkdown from 'react-markdown';
import {
  sendMessage, connectChatStream, completeSession, restartSession, generateNovel, convertToNovel,
  getSuggestions, getVoiceSuggestions, getAuthorReaction, proofread,
  getErrorWarmup, deleteMessage, setGenreOpen,
} from '../../lib/chatApi';
import { getVoiceProfile } from '../../lib/voiceApi';
import { speakReaction, stopReaction, extractFirstSentence } from '../../lib/ttsApi';
import { getSession, getWorld, getCharacters, getDialogues } from '../../lib/worldviewApi';
import { generateOpeningScene } from '../../lib/openingSceneApi';
import { useAuthorTheme, resolveAuthorId } from '../../hooks/useAuthorTheme';
import { authClient } from '../../lib/auth';
import { toast } from '../../lib/toast';
import AuthorPanel from '../../components/AuthorPanel';
import './ui.css';

const AUTHOR_IDS = [1, 2, 3, 4];

const AUTHOR_MAP = {
  1: { characterId: 'baekya', displayName: '백야', image: '/assets/author1/author1.png' },
  2: { characterId: 'charoun', displayName: '차로운', image: '/assets/author2/author2.png' },
  3: { characterId: 'hanyeoreum', displayName: '한여름', image: '/assets/author3/author3.png' },
  4: { characterId: 'kimdohyeon', displayName: '김도현', image: '/assets/author4/author4.png' },
};

const DEMO_REACTIONS = {
  '/start': {
    emotion: 'start',
    reactions: {
      charoun: '좋은 출발입니다.',
      hanyeoreum: '벌써 기대되는데요?',
      baekya: '흥미롭군요.',
      kimdohyeon: '이야기가 움직이기 시작했어요.',
    },
  },
  '/tension': {
    emotion: 'tension',
    reactions: {
      charoun: '그건 생각 못 했군요.',
      hanyeoreum: '흥미로운데요?',
      baekya: '그렇게 흘러가나요.',
      kimdohyeon: '조금 의외인데요?',
    },
  },
  '/joy': {
    emotion: 'joy',
    reactions: {
      charoun: '이건, 계산된 한수처럼 보이는군요',
      hanyeoreum: '정말 좋은 표현인데요?',
      baekya: '설명하지 않아도 충분합니다.',
      kimdohyeon: '이런 순간이 좋아요.',
    },
  },
  '/delay': {
    emotion: 'delays',
    reactions: {
      charoun: '막히셨나요? 괜찮습니다.',
      hanyeoreum: '인물의 마음을 생각해볼까요?',
      baekya: '조금 더 들여다보시죠.',
      kimdohyeon: '천천히 써도 괜찮아요.',
    },
  },
  '/read': {
    emotion: 'read',
    reactions: {
      charoun: '이제 확인해볼 시간입니다.',
      hanyeoreum: '끝까지 함께할 수 있어서 좋았어요.',
      baekya: '이야기를 펼쳐볼 시간입니다.',
      kimdohyeon: '자, 함께 이야기를 펼쳐볼까요?',
    },
  },
};


function formatText(text) {
  return text
    .replace(/\n?\[STATE:[^\]]*\]/g, '')
    .replace(/"([^"]*)"/g, '\n\n"$1"\n\n')
    .replace(/\n{3,}/g, '\n\n')
    .trim();
}

// 받은 텍스트를 타자기처럼 한 글자씩 표시(백엔드는 통째로 보내고 화면 노출만 점진적 → 응답 '마' 제거)
function TypedText({ text, speed = 30, step = 1, onType, onDone }) {
  const [count, setCount] = useState(0);
  useEffect(() => {
    setCount(0);
    if (!text) { onDone?.(); return; }
    let i = 0;
    const id = setInterval(() => {
      i = Math.min(text.length, i + step);
      setCount(i);
      onType?.();
      if (i >= text.length) { clearInterval(id); onDone?.(); }
    }, speed);
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [text]);
  return text.slice(0, count);
}

// 작가 AI 메시지 — 라이브 응답이면 나레이션→대사 순으로 타이핑, 복원된 기록은 즉시 표시
function CharMessage({ msg, characterName, hasBookmark, onType, onDone }) {
  // 토큰 스트리밍 중(isStreaming)·스트리밍 완료분(isStreamDone)은 실제로 흘러왔으므로 타자기 비활성.
  const live = !!msg.narration && !msg.isRestored && !msg.isStreaming && !msg.isStreamDone;
  // 복원 메시지는 narration이 ""(빈 문자열)이어도 text로 fallback하지 않음 (?? 사용)
  const rawNarration = msg.isRestored ? (msg.narration ?? msg.text ?? '') : (msg.narration || msg.text || '');
  const narration = formatText(rawNarration);
  const dialogue = (msg.dialogue || '').replace(/\n{2,}/g, '\n').trim();
  const hasDialogue = !!dialogue;
  const charName = msg.speaker || characterName || msg.name;
  const [narrDone, setNarrDone] = useState(!live || !narration);

  return (
    <div className="bubble-content">
      {narration && (
        <p className="narration-text">
          {hasBookmark && !hasDialogue && <span className="bubble-bookmark">🔖</span>}
          {live
            ? <TypedText text={narration} onType={onType} onDone={() => { setNarrDone(true); if (!hasDialogue) onDone?.(); }} />
            : narration}
        </p>
      )}
      {hasDialogue && narrDone && (
        <div className="dialogue-block">
          <span className="badge">{charName}</span>
          <div className="bubble bubble--char">
            {hasBookmark && <span className="bubble-bookmark">🔖</span>}
            &ldquo;{live ? <TypedText text={dialogue} onType={onType} onDone={onDone} /> : dialogue}&rdquo;
          </div>
        </div>
      )}
    </div>
  );
}

function Bubble({ msg, persona, characterName, protagonistName, streaming, hasBookmark, isSelected, onContextMenu, onType, onDone }) {
  if (msg.role === 'system') {
    return <div className="world-info-header">{msg.text}</div>;
  }

  if (msg.role === 'opening') {
    return (
      <div className="opening-scene">
        {(msg.narration || '').split('\n').filter(Boolean).map((line, i) => (
          <p key={i} className="opening-scene__line">{line}</p>
        ))}
      </div>
    );
  }

  const isUser = msg.role === 'user' && !msg.isSideChar;

  if (!isUser) {
    const hasContent = !!(msg.narration || msg.text || msg.dialogue);
    const isLoading = !hasContent && streaming;

    // @조연 입력: 왼쪽 캐릭터 버블
    if (msg.role === 'user' && msg.isSideChar) {
      return (
        <div
          id={`bubble-${msg.id}`}
          className={`bubble-row bubble-row--char${isSelected ? ' bubble-row--selected' : ''}`}
          onContextMenu={onContextMenu}
        >
          <div className="bubble-content">
            <div className="dialogue-block">
              <span className="badge">{msg.name}</span>
              <div className="bubble bubble--char bubble--markdown">
                {hasBookmark && <span className="bubble-bookmark">🔖</span>}
                <ReactMarkdown>{msg.text}</ReactMarkdown>
              </div>
            </div>
          </div>
        </div>
      );
    }

    // speaker가 주인공 이름이면 오른쪽 버블 + narration만 표시
    const speakerIsProtagonist = protagonistName && msg.speaker && msg.speaker === protagonistName;
    if (speakerIsProtagonist) {
      return (
        <>
          <div
            id={`bubble-${msg.id}`}
            className={`bubble-row bubble-row--char${isSelected ? ' bubble-row--selected' : ''}`}
            onContextMenu={onContextMenu}
          >
            {isLoading ? (
              <div className="bubble-content"><div className="typing-dots"><span /><span /><span /></div></div>
            ) : (
              <CharMessage
                msg={{ ...msg, dialogue: null, speaker: '' }}
                characterName={characterName}
                hasBookmark={hasBookmark}
                onType={onType}
                onDone={!msg.dialogue ? onDone : undefined}
              />
            )}
          </div>
          {msg.dialogue && (
            <div className="bubble-row bubble-row--user">
              <div className="bubble-content bubble-content--user">
                <div className="dialogue-block" style={{ alignItems: 'flex-end' }}>
                  <span className="badge badge--user">{msg.speaker}</span>
                  <div className="bubble bubble--user">&ldquo;{msg.dialogue}&rdquo;</div>
                </div>
              </div>
            </div>
          )}
        </>
      );
    }

    return (
      <div
        id={`bubble-${msg.id}`}
        className={`bubble-row bubble-row--char${isSelected ? ' bubble-row--selected' : ''}`}
        onContextMenu={onContextMenu}
      >
        {isLoading ? (
          <div className="bubble-content">
            <div className="typing-dots"><span /><span /><span /></div>
          </div>
        ) : (
          <CharMessage msg={msg} characterName={characterName} hasBookmark={hasBookmark} onType={onType} onDone={onDone} />
        )}
      </div>
    );
  }

  return (
    <div
      id={`bubble-${msg.id}`}
      className={`bubble-row bubble-row--user${isSelected ? ' bubble-row--selected' : ''}`}
      onContextMenu={onContextMenu}
    >
      <div className="bubble-content bubble-content--user">
        <span className="badge badge--user">{msg.name}</span>
        <div className="bubble bubble--user bubble--markdown">
          {hasBookmark && <span className="bubble-bookmark">🔖</span>}
          <ReactMarkdown>{msg.text}</ReactMarkdown>
        </div>
      </div>
    </div>
  );
}

export default function Chat() {
  const location = useLocation();
  const navigate = useNavigate();
  const { worldId, chatId: chatIdFromState, authorId: authorIdRaw, opening, manuscriptContent, generateOpening } = location.state ?? {};
  const chatId = chatIdFromState ?? worldId ?? 'room_001';
  const [authorId, setAuthorId] = useState(() => resolveAuthorId(authorIdRaw));
  useAuthorTheme(authorId);
  const [videoError, setVideoError] = useState(false);
  const [reactionEmotion, setReactionEmotion] = useState(null);
  const delayTimerRef = useRef(null);
  const delayPlayedRef = useRef(false);
  const pendingReactionEmotionRef = useRef(null);

  // manuscriptContent: state로 오면 localStorage에 저장, 없으면 localStorage에서 복원
  useEffect(() => {
    if (!chatId || chatId === 'room_001') return;
    if (manuscriptContent) {
      localStorage.setItem(`manuscript_${chatId}`, manuscriptContent);
    }
  }, [chatId, manuscriptContent]);

  // 능동 경고: 진입 시 '자주 틀리는 것'(2회 이상) 미리 보기. 닫으면 그날은 다시 안 뜸.
  useEffect(() => {
    if (!chatId || chatId === 'room_001') return;
    const today = new Date().toISOString().slice(0, 10);
    if (localStorage.getItem(`warmup_off_${chatId}_${today}`)) return;
    getErrorWarmup(chatId, 3).then(r => setWarmup(r?.items ?? [])).catch(() => { });
  }, [chatId]);

  const dismissWarmup = () => {
    try {
      const today = new Date().toISOString().slice(0, 10);
      localStorage.setItem(`warmup_off_${chatId}_${today}`, '1');
    } catch { /* localStorage 차단 무시 */ }
    setWarmup([]);
  };

  // 스토리 채팅 작가 (고정)
  const storyAuthor = AUTHOR_MAP[authorId] ?? AUTHOR_MAP[1];

  // 오른쪽 패널 작가 (슬라이드로 전환 가능)
  const initialAuthorIdx = AUTHOR_IDS.indexOf(Number(authorId));
  const [currentAuthorIdx, setCurrentAuthorIdx] = useState(
    initialAuthorIdx !== -1 ? initialAuthorIdx : 0
  );
  const currentAuthor = AUTHOR_MAP[AUTHOR_IDS[currentAuthorIdx]];

  // ── 스토리 채팅 상태 ───────────────────────────────────────
  const [messages, setMessages] = useState([]);
  const [loadingHistory, setLoadingHistory] = useState(!!chatId && chatId !== 'room_001');   // 채팅 기록 로딩 표시
  const [input, setInput] = useState(opening || '');
  const [streaming, setStreaming] = useState(false);
  const [suggestions, setSuggestions] = useState([]);   // 💡 입력 추천(말투 기반 voice 포함)
  const [suggestOn, setSuggestOn] = useState(false);    // 💡 버튼 토글 상태
  const [speaker, setSpeaker] = useState(null);       // @등장인물: 이번 대사를 말하는 인물(없으면 주인공)
  const [mentionOpen, setMentionOpen] = useState(false);   // @ 멘션 드롭다운 표시 여부
  const [mentionQuery, setMentionQuery] = useState('');    // @ 뒤 입력값(필터)
  const [reaction, setReaction] = useState('');     // F-AS-05 작가 리액션 자막
  const reactionTimerRef = useRef(null);
  const [world, setWorld] = useState(null);
  const [dbCharacters, setDbCharacters] = useState([]);
  const [warmup, setWarmup] = useState([]);   // 능동 경고: 자주 틀리는 것 미리 보기(2회 이상)
  const [ending, setEnding] = useState(false);
  const [converting, setConverting] = useState(false);
  const [showSaveModal, setShowSaveModal] = useState(false);
  const [saveComplete, setSaveComplete] = useState(false);

  const [importedNarration, setImportedNarration] = useState(() => {
    if (manuscriptContent) return manuscriptContent;
    if (chatId && chatId !== 'room_001') return localStorage.getItem(`manuscript_${chatId}`) ?? null;
    return null;
  });

  // ── 메모/교정 상태 (패널과 공유) ─────────────────────────
  const [memos, setMemos] = useState([]);
  const [corrections, setCorrections] = useState([]);
  const [selectedMsgId, setSelectedMsgId] = useState(null);

  // ── 컨텍스트 메뉴 (스토리 말풍선용) ──────────────────────
  const [contextMenu, setContextMenu] = useState({ visible: false, x: 0, y: 0, msgId: null });

  // ── 자동 피드백 / 교정 상태 ──────────────────────────────
  const [autoFeedback, setAutoFeedback] = useState(false);
  const [realtimeProof, setRealtimeProof] = useState(false);
  // 🔊 작가 리액션 음성(말로 반응) ON/OFF — 기본 ON, 사용자가 끄면 기억
  const [voiceReaction, setVoiceReaction] = useState(() => localStorage.getItem('voice_reaction') !== 'off');
  // 🔍 설정 검수(F-QC-01) ON/OFF — 새 응답이 확립된 설정과 모순되는지 RAG 검수. 기본 ON.
  const [consistencyOn, setConsistencyOn] = useState(() => localStorage.getItem('consistency_check') !== 'off');
  const [consistencyAlert, setConsistencyAlert] = useState(null);   // [{established, conflict, severity}] | null
  // 장르 가드: 장르 밖 감지 알림(비차단 칩) + 세션 확장 승인 여부
  const [genreAlert, setGenreAlert] = useState(null);   // { note } | null
  const [genreOpen, setGenreOpen_] = useState(false);   // 이 세션에서 '판타지로 도입' 승인됨

  // ── 사용자 ID ────────────────────────────────────────────
  const [userId, setUserId] = useState(null);

  // ── Refs ─────────────────────────────────────────────────
  const bottomRef = useRef(null);
  const esRef = useRef(null);
  const inputRef = useRef(null);
  const feedbackTimerRef = useRef(null);
  const authorPanelRef = useRef(null);

  // ── userId 로드 ──────────────────────────────────────────
  useEffect(() => {
    authClient.getSession().then(s => setUserId(s.data?.user?.id ?? null));
  }, []);

  // ── 마지막 사용 모드 기록 ────────────────────────────────
  useEffect(() => {
    if (chatId && chatId !== 'room_001') localStorage.setItem(`session_mode_${chatId}`, 'chat');
  }, [chatId]);

  // ── 세션/세계관 로드 ──────────────────────────────────────
  useEffect(() => {
    if (!chatId || chatId === 'room_001') { setLoadingHistory(false); return; }
    setLoadingHistory(true);
    setMessages([]);
    setImportedNarration(null);
    getSession(chatId)
      .then(session => {
        if (session?.author_id) {
          setAuthorId(session.author_id);
          const idx = AUTHOR_IDS.indexOf(Number(session.author_id));
          if (idx !== -1) setCurrentAuthorIdx(idx);
        }
        return Promise.all([
          getWorld(session.world_id),
          getCharacters(session.world_id),
          getDialogues(chatId),
        ]);
      })
      .then(([w, chars, dialogues]) => {
        setWorld(w);
        setDbCharacters(chars);
        const protagonistName = chars.find(c => c.role === 'protagonist')?.name ?? '나';

        const savedOpening = localStorage.getItem('opening_' + chatId);
        if (savedOpening && dialogues.length === 0) {
          setMessages([{ id: 'opening_scene', role: 'opening', narration: savedOpening, isRestored: true }]);
        }

        if (dialogues.length > 0) {
          const restored = dialogues.map(d => {
            const isUser = d.speaker_type === 'user';
            const speakerName = d.speaker || (isUser ? protagonistName : storyAuthor.displayName);
            const isSideChar = isUser && !!d.speaker && d.speaker !== protagonistName;

            // AI 응답: “나레이션\n\n\”대사\”” 형태로 저장됨 → 분리해서 복원
            let narration = undefined;
            let dialogue = undefined;
            if (!isUser) {
              const trimmed = (d.content || '').trim();
              // Pattern 1: 나레이션\n\n”대사” 형식
              // “=직선따옴표(DB저장형식), “”=곡선따옴표
              // split 대신 regex 사용 — 대사 내부에 \n\n이 있어도 깨지지 않음
              const m1 = trimmed.match(/^([\s\S]*?)\n\n["“”]([\s\S]*)["“”]$/);
              if (m1) {
                narration = m1[1].trim();
                dialogue = m1[2];
              } else {
                // Pattern 2: 전체가 “대사”인 경우 (나레이션 없음)
                const m2 = trimmed.match(/^["“”]([\s\S]*)["“”]$/);
                if (m2) {
                  narration = '';
                  dialogue = m2[1];
                } else {
                  narration = trimmed;
                  dialogue = '';
                }
              }
            }

            return {
              id: d.id,
              role: isUser ? 'user' : 'character',
              name: speakerName,
              speaker: d.speaker || null,
              text: d.content,
              narration,
              dialogue,
              isSideChar,
              isRestored: true,
            };
          });
          if (savedOpening) {
            setMessages([
              { id: 'opening_scene', role: 'opening', narration: savedOpening, isRestored: true },
              ...restored,
            ]);
          } else {
            setMessages(restored);
          }
        }
      })
      .catch(console.error)
      .finally(() => setLoadingHistory(false));
  }, [chatId]);

  // ── 첫 장면 생성 — worldview에서 generateOpening: true 로 진입한 경우만 실행
  useEffect(() => {
    if (!generateOpening || !chatIdFromState) return;
    const runOpening = async () => {
      const narration = await generateOpeningScene(chatIdFromState).catch(() => '');
      if (!narration) return;
      localStorage.setItem('opening_' + chatIdFromState, narration);
      setMessages(prev =>
        prev.length === 0
          ? [{ id: 'opening_scene', role: 'opening', narration, isRestored: true }]
          : prev
      );
    };
    const timer = setTimeout(runOpening, 300);
    return () => clearTimeout(timer);
  }, [generateOpening, chatIdFromState]);

  // ── 자동 스크롤 ──────────────────────────────────────────
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // ── 자동 피드백 (스트리밍 종료 시 트리거) ────────────────
  useEffect(() => {
    if (streaming || !autoFeedback) return;
    const lastMsg = messages[messages.length - 1];
    if (!lastMsg || lastMsg.role !== 'character') return;
    clearTimeout(feedbackTimerRef.current);
    feedbackTimerRef.current = setTimeout(() => {
      const lastUserMsg = [...messages].reverse().find(m => m.role === 'user' && m.text);
      if (lastUserMsg) authorPanelRef.current?.triggerFeedback(lastUserMsg.text);
    }, 2000);
    return () => clearTimeout(feedbackTimerRef.current);
  }, [streaming, autoFeedback, messages]);

  // ── EventSource cleanup (페이지 이탈 시 스트림·리액션 음성 정리) ────
  useEffect(() => {
    return () => {
      if (esRef.current) { esRef.current.close(); esRef.current = null; }
      stopReaction();
    };
  }, []);

  // ── 리액션 음성 ON/OFF 영속 + OFF 시 재생 중인 음성 정지 ────
  useEffect(() => {
    localStorage.setItem('voice_reaction', voiceReaction ? 'on' : 'off');
    if (!voiceReaction) stopReaction();
  }, [voiceReaction]);

  // 검수 ON/OFF 영속
  useEffect(() => {
    localStorage.setItem('consistency_check', consistencyOn ? 'on' : 'off');
  }, [consistencyOn]);

  // ── 컨텍스트 메뉴 외부 클릭 닫기 ─────────────────────────
  useEffect(() => {
    function close() { setContextMenu(prev => ({ ...prev, visible: false })); }
    document.addEventListener('click', close);
    return () => document.removeEventListener('click', close);
  }, []);

  // ── 컨텍스트 메뉴 ─────────────────────────────────────────
  function handleBubbleContextMenu(e, msgId) {
    e.preventDefault();
    setContextMenu({ visible: true, x: e.clientX, y: e.clientY, msgId });
  }

  function handleMemoFromContext(msgId) {
    setContextMenu(prev => ({ ...prev, visible: false }));
    authorPanelRef.current?.openMemoFor(msgId);
  }

  async function handleDeleteMsg(msgId) {
    setContextMenu(prev => ({ ...prev, visible: false }));
    setMessages(prev => prev.filter(m => m.id !== msgId));
    try {
      await deleteMessage(chatId, msgId);
    } catch (e) {
      console.warn('메시지 DB 삭제 실패:', e);
    }
  }

  function handleMemoClick(memo) {
    if (!memo.msgId) return;
    document.getElementById(`bubble-${memo.msgId}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    setSelectedMsgId(memo.msgId);
  }

  // ── 💡 입력 추천 (voice 프로파일 있으면 말투 기반, 없으면 일반) ──
  async function fetchSuggestions() {
    if (!chatId || chatId === 'room_001') return;

    if (userId) {
      try {
        const voiceProfile = await getVoiceProfile();
        if (voiceProfile) {
          const lastCharMsg = [...messages].reverse().find(m => m.role === 'character');
          const npcDialogue = lastCharMsg?.dialogue || lastCharMsg?.narration || '';
          const data = await getVoiceSuggestions(chatId, {
            npc_dialogue: npcDialogue,
            genre: world?.genre || '',
          });
          if (data.suggestions?.length) {
            setSuggestions(data.suggestions);
            return;
          }
        }
      } catch { /* 폴백 */ }
    }

    const data = await getSuggestions(chatId, { character_id: storyAuthor.characterId, world_context: '' });
    setSuggestions(data.suggestions ?? []);
  }

  // ── 스토리 채팅 ──────────────────────────────────────────
  // F-AS-05: 사용자 대사 → 작가 리액션 자막(아바타 위)을 잠깐 표시
  function showReaction(text) {
    setReaction(text);
    if (reactionTimerRef.current) clearTimeout(reactionTimerRef.current);
    reactionTimerRef.current = setTimeout(() => setReaction(''), 10000);
  }

  function playPendingReaction() {
    if (!pendingReactionEmotionRef.current) return;

    setReactionEmotion(pendingReactionEmotionRef.current);
    pendingReactionEmotionRef.current = null;
  }

  function playReactionVideo(emotion) {
    if (!emotion) return;

    setReactionEmotion(null);
    setTimeout(() => {
      setReactionEmotion(emotion);
    }, 0);
  }

  // 장르 가드 — '판타지로 도입' 승인(이후 턴 감지 끔) / '그대로 유지'(칩만 닫음)
  async function acceptGenre() {
    setGenreOpen_(true);
    setGenreAlert(null);
    await setGenreOpen(chatId, true);
    toast('장르 확장을 켰어요. 자유롭게 전개하세요.');
  }
  function keepGenre() {
    setGenreAlert(null);
  }

  function resetDelayTimer() {
    if (delayTimerRef.current) clearTimeout(delayTimerRef.current);

    delayTimerRef.current = setTimeout(() => {
      if (!delayPlayedRef.current && !streaming) {
        setReactionEmotion('delays');
        delayPlayedRef.current = true;
      }
    }, 3 * 60 * 1000);
  }

  useEffect(() => {
    resetDelayTimer();

    return () => {
      if (delayTimerRef.current) clearTimeout(delayTimerRef.current);
    };
  }, [streaming]);

  // ── @등장인물 멘션 ────────────────────────────────────────
  const mentionCandidates = mentionOpen
    ? dbCharacters.filter(c => c.name && c.name.includes(mentionQuery))
    : [];

  function handleInputChange(e) {
    const v = e.target.value;
    setInput(v);
    // 화자 미지정 + '@'로 시작 + 공백/줄바꿈 전 → 멘션 드롭다운 표시
    if (!speaker && /^@[^\s\n]*$/.test(v)) {
      setMentionQuery(v.slice(1));
      setMentionOpen(true);
    } else if (mentionOpen) {
      setMentionOpen(false);
    }
  }

  function selectSpeaker(char) {
    setSpeaker(char);
    setInput('');
    setMentionOpen(false);
    setMentionQuery('');
    inputRef.current?.focus();
  }

  async function handleSend() {
    if (!input.trim() || streaming) return;
    const userText = input.trim();
    const demoEntry = Object.entries(DEMO_REACTIONS).find(([keyword]) => userText.includes(keyword));
    const demoReaction = demoEntry?.[1];
    const cleanUserText = demoEntry ? userText.replace(demoEntry[0], '').trim() : userText;
    const activeSpeaker = speaker;   // 화자 캡처(아래에서 상태는 즉시 초기화)
    setInput('');
    setSpeaker(null);
    setMentionOpen(false);

    const isFirstChat = messages.length === 0 && !importedNarration;
    delayPlayedRef.current = false;
    resetDelayTimer();

    const protagonistName = dbCharacters.find(c => c.role === 'protagonist')?.name ?? '나';
    const speakerName = activeSpeaker?.name ?? protagonistName;
    const isSideChar = !!activeSpeaker && activeSpeaker.name !== protagonistName;
    const userMsgTempId = `temp_user_${Date.now()}`;
    setMessages(prev => [...prev, { id: userMsgTempId, role: 'user', name: speakerName, text: cleanUserText, isSideChar }]);

    // 작가 리액션 — 사용자 입력 + 작가 답변 '문맥'으로 감정을 잡으려면 답변이 나온 뒤 호출해야 함.
    // 데모 슬래시 명령(/start·/tension·/joy 등)이면 결정론적 리액션을 바로 표시(API 생략).
    const fireReaction = (authorReply) => {
      if (demoReaction) {
        playReactionVideo(demoReaction.emotion);
        const reactionText = demoReaction.reactions[currentAuthor.characterId] ?? '';
        showReaction(reactionText);
        return;
      }
      // 첫 채팅이면 무조건 /start 데모 리액션 — 결정론적 오프닝(API 생략)
      if (isFirstChat) {
        playReactionVideo('start');
        const startText = DEMO_REACTIONS['/start'].reactions[currentAuthor.characterId] ?? '';
        showReaction(startText);
        if (voiceReaction && startText) speakReaction(startText, currentAuthor.characterId);
        return;
      }
      getAuthorReaction(chatId, {
        content: userText,
        character_id: currentAuthor.characterId,
        author_reply: authorReply,
      })
        .then(r => {
          if (r.reaction) {
            console.log(`[REACTION] emotion=${r.emotion}, reaction=${r.reaction}`);


            if (r.emotion === 'joy' || r.emotion === 'tension') {
              playReactionVideo(r.emotion);
              const key = r.emotion === 'joy' ? '/joy' : '/tension';
              const demoText = DEMO_REACTIONS[key].reactions[currentAuthor.characterId] ?? '';
              showReaction(demoText);
            } else if (voiceReaction) {
              // 🔊 작가 목소리로 리액션 낭독
              speakReaction(r.reaction, currentAuthor.characterId);
              showReaction(r.reaction);
            }
          }
        })
        .catch(err => console.error('[REACTION ERROR]', err));
    };

    fireReaction('');

    // 맞춤법 교정 — 실시간 교정 ON일 때만 작가가 '여백 메모'로 짚어줌 (느려도/실패해도 본 흐름 안 막음)
    if (realtimeProof) {
      // 새 입력마다 이전 턴 교정을 먼저 비운다 — 안 비우면 옛 교정("주라는 걸" 등)이
      // 남아 지금 안 친 문장이 떠 보이던 버그. 누적하지 않고 '이번 입력 교정'만 표시.
      setCorrections([]);
      proofread(chatId, cleanUserText, currentAuthor.characterId)
        .then(r => {
          if (r.errors?.length) {
            setCorrections([{ id: Date.now(), errors: r.errors, memo: r.memo }]);
            setStreaming(cur => { if (!cur) authorPanelRef.current?.showProofView(); return cur; });
          }
        })
        .catch(() => { });
    }

    const userMsgRealId = await sendMessage(chatId, { content: cleanUserText, character_id: storyAuthor.characterId, speaker: activeSpeaker?.name ?? '' });
    if (userMsgRealId) {
      setMessages(prev => prev.map(m => m.id === userMsgTempId ? { ...m, id: userMsgRealId } : m));
    }

    const streamMsgId = `stream_${Date.now()}`;
    setMessages(prev => [...prev, { id: streamMsgId, _key: streamMsgId, role: 'character', name: storyAuthor.displayName, text: '' }]);
    setStreaming(true);

    // 50초 내 응답 없으면 로딩 해제
    const streamTimeoutId = setTimeout(() => {
      if (esRef.current) { esRef.current.close(); esRef.current = null; }
      setStreaming(false);
      setMessages(prev => prev.map(m =>
        m.id === streamMsgId && !m.narration && !m.dialogue
          ? { ...m, text: '⏱️ 응답 시간이 초과되었습니다. 다시 시도해주세요.' }
          : m
      ));
    }, 50000);

    let lastReply = { narration: '', dialogue: '' };   // 리액션 문맥용 — 작가가 쓴 장면 누적
    let streamed = false;                               // 토큰 스트리밍 발생 여부(최종 reply 재타이핑 방지)
    esRef.current = connectChatStream(
      chatId,
      { content: cleanUserText, character_id: storyAuthor.characterId, mode: 'author', world_context: '', speaker: activeSpeaker?.name ?? '', check_consistency: consistencyOn },
      ({ narration, speaker, dialogue, out_of_genre, genre_note, consistency }) => {

        if (narration) {
          const ttsText = extractFirstSentence(narration, 50);
          console.log('[FIRST TTS]', ttsText);
          speakReaction(ttsText, currentAuthor.characterId);
        }


        lastReply = { narration: narration ?? '', dialogue: dialogue ?? '' };
        setMessages(prev =>
          prev.map(m => m.id === streamMsgId
            ? { ...m, narration, speaker, dialogue, isStreaming: false, isStreamDone: streamed }
            : m)
        );
        // 장르 밖 감지 → 비차단 칩(이미 도입 승인했으면 무시)
        if (out_of_genre && !genreOpen) setGenreAlert({ note: genre_note });
        // 🔍 설정 검수 — 모순 발견 시 비차단 경고(작가가 짚어줌)
        if (consistency && consistency.consistent === false && consistency.violations?.length) {
          setConsistencyAlert(consistency.violations);
        }
      },
      (realMsgId) => {
        clearTimeout(streamTimeoutId);
        setStreaming(false);
        if (realMsgId) {
          setMessages(prev => prev.map(m => m.id === streamMsgId ? { ...m, id: realMsgId } : m));
        }
      },
      // 토큰 스트리밍: narration이 생성되는 대로 라이브 표시(체감 TTFB↓)
      (narration) => {
        streamed = true;
        setMessages(prev =>
          prev.map(m => m.id === streamMsgId ? { ...m, narration, isStreaming: true } : m)
        );
      },
    );
  }

  async function handleEnd() {
    if (!chatId || chatId === 'room_001') { toast('유효한 세션이 없습니다.', 'error'); setEnding(false); return; }

    const MIN_END_DURATION = 10000;
    const startedAt = Date.now();
    setReactionEmotion('read');

    if (esRef.current) { esRef.current.close(); esRef.current = null; }
    setStreaming(false);
    setEnding(true);
    try {
      await completeSession(chatId);
    } catch (err) {
      toast(`세션 종료 실패: ${err.message}`, 'error');
      setEnding(false);
      return;
    }
    try {
      await generateNovel(chatId);
    } catch {
      toast('소설 변환에 실패했어요. 읽기 화면의 "다시 변환"으로 재시도할 수 있어요.', 'error');
    }

    const elapsed = Date.now() - startedAt;
    const remainingDelay = Math.max(0, MIN_END_DURATION - elapsed);
    setTimeout(() => { navigate('/storylist'); }, remainingDelay);
  }

  async function handleSaveConfirm() {
    if (saveComplete && messages.filter(m => m.role !== 'system').length === 0) {
      toast('대화 내용이 없어 완결할 수 없어요.', 'error');
      return;
    }
    setShowSaveModal(false);
    if (saveComplete) {
      await handleEnd();
    } else {
      navigate('/storylist');
    }
    setSaveComplete(false);
  }

  async function handleRestart() {
    if (!window.confirm('현재 대화를 저장하고 같은 세계관으로 새로 시작할까요?')) return;
    if (esRef.current) { esRef.current.close(); esRef.current = null; }
    setStreaming(false);
    try {
      const newSession = await restartSession(chatId);
      localStorage.removeItem(`manuscript_${chatId}`);
      localStorage.removeItem('opening_' + chatId);
      navigate('/chat', { state: { worldId: newSession.world_id, chatId: newSession.id, authorId } });
    } catch (err) {
      toast(`새로하기 실패: ${err.message}`, 'error');
    }
  }

  async function handleSwitchToEditor() {
    setConverting(true);
    try {
      await convertToNovel(chatId);
    } catch { /* 변환 실패해도 에디터로 이동 */ }
    navigate('/editor', { state: { chatId, authorId } });
  }

  // ── 렌더 ─────────────────────────────────────────────────
  return (
    <div className="chat-layout">
      {converting && (
        <div className="convert-loading">소설로 변환하는 중...</div>
      )}

      {/* 왼쪽: 스토리 채팅 */}
      <div className="chat-main">
        <div className="chat-header">
          <div className="chat-header__info">
            <span className="chat-header__persona">{world?.title ?? ''}</span>
            <span className="chat-header__genre">{world?.genre ?? ''}</span>
          </div>
          <div className="chat-header__btns">
            <div className="mode-switcher">
              <button
                className="mode-switcher__track"
                onClick={handleSwitchToEditor}
                disabled={converting || ending}
                aria-label="집필형으로 전환"
              />
              <span className="mode-switcher__label">{converting ? '변환 중' : '참여형'}</span>
            </div>
            <button className="editor-save-btn" onClick={() => setShowSaveModal(true)} disabled={ending || converting}>
              {ending ? '완결 중...' : '저장'}
            </button>
            <button className="editor-back-btn restart-btn" onClick={handleRestart} disabled={ending || converting}>새로하기</button>
            <button className="editor-back-btn" onClick={() => navigate('/storylist')}>목록</button>
          </div>
        </div>

        <div className="chat-messages">
          {warmup.length > 0 && (
            <div className="warmup-card">
              <button className="warmup-card__close" onClick={dismissWarmup} aria-label="닫기">×</button>
              <div className="warmup-card__title">💡 자주 놓치는 것, 오늘은 미리 체크해요</div>
              <div className="warmup-card__items">
                {warmup.map((w, i) => (
                  <span key={i} className="warmup-chip">
                    <span className="warmup-chip__bad">{w.original}</span>
                    <span className="warmup-chip__arrow">→</span>
                    <span className="warmup-chip__good">{w.corrected}</span>
                    <span className="warmup-chip__count">{w.count}회</span>
                  </span>
                ))}
              </div>
            </div>
          )}
          {importedNarration && !loadingHistory && messages.length === 0 && (
            <div className="narration-import-block">
              <span className="narration-import-block__label">원고</span>
              <div className="narration-import-block__text">{importedNarration}</div>
              <div className="narration-import-block__divider">— 여기서부터 참여형 대화 —</div>
            </div>
          )}
          {loadingHistory && (
            <div className="chat-loading">채팅을 불러오는 중...</div>
          )}
          {messages.map(msg => (
            <Bubble
              key={msg._key ?? msg.id}
              msg={msg}
              persona={storyAuthor}
              characterName={dbCharacters.find(c => c.role !== 'protagonist')?.name}
              protagonistName={dbCharacters.find(c => c.role === 'protagonist')?.name}
              streaming={streaming && msg === messages[messages.length - 1]}
              hasBookmark={memos.some(m => m.msgId === msg.id)}
              isSelected={selectedMsgId === msg.id}
              onType={() => bottomRef.current?.scrollIntoView({ block: 'end' })}
              onDone={playPendingReaction}
              onContextMenu={msg.role !== 'system'
                ? e => handleBubbleContextMenu(e, msg.id)
                : undefined}
            />
          ))}
          <div ref={bottomRef} />
        </div>


        {genreAlert && (
          <div className="genre-alert">
            <span className="genre-alert__text">
              ⚠️ 장르 밖 요소 감지{genreAlert.note ? ` — ${genreAlert.note}` : ''}
            </span>
            <button className="genre-alert__btn genre-alert__btn--accept" onClick={acceptGenre}>
              판타지로 도입
            </button>
            <button className="genre-alert__btn" onClick={keepGenre}>
              그대로 유지
            </button>
          </div>
        )}

        {consistencyAlert && (
          <div className="consistency-alert">
            <div className="consistency-alert__head">
              <span className="consistency-alert__title">🔍 설정 검수 — 모순 발견</span>
              <button className="consistency-alert__x" onClick={() => setConsistencyAlert(null)} title="닫기">✕</button>
            </div>
            {consistencyAlert.map((v, i) => (
              <div key={i} className="consistency-alert__item">
                <span className={`consistency-alert__sev consistency-alert__sev--${v.severity || 'mid'}`}>
                  {v.severity === 'high' ? '심각' : v.severity === 'low' ? '경미' : '주의'}
                </span>
                <span className="consistency-alert__text">
                  <b>설정:</b> {v.established} <b>↔ 충돌:</b> {v.conflict}
                </span>
              </div>
            ))}
          </div>
        )}

        {suggestions.length > 0 && !streaming && (
          <div className="chat-suggestions">
            {suggestions.map((s, i) => {
              const text = typeof s === 'string' ? s : s.text;
              const label = typeof s === 'object' ? s.label : null;
              return (
                <button
                  key={i}
                  className="suggestion-chip"
                  onClick={() => { setInput(text); setSuggestions([]); setSuggestOn(false); }}
                >
                  {label && <span className="suggestion-chip__label">{label}</span>}
                  {text}
                </button>
              );
            })}
          </div>
        )}

        <div className="chat-input-wrap">
          {mentionOpen && mentionCandidates.length > 0 && (
            <div className="mention-dropdown">
              <div className="mention-dropdown__hint">대사를 말할 등장인물 선택</div>
              {mentionCandidates.map(c => (
                <button
                  key={c.id ?? c.name}
                  type="button"
                  className="mention-item"
                  onMouseDown={e => { e.preventDefault(); selectSpeaker(c); }}
                >
                  <span className="mention-item__name">@{c.name}</span>
                  <span className="mention-item__role">{c.role === 'protagonist' ? '주인공' : '조연'}</span>
                </button>
              ))}
            </div>
          )}
          <div className="chat-input-bar">
            <button
              className={`suggest-btn${suggestOn ? ' suggest-btn--on' : ''}`}
              onClick={() => {
                if (suggestOn) {
                  setSuggestOn(false);
                  setSuggestions([]);
                } else {
                  setSuggestOn(true);
                  fetchSuggestions();
                }
              }}
              disabled={streaming}
              title={suggestOn ? '입력 추천 끄기' : '입력 추천(말투 기반)'}
              aria-pressed={suggestOn}
            >
              💡
            </button>
            <button
              className="suggest-btn"
              onClick={() => setVoiceReaction(v => !v)}
              title={voiceReaction ? '작가 음성 리액션 끄기' : '작가 음성 리액션 켜기'}
              aria-pressed={voiceReaction}
            >
              {voiceReaction ? '🔊' : '🔇'}
            </button>
            <button
              className={`suggest-btn${consistencyOn ? ' suggest-btn--on' : ''}`}
              onClick={() => setConsistencyOn(v => !v)}
              title={consistencyOn ? '설정 검수 끄기 (모순 탐지)' : '설정 검수 켜기 (모순 탐지)'}
              aria-pressed={consistencyOn}
            >
              🔍
            </button>
            {speaker && (
              <span className="speaker-chip" title="이 인물의 대사로 전송됩니다">
                @{speaker.name}
                <button className="speaker-chip__x" onClick={() => setSpeaker(null)} title="화자 해제">✕</button>
              </span>
            )}
            <textarea
              ref={inputRef}
              className="chat-input"
              placeholder={streaming ? '응답 중...' : speaker ? `${speaker.name}의 대사 입력...` : '대사 입력  (@ 로 등장인물 지정)'}
              value={input}
              disabled={streaming}
              rows={1}
              onChange={handleInputChange}
              onKeyDown={e => {
                if (mentionOpen && mentionCandidates.length > 0 && e.key === 'Enter' && !e.nativeEvent.isComposing) {
                  e.preventDefault(); selectSpeaker(mentionCandidates[0]); return;
                }
                if (e.key === 'Escape' && mentionOpen) { setMentionOpen(false); return; }
                if (e.key === 'Backspace' && input === '' && speaker) { e.preventDefault(); setSpeaker(null); return; }
                if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); handleSend(); }
              }}
            />
            <button className="chat-send-btn" onClick={handleSend} disabled={streaming}>전송</button>
          </div>
        </div>
      </div>

      {/* 오른쪽: 작가 AI 패널 */}
      <AuthorPanel
        ref={authorPanelRef}
        chatId={chatId}
        userId={userId}
        world={world}
        dbCharacters={dbCharacters}
        mode="chat"
        currentAuthorIdx={currentAuthorIdx}
        onAuthorChange={setCurrentAuthorIdx}
        autoFeedback={autoFeedback}
        onAutoFeedbackChange={setAutoFeedback}
        realtimeProof={realtimeProof}
        onRealtimeProofChange={setRealtimeProof}
        memos={memos}
        onMemosChange={setMemos}
        onApplyText={text => setInput(prev => prev ? `${prev}\n${text}` : text)}
        getFeedbackText={() => [...messages].reverse().find(m => m.role === 'user' && m.text)?.text ?? null}
        isFeedbackDisabled={messages.length === 0}
        reaction={reaction}
        reactionEmotion={reactionEmotion}
        onReactionEnd={() => setReactionEmotion(null)}
        selectedMsgId={selectedMsgId}
        onSelectedMsgIdChange={setSelectedMsgId}
        onMemoClick={handleMemoClick}
        corrections={corrections}
        onSkipCorrection={id => setCorrections(prev => prev.filter(c => c.id !== id))}
        onWorldEdit={world?.id ? () => navigate('/worldedit', { state: { worldId: world.id, chatId, authorId, from: 'chat' } }) : null}
      />

      {/* 저장 확인 팝업 */}
      {showSaveModal && (
        <div className="save-modal-overlay" onClick={() => setShowSaveModal(false)}>
          <div className="save-modal" onClick={e => e.stopPropagation()}>
            <p className="save-modal__title">저장하시겠습니까?</p>
            <label className="save-modal__check">
              <input
                type="checkbox"
                checked={saveComplete}
                onChange={e => setSaveComplete(e.target.checked)}
              />
              완결하기
            </label>
            <div className="save-modal__btns">
              <button className="save-modal__btn save-modal__btn--cancel" onClick={() => { setShowSaveModal(false); setSaveComplete(false); }}>취소</button>
              <button className="save-modal__btn save-modal__btn--save" onClick={handleSaveConfirm}>저장</button>
            </div>
          </div>
        </div>
      )}

      {/* 스토리 말풍선 컨텍스트 메뉴 */}
      {contextMenu.visible && (
        <div
          className="context-menu"
          style={{ top: contextMenu.y, left: contextMenu.x }}
          onClick={e => e.stopPropagation()}
        >
          <button className="context-menu__item" onClick={() => handleMemoFromContext(contextMenu.msgId)}>
            메모
          </button>
          <button
            className="context-menu__item context-menu__item--danger"
            onClick={() => handleDeleteMsg(contextMenu.msgId)}
          >
            삭제
          </button>
        </div>
      )}
    </div>
  );
}
