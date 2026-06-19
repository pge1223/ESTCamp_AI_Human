import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { saveVoiceProfile } from '../../lib/voiceApi';
import './voice.css';

const STORAGE_KEY = 'voice_profile_answers';

const REQUIRED_QUESTIONS = [
  { id: 'shock',   emotion: '당황',   text: '카페 화장실을 썼는데 변기가 막혀서 너무 당황했다.' },
  { id: 'hurt',    emotion: '서운함', text: '상대가 내 말을 제대로 듣지 않는 것 같아서 조금 서운했다.' },
  { id: 'sorry',   emotion: '미안함', text: '내가 약속 시간에 늦어서 상대에게 미안했다.' },
  { id: 'refuse',  emotion: '거절',   text: '상대의 부탁을 들어주기 어려워서 거절해야 한다.' },
  { id: 'flutter', emotion: '설렘',   text: '좋아하는 사람이 갑자기 내 이름을 불러서 긴장했다.' },
];

const OPTIONAL_QUESTIONS = [
  { id: 'joke',    emotion: '장난',   text: '친구가 말도 안 되는 소리를 해서 웃겼다.' },
  { id: 'avoid',   emotion: '회피',   text: '대답하기 곤란한 질문을 받아서 말을 돌리고 싶었다.' },
  { id: 'angry',   emotion: '화남',   text: '상대가 선을 넘는 말을 해서 기분이 나빴다.' },
  { id: 'sincere', emotion: '진심',   text: '평소에 숨기고 있던 마음을 조심스럽게 말하고 싶었다.' },
  { id: 'awkward', emotion: '어색함', text: '오랜만에 만난 사람과 단둘이 있게 되어 어색했다.' },
  { id: 'worry',   emotion: '걱정',   text: '상대가 괜찮다고 말했지만 계속 신경 쓰였다.' },
  { id: 'firm',    emotion: '단호함',   text: '더 이상 참기 어려워서 분명하게 말해야 했다.' },
  { id: 'tension', emotion: '갈등/긴장', text: '상대가 내가 숨기고 있던 일을 이미 알고 있는 것처럼 말했다.' },
];

const GENRE_QUESTIONS = {
  horror:  { emotion: '호러/미스터리', text: '분명 아무도 없었는데, 방금 뒤에서 발소리가 들렸다.' },
  mystery: { emotion: '추리',         text: '상대가 방금 한 말이 아까 했던 말과 맞지 않는 것 같다.' },
  romance: { emotion: '로맨스',       text: '상대가 별말 없이 내 쪽으로 우산을 기울여줬다.' },
  daily:   { emotion: '일상/에세이',  text: '별일 아닌 하루였는데, 집에 오는 길에 이상하게 마음이 가라앉았다.' },
};

const GENRE_LABELS = [
  { key: 'horror',  label: '호러/미스터리' },
  { key: 'mystery', label: '추리' },
  { key: 'romance', label: '로맨스' },
  { key: 'daily',   label: '일상/에세이' },
];

function loadSaved() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch { return null; }
}

function VoiceProfile() {
  const navigate = useNavigate();
  const saved = loadSaved();

  const [requiredAnswers, setRequiredAnswers] = useState(
    saved?.requiredAnswers ?? Object.fromEntries(REQUIRED_QUESTIONS.map(q => [q.id, '']))
  );
  const [optionalChecked, setOptionalChecked] = useState(
    saved?.optionalChecked ?? Object.fromEntries(OPTIONAL_QUESTIONS.map(q => [q.id, false]))
  );
  const [optionalAnswers, setOptionalAnswers] = useState(
    saved?.optionalAnswers ?? Object.fromEntries(OPTIONAL_QUESTIONS.map(q => [q.id, '']))
  );
  const [selectedGenres, setSelectedGenres] = useState(
    new Set(saved?.selectedGenres ?? [])
  );
  const [genreAnswers, setGenreAnswers] = useState(saved?.genreAnswers ?? {});
  const [userSamples, setUserSamples] = useState(saved?.userSamples ?? '');
  const [optionalContext, setOptionalContext] = useState(saved?.optionalContext ?? '');

  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [done, setDone] = useState(false);

  // 폼 변경 시마다 localStorage 자동 저장
  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({
      requiredAnswers,
      optionalChecked,
      optionalAnswers,
      selectedGenres: [...selectedGenres],
      genreAnswers,
      userSamples,
      optionalContext,
    }));
  }, [requiredAnswers, optionalChecked, optionalAnswers, selectedGenres, genreAnswers, userSamples, optionalContext]);

  const handleToggleOptional = (id) => {
    setOptionalChecked(prev => ({ ...prev, [id]: !prev[id] }));
  };

  const handleSubmit = async () => {
    const filledRequired = REQUIRED_QUESTIONS
      .map(q => requiredAnswers[q.id]?.trim())
      .filter(Boolean);

    if (filledRequired.length === 0) {
      setError('필수 문장을 최소 1개 이상 작성해주세요.');
      return;
    }

    // 가이드 문항 조합 (필수 + 선택 체크된 것 + 장르)
    const guideAnswers = [
      ...REQUIRED_QUESTIONS
        .filter(q => requiredAnswers[q.id]?.trim())
        .map(q => `[${q.emotion}] ${requiredAnswers[q.id].trim()}`),
      ...OPTIONAL_QUESTIONS
        .filter(q => optionalChecked[q.id] && optionalAnswers[q.id]?.trim())
        .map(q => `[${q.emotion}] ${optionalAnswers[q.id].trim()}`),
      ...[...selectedGenres]
        .filter(key => genreAnswers[key]?.trim())
        .map(key => `[${GENRE_QUESTIONS[key].emotion}] ${genreAnswers[key].trim()}`),
    ];

    const samples = userSamples.trim()
      ? userSamples.split('\n').map(s => s.trim()).filter(Boolean)
      : [];

    setError('');
    setIsLoading(true);
    try {
      await saveVoiceProfile({
        userSamples: samples,
        guideAnswers,
        optionalContext: optionalContext.trim(),
      });
      setDone(true);
    } catch (e) {
      setError(e.message || '오류가 발생했습니다. 다시 시도해주세요.');
    } finally {
      setIsLoading(false);
    }
  };

  if (done) {
    return (
      <div className="voice-container">
        <div className="voice-done">
          <p className="voice-done-emoji">✨</p>
          <h2 className="voice-done-title">말투 분석 완료!</h2>
          <p className="voice-done-desc">
            이제 소설 속 대사 추천이 내 말투에 맞게 나와요.
          </p>
          <button className="voice-btn-primary" onClick={() => navigate('/')}>
            메인으로 돌아가기
          </button>
          <button className="voice-btn-secondary" onClick={() => setDone(false)}>
            수정하기
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="voice-container">
      <div className="voice-wrapper">
        <button className="voice-back" onClick={() => navigate(-1)}>← 뒤로</button>

        <div className="voice-header">
          <h1 className="voice-title">나만의 말투 설정</h1>
          <p className="voice-subtitle">
            아래 문장을 <strong>평소 본인 말투</strong>로 바꿔 적어주세요.<br />
            예쁘게 쓰지 않아도 됩니다. 친구에게 카톡하듯 써도 되고, 혼잣말처럼 써도 됩니다.<br />
            <span className="voice-notice">작성한 문장은 말투 특징 분석에만 사용되며, 대사에 그대로 복사되지 않습니다.</span>
          </p>
        </div>

        {/* 장르 선택 */}
        <section className="voice-section">
          <h2 className="voice-section-title">장르 선택 <span className="voice-optional">(선택)</span></h2>
          <p className="voice-section-desc">선택하면 해당 장르 문장이 추가로 제공됩니다.</p>
          <div className="voice-genre-list">
            {GENRE_LABELS.map(({ key, label }) => (
              <button
                key={key}
                className={`voice-genre-chip ${selectedGenres.has(key) ? 'active' : ''}`}
                onClick={() => {
                  setSelectedGenres(prev => {
                    const next = new Set(prev);
                    next.has(key) ? next.delete(key) : next.add(key);
                    return next;
                  });
                  if (selectedGenres.has(key)) {
                    setGenreAnswers(prev => { const n = { ...prev }; delete n[key]; return n; });
                  }
                }}
              >
                {selectedGenres.has(key) && <span className="voice-chip-check">✓ </span>}
                {label}
              </button>
            ))}
          </div>
        </section>

        {/* 필수 문장 */}
        <section className="voice-section">
          <h2 className="voice-section-title">필수 문장 <span className="voice-badge">기본 말투 분석용</span></h2>
          {REQUIRED_QUESTIONS.map((q, i) => (
            <div key={q.id} className="voice-question-block">
              <label className="voice-question-label">
                <span className="voice-question-num">{i + 1}</span>
                <span className="voice-emotion-tag">{q.emotion}</span>
                {q.text}
              </label>
              <textarea
                className="voice-textarea"
                placeholder="평소 말투로 바꿔서 써주세요..."
                value={requiredAnswers[q.id]}
                onChange={e => setRequiredAnswers(prev => ({ ...prev, [q.id]: e.target.value }))}
                rows={2}
              />
            </div>
          ))}
        </section>

        {/* 선택 문장 */}
        <section className="voice-section">
          <h2 className="voice-section-title">선택 문장 <span className="voice-badge voice-badge-sub">감정 반응 분석용</span></h2>
          <p className="voice-section-desc">원하는 항목을 선택해 답변해주세요.</p>
          {OPTIONAL_QUESTIONS.map((q, i) => (
            <div key={q.id} className="voice-optional-block">
              <button
                className={`voice-optional-toggle ${optionalChecked[q.id] ? 'checked' : ''}`}
                onClick={() => handleToggleOptional(q.id)}
              >
                <span className="voice-toggle-check">{optionalChecked[q.id] ? '✓' : '+'}</span>
                <span className="voice-emotion-tag">{q.emotion}</span>
                <span className="voice-optional-text">{q.text}</span>
              </button>
              {optionalChecked[q.id] && (
                <textarea
                  className="voice-textarea voice-textarea-indent"
                  placeholder="평소 말투로 바꿔서 써주세요..."
                  value={optionalAnswers[q.id]}
                  onChange={e => setOptionalAnswers(prev => ({ ...prev, [q.id]: e.target.value }))}
                  rows={2}
                />
              )}
            </div>
          ))}
        </section>

        {/* 장르 문장 */}
        {selectedGenres.size > 0 && (
          <section className="voice-section">
            <h2 className="voice-section-title">장르 문장</h2>
            {[...selectedGenres].map(key => (
              <div key={key} className="voice-question-block">
                <label className="voice-question-label">
                  <span className="voice-emotion-tag">{GENRE_QUESTIONS[key].emotion}</span>
                  {GENRE_QUESTIONS[key].text}
                </label>
                <textarea
                  className="voice-textarea"
                  placeholder="평소 말투로 바꿔서 써주세요..."
                  value={genreAnswers[key] || ''}
                  onChange={e => setGenreAnswers(prev => ({ ...prev, [key]: e.target.value }))}
                  rows={2}
                />
              </div>
            ))}
          </section>
        )}

        {/* 자유 문장 */}
        <section className="voice-section">
          <h2 className="voice-section-title">자유 문장 <span className="voice-optional">(선택)</span></h2>
          <p className="voice-section-desc">평소 자주 쓰는 문장을 줄 단위로 입력해주세요.</p>
          <textarea
            className="voice-textarea voice-textarea-tall"
            placeholder={"야 나 오늘 진짜 피곤해 죽겠어\n헐 그거 진짜야? 완전 신기하다\n..."}
            value={userSamples}
            onChange={e => setUserSamples(e.target.value)}
            rows={4}
          />
        </section>

        {/* 원하는 방향 */}
        <section className="voice-section">
          <h2 className="voice-section-title">원하는 말투 방향 <span className="voice-optional">(선택)</span></h2>
          <textarea
            className="voice-textarea"
            placeholder="예시: 좀 더 차분하게, 반말로, 이모지 없이..."
            value={optionalContext}
            onChange={e => setOptionalContext(e.target.value)}
            rows={2}
          />
        </section>

        {error && <p className="voice-error">{error}</p>}

        <button
          className="voice-btn-primary"
          onClick={handleSubmit}
          disabled={isLoading}
        >
          {isLoading ? '분석 중...' : '말투 분석 시작하기'}
        </button>
      </div>
    </div>
  );
}

export default VoiceProfile;
