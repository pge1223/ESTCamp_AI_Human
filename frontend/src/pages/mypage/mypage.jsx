import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { getTemplates, deleteTemplate } from '../../lib/worldTemplates';
import { authClient } from '../../lib/auth';
import {
    getProfile, getWorks, getRecent, getSentences, getWiki, saveRelations,
    deleteSentence, getAuthorRecords, getAchievements, getStats, getDashboard,
    getTasteProfile, setupTasteProfile, getErrorNotebook, deleteErrorNotebookEntry,
} from '../../lib/mypageApi';
import TasteOnboarding from './TasteOnboarding';
import { getDailyLetter, determineSituation } from '../../lib/authorLetters';
import { getVoiceProfile } from '../../lib/voiceApi';
import { toast } from '../../lib/toast';
import './mypage.css';
import VideoPreviewModal from '../../components/videoPreviewModal';
import { getGlobalVideoVolume, setGlobalVideoVolume } from '../../lib/videoVolume';

const WORK_GOAL_CHARS = 30000;

function formatRelativeTime(iso) {
    if (!iso) return '';
    const d = new Date(iso);
    const now = new Date();
    const diffDays = Math.floor((now - d) / 86400000);
    const hh = d.getHours();
    const mm = String(d.getMinutes()).padStart(2, '0');
    const period = hh < 12 ? '오전' : '오후';
    const h12 = hh % 12 || 12;
    const timeStr = `${period} ${h12}:${mm}`;
    if (diffDays === 0) return `오늘 ${timeStr}`;
    if (diffDays === 1) return `어제 ${timeStr}`;
    return `${diffDays}일 전`;
}

const NAV = {
    library: [
        { id: '대시보드', icon: '🏠' },
        { id: '최근 작업', icon: '🕐' },
        { id: '취향 프로필', icon: '✨' },
        { id: '세계관 보관함', icon: '📁' },
        { id: '설정집', icon: '🗂️' },
        { id: '문장 보관함', icon: '💾' },
        { id: '오답노트', icon: '✏️' },
        { id: 'AI 작가 기록', icon: '🤖' },
        { id: '갤러리', icon: '🎬' },
        { id: '내 작품', icon: '📚' },
        { id: '업적', icon: '🏆' },
    ],
    account: [
        { id: '말투 설정', icon: '✨' },
        { id: '환경설정', icon: '⚙️' },
        { id: '알림설정', icon: '🔔' },
    ],
};


// 내 서재 탭 데이터 캐시(stale-while-revalidate) — 재방문 시 인증 대기 없이 즉시 표시 후 백그라운드 갱신
function mpCacheGet(uid, key) {
    try {
        const v = localStorage.getItem(`${key}_${uid}`);
        return v ? JSON.parse(v) : null;
    } catch { return null; }
}
function mpCacheSet(uid, key, val) {
    try { localStorage.setItem(`${key}_${uid}`, JSON.stringify(val)); } catch { /* 무시 */ }
}

// 마운트 즉시(인증 대기 없이) 마지막 유저의 캐시를 읽어 스피너 플래시 제거 (재방문 0초 체감)
function readMpCache() {
    try {
        const uid = localStorage.getItem('mp_last_uid');
        if (!uid) return { hadCache: false };
        const cp = mpCacheGet(uid, 'profile');
        const cd = mpCacheGet(uid, 'dashboard');
        const cs = mpCacheGet(uid, 'stats');
        return {
            profile: cp,
            dashboard: cd,
            stats: cs,
            works: mpCacheGet(uid, 'works'),
            recent: mpCacheGet(uid, 'recent'),
            sentences: mpCacheGet(uid, 'sentences'),
            authorRecords: mpCacheGet(uid, 'authorRecords'),
            achievements: mpCacheGet(uid, 'achievements'),
            errorNotebook: mpCacheGet(uid, 'errorNotebook'),
            hadCache: !!(cp && cd && cs),
        };
    } catch {
        return { hadCache: false };
    }
}

function MyPage() {
    const navigate = useNavigate();
    const [userId, setUserId] = useState(null);
    const [userInfo, setUserInfo] = useState(null);
    const [active, setActive] = useState('대시보드');

    // 각 탭 데이터 (lazy)
    const [dashboard, setDashboard] = useState(() => readMpCache().dashboard ?? null);
    const [profile, setProfile] = useState(() => readMpCache().profile ?? null);
    const [works, setWorks] = useState(() => readMpCache().works ?? null);
    const [recent, setRecent] = useState(() => readMpCache().recent ?? null);
    const [sentences, setSentences] = useState(() => readMpCache().sentences ?? null);
    const [authorRecords, setAuthorRecords] = useState(() => readMpCache().authorRecords ?? null);
    const [selectedVideoAuthor, setSelectedVideoAuthor] = useState(1);
    const [previewVideo, setPreviewVideo] = useState(null);
    const [achievements, setAchievements] = useState(() => readMpCache().achievements ?? null);
    const [errorNotebook, setErrorNotebook] = useState(() => readMpCache().errorNotebook ?? null);   // 오답노트(자주 틀린 맞춤법)
    const [errSort, setErrSort] = useState('count');            // 'count'=많이 틀린 순 | 'recent'=최신순
    const [stats, setStats] = useState(() => readMpCache().stats ?? null);

    // 취향 프로필
    const [tasteProfile, setTasteProfile] = useState(null);
    const [tasteWorks, setTasteWorks] = useState([]);
    const [showTasteOnboarding, setShowTasteOnboarding] = useState(false);

    // 세계관 보관함
    const [myTemplates, setMyTemplates] = useState(null); // null=미로드

    // 설정집 선택 상태
    const [wikiWork, setWikiWork] = useState(null);
    const [wiki, setWiki] = useState(null);
    const [wikiTab, setWikiTab] = useState('세계관');
    // 등장인물 관계도(사용자 직접 입력) — relations=[{from, to, label}], 편집 입력값
    const [relations, setRelations] = useState([]);
    const [relFrom, setRelFrom] = useState('');
    const [relTo, setRelTo] = useState('');
    const [relLabel, setRelLabel] = useState('');
    const [editIdx, setEditIdx] = useState(null);   // null=새 관계 추가, 숫자=그 관계 수정 중

    const [voiceProfile, setVoiceProfile] = useState(undefined); // undefined=미로드, null=없음, obj=있음
    const [loading, setLoading] = useState(() => !readMpCache().hadCache);

    const VIDEO_AUTHORS = [
        { id: 1, name: '백야', path: '/assets/author1' },
        { id: 2, name: '차로운', path: '/assets/author2' },
        { id: 3, name: '한여름', path: '/assets/author3' },
        { id: 4, name: '김도현', path: '/assets/author4' },
    ];

    const REACTION_VIDEOS = [
        { key: 'start', label: '첫 입력 반응' },
        { key: 'tension', label: '예상 밖 전개' },
        { key: 'joy', label: '장면이 잘 나왔을 때' },
        { key: 'delays', label: '입력이 없을 때' },
        { key: 'read', label: '소설 완성' },
        { key: 'loading', label: '로딩중' },
    ];

    // 초기 로딩: 유저 확인 + 프로필 + 작품 목록
    useEffect(() => {
        const init = async () => {
            const session = await authClient.getSession();
            const uid = session.data?.user?.id || null;
            if (!uid) { navigate('/login'); return; }
            setUserId(uid);
            setUserInfo(session.data?.user);
            try { localStorage.setItem('mp_last_uid', uid); } catch { /* 무시 */ }

            // 0) 캐시 즉시 표시(stale-while-revalidate) — dashboard 엔드포인트가 ~6s라
            //    재방문 시 캐시로 0초 표시 후 백그라운드 갱신(내 서재 들락날락 체감 단축)
            let hadCache = false;
            try {
                const cp = localStorage.getItem(`profile_${uid}`);
                const cd = localStorage.getItem(`dashboard_${uid}`);
                const cs = localStorage.getItem(`stats_${uid}`);
                if (cp) setProfile(JSON.parse(cp));
                if (cd) setDashboard(JSON.parse(cd));
                if (cs) setStats(JSON.parse(cs));
                if (cp && cd && cs) { hadCache = true; setLoading(false); }   // 캐시 있으면 즉시 화면
            } catch { /* 캐시 무시 */ }

            // 1) 최신값 갱신 — 캐시가 없었으면 이게 첫 화면(스피너 유지), 있었으면 조용히 교체
            try {
                const [profileData, dashboardData, statsData] = await Promise.all([
                    getProfile(uid),
                    getDashboard(uid),
                    getStats(uid),
                ]);
                setProfile(profileData);
                setDashboard(dashboardData);
                setStats(statsData);
                try {
                    localStorage.setItem(`profile_${uid}`, JSON.stringify(profileData));
                    localStorage.setItem(`dashboard_${uid}`, JSON.stringify(dashboardData));
                    localStorage.setItem(`stats_${uid}`, JSON.stringify(statsData));
                } catch { /* 무시 */ }
            } catch (e) {
                console.error(e);
            } finally {
                if (!hadCache) setLoading(false);   // 캐시로 이미 화면 떴으면 finally에서 또 끌 필요 없음
            }

            // 2) 다른 탭 전용 + 느린 voice-profile(~1.6s)은 백그라운드 — 대기하지 않음
            getVoiceProfile().then(vp => setVoiceProfile(vp ?? null)).catch(() => setVoiceProfile(null));
            getWorks(uid).then(w => { setWorks(w); mpCacheSet(uid, 'works', w); }).catch(() => { });
            getTasteProfile(uid).then(t => {
                setTasteProfile(t.taste_profile ?? {});
                setTasteWorks(t.selected_works ?? []);
            }).catch(() => { });
        };
        init();
    }, [navigate]);

    // 탭 전환 시 lazy fetch
    const handleNav = useCallback(async (tab) => {
        if (tab === '말투 설정') { navigate('/voice-profile'); return; }
        setActive(tab);
        if (!userId) return;
        // 캐시가 있으면 화면은 이미 떠 있음 → 열 때 조용히 재검증(stale-while-revalidate)하고 캐시 갱신
        try {
            if (tab === '최근 작업') { const d = await getRecent(userId); setRecent(d); mpCacheSet(userId, 'recent', d); }
            if (tab === '문장 보관함') { const d = await getSentences(userId); setSentences(d); mpCacheSet(userId, 'sentences', d); }
            if (tab === 'AI 작가 기록') { const d = await getAuthorRecords(userId); setAuthorRecords(d); mpCacheSet(userId, 'authorRecords', d); }
            if (tab === '업적') { const d = await getAchievements(userId); setAchievements(d); mpCacheSet(userId, 'achievements', d); }
            if (tab === '오답노트') { const d = await getErrorNotebook(userId); setErrorNotebook(d); mpCacheSet(userId, 'errorNotebook', d); }
        } catch (e) {
            console.error(e);
        }
    }, [userId]);

    async function handleTasteComplete(selectedWorks) {
        try {
            const data = await setupTasteProfile(userId, selectedWorks);
            setTasteProfile(data.taste_profile ?? {});
            setTasteWorks(data.selected_works ?? []);
        } catch (e) { console.error(e); }
        setShowTasteOnboarding(false);
    }

    const handleWikiSelect = async (work) => {
        setWikiWork(work);
        setWiki(null);
        setWikiTab('세계관');
        setRelations([]);
        setRelFrom(''); setRelTo(''); setRelLabel(''); setEditIdx(null);
        try {
            const w = await getWiki(userId, work.session_id);
            setWiki(w);
            setRelations(w.relations || []);
        } catch (e) { console.error(e); }
    };

    const persistRelations = async (next) => {
        setRelations(next);
        if (!wikiWork) return;
        try { await saveRelations(userId, wikiWork.session_id, next); }
        catch (e) { console.error(e); toast('관계도 저장에 실패했어요.', 'error'); }
    };

    const resetRelEditor = () => { setRelFrom(''); setRelTo(''); setRelLabel(''); setEditIdx(null); };

    const handleSaveRelation = () => {
        if (!relFrom || !relTo || relFrom === relTo) {
            toast('서로 다른 두 인물을 선택하세요.', 'error');
            return;
        }
        if (editIdx !== null) {
            // 수정 — 기존 라벨 위치(dx/dy)는 유지하고 from/to/label만 갱신
            persistRelations(relations.map((r, i) => (
                i === editIdx ? { ...r, from: relFrom, to: relTo, label: relLabel.trim() } : r
            )));
        } else {
            persistRelations([...relations, { from: relFrom, to: relTo, label: relLabel.trim() }]);
        }
        resetRelEditor();
    };

    const handleEditRelation = (idx) => {
        const r = relations[idx];
        setRelFrom(r.from); setRelTo(r.to); setRelLabel(r.label || '');
        setEditIdx(idx);
    };

    const handleDeleteRelation = (idx) => {
        persistRelations(relations.filter((_, i) => i !== idx));
        if (editIdx === idx) resetRelEditor();
        else if (editIdx !== null && idx < editIdx) setEditIdx(editIdx - 1);
    };

    // 관계 라벨 드래그 — 사용자가 끌어 위치 이동(겹침 해소). offset(dx,dy)을 관계에 저장.
    const relationsRef = useRef(relations);
    useEffect(() => { relationsRef.current = relations; }, [relations]);
    const labelDragRef = useRef(null);

    const onLabelDragMove = (e) => {
        const d = labelDragRef.current;
        if (!d) return;
        const ndx = Math.round(d.baseDx + (e.clientX - d.startX));
        const ndy = Math.round(d.baseDy + (e.clientY - d.startY));
        setRelations(prev => prev.map((r, i) => (i === d.idx ? { ...r, dx: ndx, dy: ndy } : r)));
    };
    const onLabelDragEnd = () => {
        window.removeEventListener('mousemove', onLabelDragMove);
        window.removeEventListener('mouseup', onLabelDragEnd);
        if (labelDragRef.current) {
            labelDragRef.current = null;
            if (wikiWork) saveRelations(userId, wikiWork.session_id, relationsRef.current).catch(err => console.error(err));
        }
    };
    const onLabelDragStart = (e, idx) => {
        e.preventDefault();
        const r = relations[idx];
        labelDragRef.current = { idx, startX: e.clientX, startY: e.clientY, baseDx: r.dx || 0, baseDy: r.dy || 0 };
        window.addEventListener('mousemove', onLabelDragMove);
        window.addEventListener('mouseup', onLabelDragEnd);
    };

    const handleDeleteSentence = async (id) => {
        if (!window.confirm('삭제할까요?')) return;
        try {
            await deleteSentence(userId, id);
            setSentences(prev => prev.filter(s => s.id !== id));
        } catch (e) { console.error(e); }
    };

    const handleDeleteError = async (original) => {
        try {
            const nb = await deleteErrorNotebookEntry(userId, original);
            setErrorNotebook(nb);
        } catch {
            toast('삭제에 실패했어요. 잠시 후 다시 시도해주세요.', 'error');
        }
    };

    const [bgmVolume, setBgmVolume] = useState(() => {
        const saved = localStorage.getItem('bgm_volume');
        return saved !== null ? Number(saved) : 0.2;
    });

    const [bgmPlaying, setBgmPlaying] = useState(() => {
        const saved = localStorage.getItem('bgm_playing');
        return saved === null ? true : saved === 'true';
    });

    const [videoVolume, setVideoVolume] = useState(() => getGlobalVideoVolume());

    return (
        <div className="mp">
            {loading && (
                <div className="mp-loading-overlay">
                    <div className="mp-spinner" />
                    <span>내 서재 불러오는 중…</span>
                </div>
            )}

            {/* 사이드바 */}
            <aside className="mp-sidebar">
                <button className="mp-back" onClick={() => navigate('/')}>← 메인</button>

                {/* 프로필 미니 카드 */}
                {profile && (
                    <div className="mp-sidebar-profile">
                        <div className="mp-sidebar-avatar">
                            {profile.username?.[0]?.toUpperCase() ?? '?'}
                        </div>
                        <div className="mp-sidebar-name">{profile.username}</div>
                        <div className="mp-sidebar-stats">
                            <span>{profile.stats.total_works} 작품</span>
                            <span>{profile.stats.total_chars.toLocaleString()}자</span>
                        </div>
                    </div>
                )}

                {/* 내 소설 목록 바로가기 */}
                <button className="mp-storylist-btn" onClick={() => navigate('/storylist')}>
                    내 소설 목록
                </button>

                {/* 내 서재 */}
                <div className="mp-nav-group">
                    <span className="mp-nav-label">내 서재</span>
                    {NAV.library.map(({ id, icon }) => (
                        <button
                            key={id}
                            className={`mp-nav-item ${active === id ? 'mp-nav-item--active' : ''}`}
                            onClick={() => handleNav(id)}
                        >
                            <span className="mp-nav-icon">{icon}</span>{id}
                        </button>
                    ))}
                </div>

                {/* 계정 */}
                <div className="mp-nav-group">
                    <span className="mp-nav-label">계정</span>
                    {NAV.account.map(({ id, icon }) => (
                        <button
                            key={id}
                            className={`mp-nav-item ${active === id ? 'mp-nav-item--active' : ''}`}
                            onClick={() => handleNav(id)}
                        >
                            <span className="mp-nav-icon">{icon}</span>{id}
                        </button>
                    ))}
                </div>
            </aside>

            {/* 메인 콘텐츠 */}
            <main className="mp-main">
                <h2 className="mp-page-title">{active}</h2>

                {/* ── 대시보드 ── */}
                {active === '대시보드' && (
                    <div className="mp-dashboard">
                        {dashboard && profile && works ? (
                            <>
                                {/* 오늘의 작가 편지 */}
                                {(() => {
                                    const { situation, authorId } = determineSituation(dashboard, profile, works);
                                    const protagonistName = dashboard.resume_work?.protagonist_name ?? null;
                                    const letter = getDailyLetter(situation, authorId, protagonistName);
                                    return (
                                        <div className="mp-letter">
                                            <div className="mp-letter__label">오늘의 작가 편지</div>
                                            <div className="mp-letter__author">{letter.author}</div>
                                            <div className="mp-letter__body">
                                                {letter.paragraphs.map((para, i) => <p key={i}>{para}</p>)}
                                            </div>
                                        </div>
                                    );
                                })()}

                                {/* 말투 설정 카드 */}
                                <div className="mp-voice-card" onClick={() => navigate('/voice-profile')}>
                                    <div className="mp-voice-card__left">
                                        <span className="mp-voice-card__icon">✨</span>
                                        <div>
                                            <div className="mp-voice-card__title">나만의 말투 설정</div>
                                            {voiceProfile ? (
                                                <>
                                                    <div className="mp-voice-card__tags">
                                                        {voiceProfile.speech_level?.value && voiceProfile.speech_level.value !== '추정 불가' && (
                                                            <span className="mp-voice-tag">{voiceProfile.speech_level.value}</span>
                                                        )}
                                                        {voiceProfile.sentence_length?.value && voiceProfile.sentence_length.value !== '추정 불가' && (
                                                            <span className="mp-voice-tag">문장 {voiceProfile.sentence_length.value}</span>
                                                        )}
                                                        {voiceProfile.tone?.primary?.slice(0, 2).map(t => (
                                                            <span key={t} className="mp-voice-tag">{t}</span>
                                                        ))}
                                                        {voiceProfile.emoji_style?.value && voiceProfile.emoji_style.value !== '추정 불가' && (
                                                            <span className="mp-voice-tag">이모지 {voiceProfile.emoji_style.value}</span>
                                                        )}
                                                    </div>
                                                    <div className="mp-voice-card__desc">
                                                        {voiceProfile.summary_for_user ?? '대사 추천에 반영 중'}
                                                    </div>
                                                </>
                                            ) : (
                                                <div className="mp-voice-card__desc">
                                                    말투를 설정하면 대사 추천이 내 말투로 나와요
                                                </div>
                                            )}
                                        </div>
                                    </div>
                                    <span className="mp-voice-card__arrow">
                                        {voiceProfile ? '수정 →' : '설정하기 →'}
                                    </span>
                                </div>

                                {/* 이어쓰기 + 최근 AI 피드백 */}
                                <div className="mp-dash-row">
                                    {dashboard.resume_work ? (
                                        <div className="mp-dash-card mp-resume">
                                            <div className="mp-dash-card__label">이어쓰기</div>
                                            <div className="mp-resume__title">{dashboard.resume_work.title}</div>
                                            <div className="mp-resume__progress">
                                                <div className="mp-resume__bar">
                                                    <div className="mp-resume__fill"
                                                        style={{ width: `${Math.min(100, Math.round(dashboard.resume_work.char_count / WORK_GOAL_CHARS * 100))}%` }}
                                                    />
                                                </div>
                                                <span className="mp-resume__pct">
                                                    {Math.min(100, Math.round(dashboard.resume_work.char_count / WORK_GOAL_CHARS * 100))}%
                                                </span>
                                            </div>
                                            {dashboard.resume_work.last_modified && (
                                                <div className="mp-resume__meta">
                                                    마지막 수정 {formatRelativeTime(dashboard.resume_work.last_modified)}
                                                </div>
                                            )}
                                            <button
                                                className="mp-resume__btn"
                                                onClick={() => navigate('/chat', {
                                                    state: {
                                                        chatId: dashboard.resume_work.session_id,
                                                        authorId: dashboard.resume_work.author_id,
                                                    }
                                                })}
                                            >
                                                이어쓰기 →
                                            </button>
                                        </div>
                                    ) : (
                                        <div className="mp-dash-card">
                                            <div className="mp-dash-card__label">이어쓰기</div>
                                            <p className="mp-empty" style={{ padding: '20px 0' }}>아직 작품이 없어요.</p>
                                        </div>
                                    )}

                                    {dashboard.recent_feedback ? (
                                        <div className="mp-dash-card mp-feedback">
                                            <div className="mp-dash-card__label">최근 AI 피드백</div>
                                            <div className="mp-feedback__author">{dashboard.recent_feedback.author_name}</div>
                                            <p className="mp-feedback__text">"{dashboard.recent_feedback.content}"</p>
                                        </div>
                                    ) : (
                                        <div className="mp-dash-card">
                                            <div className="mp-dash-card__label">최근 AI 피드백</div>
                                            <p className="mp-empty" style={{ padding: '20px 0' }}>피드백 기록이 없어요.</p>
                                        </div>
                                    )}
                                </div>

                                {/* 이번 주 집필 현황 */}
                                <div className="mp-dash-card mp-weekly">
                                    <div className="mp-dash-card__label">이번 주 집필 현황</div>
                                    <div className="mp-weekly__nums">
                                        <span>총 작성 <strong>{dashboard.weekly_chars.toLocaleString()}자</strong></span>
                                        <span>목표 <strong>{dashboard.weekly_goal.toLocaleString()}자</strong></span>
                                        <span className="mp-weekly__pct">
                                            {Math.min(100, Math.round(dashboard.weekly_chars / dashboard.weekly_goal * 100))}%
                                        </span>
                                    </div>
                                    <div className="mp-weekly__bar">
                                        <div className="mp-weekly__fill"
                                            style={{ width: `${Math.min(100, Math.round(dashboard.weekly_chars / dashboard.weekly_goal * 100))}%` }}
                                        />
                                    </div>
                                </div>

                                {/* 함께한 작가 */}
                                {dashboard.author_shares.length > 0 && (
                                    <div className="mp-dash-card mp-dash-authors">
                                        <div className="mp-dash-card__label">함께한 작가</div>
                                        {dashboard.author_shares.map(a => (
                                            <div key={a.author_id} className="mp-dash-author-row">
                                                <span className="mp-dash-author-name">{a.name}</span>
                                                <div className="mp-dash-author-bar">
                                                    <div className="mp-dash-author-fill" style={{ width: `${a.ratio}%` }} />
                                                </div>
                                                <span className="mp-dash-author-pct">{a.ratio}%</span>
                                            </div>
                                        ))}
                                    </div>
                                )}

                                {/* 창작 수치 */}
                                {profile && (
                                    <div className="mp-dash-numbers">
                                        <div className="mp-dash-num">
                                            <span className="mp-dash-num__val">{profile.stats.total_works}</span>
                                            <span className="mp-dash-num__lbl">총 작품</span>
                                        </div>
                                        <div className="mp-dash-num">
                                            <span className="mp-dash-num__val">{profile.stats.total_chars.toLocaleString()}</span>
                                            <span className="mp-dash-num__lbl">총 글자</span>
                                        </div>
                                        <div className="mp-dash-num">
                                            <span className="mp-dash-num__val">{profile.stats.completed_works}</span>
                                            <span className="mp-dash-num__lbl">완결</span>
                                        </div>
                                        <div className="mp-dash-num">
                                            <span className="mp-dash-num__val">{profile.stats.active_days}일</span>
                                            <span className="mp-dash-num__lbl">집필 일수</span>
                                        </div>
                                        {stats && (
                                            <div className="mp-dash-num">
                                                <span className="mp-dash-num__val">{stats.avg_chars_per_work.toLocaleString()}</span>
                                                <span className="mp-dash-num__lbl">작품당 평균</span>
                                            </div>
                                        )}
                                    </div>
                                )}
                            </>
                        ) : (
                            <p className="mp-empty">불러오는 중...</p>
                        )}
                    </div>
                )}

                {/* ── 내 작품 (완결) ── */}
                {active === '내 작품' && (() => {
                    const completed = works?.filter(w => w.status === 'completed') ?? [];
                    return (
                        <div className="mp-works">
                            {completed.length === 0 ? (
                                <p className="mp-empty">완결된 작품이 없어요.<br />집필을 마무리하면 여기에 쌓여요.</p>
                            ) : completed.map(w => (
                                <div
                                    key={w.session_id}
                                    className="mp-work-card mp-work-card--completed"
                                    onClick={() => navigate(`/read/${w.session_id}`)}
                                >
                                    <div className="mp-work-card__top">
                                        <span className="mp-work-card__title">{w.title}</span>
                                        <span className="mp-badge mp-badge--completed">완결</span>
                                    </div>
                                    <div className="mp-work-card__meta">
                                        {w.author_name && <span>작가 : {w.author_name}</span>}
                                        {w.world?.genre && <span>{w.world.genre}</span>}
                                        <span>{w.char_count.toLocaleString()}자</span>
                                        <span>{w.last_modified?.slice(0, 10)}</span>
                                    </div>
                                </div>
                            ))}
                        </div>
                    );
                })()}

                {/* ── 최근 작업 ── */}
                {active === '최근 작업' && (
                    <div className="mp-recent">
                        {!recent || recent.length === 0 ? (
                            <p className="mp-empty">최근 작업 기록이 없어요.</p>
                        ) : recent.map(day => (
                            <div key={day.date} className="mp-recent-day">
                                <h3 className="mp-recent-date">{day.date}</h3>
                                {day.activities.map(act => (
                                    <div key={act.session_id} className="mp-recent-item">
                                        <span className="mp-recent-title">{act.title}</span>
                                        <span className="mp-recent-chars">+{act.chars_added.toLocaleString()}자</span>
                                        {act.status !== 'completed' && (
                                            <button
                                                className="mp-recent-continue"
                                                onClick={() => navigate('/chat', {
                                                    state: { chatId: act.session_id, authorId: act.author_id }
                                                })}
                                            >
                                                이어쓰기 →
                                            </button>
                                        )}
                                    </div>
                                ))}
                            </div>
                        ))}
                    </div>
                )}

                {/* ── 취향 프로필 ── */}
                {active === '취향 프로필' && (
                    <div className="mp-taste">
                        <div className="mp-taste__header">
                            <div>
                                <h2 className="mp-taste__title">취향 프로필</h2>
                                <p className="mp-taste__desc">좋아하는 작품을 선택하면 AI가 당신의 취향을 분석해요</p>
                            </div>
                            <button
                                className="mp-taste__setup-btn"
                                onClick={() => setShowTasteOnboarding(true)}
                            >
                                {tasteWorks.length > 0 ? '다시 설정하기' : '취향 설정하기'}
                            </button>
                        </div>

                        {tasteWorks.length > 0 ? (
                            <>
                                {/* 선택한 작품 chips */}
                                <div className="mp-taste__section-label">선택한 작품</div>
                                <div className="mp-taste__chips">
                                    {['book', 'movie', 'drama'].map(cat => {
                                        const catWorks = tasteWorks.filter(w => w.category === cat);
                                        if (!catWorks.length) return null;
                                        const catLabel = { book: '책', movie: '영화', drama: '드라마' }[cat];
                                        return (
                                            <div key={cat} className="mp-taste__chip-group">
                                                <span className="mp-taste__chip-cat">{catLabel}</span>
                                                {catWorks.map(w => (
                                                    <span key={w.id} className="mp-taste__chip">{w.title}</span>
                                                ))}
                                            </div>
                                        );
                                    })}
                                </div>

                                {/* 취향 분석 결과 */}
                                {tasteProfile && (tasteProfile["선호장르"] || tasteProfile["선호키워드"]?.length > 0) && (
                                    <>
                                        <div className="mp-taste__section-label">취향 분석 결과</div>
                                        {tasteProfile["선호장르"] && (
                                            <div className="mp-taste__genre-result">
                                                <span className="mp-taste__genre-label">선호 장르</span>
                                                <span className="mp-taste__genre-value">{tasteProfile["선호장르"]}</span>
                                            </div>
                                        )}
                                        {tasteProfile["선호키워드"]?.length > 0 && (
                                            <div className="mp-taste__keywords-section">
                                                <span className="mp-taste__genre-label">선호 키워드</span>
                                                <div className="mp-taste__keywords">
                                                    {tasteProfile["선호키워드"].map((kw, i) => (
                                                        <span key={i} className="mp-taste__keyword">{kw}</span>
                                                    ))}
                                                </div>
                                            </div>
                                        )}
                                    </>
                                )}
                            </>
                        ) : (
                            <div className="mp-taste__empty">
                                <p>아직 취향 프로필이 없어요</p>
                                <p>좋아하는 작품을 선택해 AI가 당신의 취향을 분석하도록 해보세요</p>
                                <button
                                    className="mp-taste__setup-btn mp-taste__setup-btn--large"
                                    onClick={() => setShowTasteOnboarding(true)}
                                >취향 설정하기</button>
                            </div>
                        )}
                    </div>
                )}

                {/* ── 세계관 보관함 ── */}
                {active === '세계관 보관함' && (() => {
                    const tmpls = myTemplates ?? getTemplates();
                    if (myTemplates === null) setMyTemplates(getTemplates());
                    return (
                        <div className="mp-world-vault">
                            {tmpls.length === 0 ? (
                                <p className="mp-empty">저장된 세계관이 없어요.<br />세계관 수정 화면에서 내서재 저장을 눌러보세요.</p>
                            ) : tmpls.map(t => (
                                <div key={t.id} className="mp-vault-card">
                                    <div className="mp-vault-card__top">
                                        <span className="mp-vault-card__title">{t.title}</span>
                                        {t.genre && <span className="mp-badge mp-badge--active mp-badge--sm">{t.genre}</span>}
                                        <button
                                            className="mp-vault-card__del"
                                            onClick={() => { deleteTemplate(t.id); setMyTemplates(getTemplates()); }}
                                            title="삭제"
                                        >✕</button>
                                    </div>
                                    {t.setting && <div className="mp-vault-card__row"><span className="mp-vault-card__lbl">배경</span>{t.setting}</div>}
                                    {t.description && <div className="mp-vault-card__row"><span className="mp-vault-card__lbl">요약</span>{t.description}</div>}
                                    {t.rules && <div className="mp-vault-card__row"><span className="mp-vault-card__lbl">규칙</span>{t.rules}</div>}
                                    {t.characters?.length > 0 && (
                                        <div className="mp-vault-card__chars">
                                            {t.characters.map((c, i) => (
                                                <span key={i} className="mp-vault-card__char">
                                                    {c.name}
                                                    <span className="mp-vault-card__char-role">{c.role === 'protagonist' ? '주인공' : '조연'}</span>
                                                </span>
                                            ))}
                                        </div>
                                    )}
                                    <div className="mp-vault-card__date">{new Date(t.saved_at).toLocaleDateString('ko-KR')} 저장</div>
                                </div>
                            ))}
                        </div>
                    );
                })()}

                {/* ── 설정집 (세계관 · 등장인물 관계도 · 타임라인) ── */}
                {active === '설정집' && (
                    <div className="mp-wiki-layout">
                        {/* 작품 목록 */}
                        <div className="mp-wiki-list">
                            {!works || works.length === 0 ? (
                                <p className="mp-empty">작품이 없어요.</p>
                            ) : works.map(w => (
                                <button
                                    key={w.session_id}
                                    className={`mp-wiki-item ${wikiWork?.session_id === w.session_id ? 'mp-wiki-item--active' : ''}`}
                                    onClick={() => handleWikiSelect(w)}
                                >
                                    <span className="mp-wiki-item__title">{w.title}</span>
                                    <span className={`mp-badge mp-badge--${w.status} mp-badge--sm`}>
                                        {w.status === 'active' ? '진행중' : '완결'}
                                    </span>
                                </button>
                            ))}
                        </div>

                        {/* 위키 상세 */}
                        <div className="mp-wiki-detail">
                            {!wikiWork && <p className="mp-empty">좌측에서 작품을 선택해주세요.</p>}
                            {wikiWork && !wiki && <p className="mp-empty">불러오는 중...</p>}
                            {wiki && (
                                <>
                                    <div className="mp-wiki-tabs">
                                        {['세계관', '등장인물', '타임라인'].map(t => (
                                            <button
                                                key={t}
                                                className={`mp-wiki-tab ${wikiTab === t ? 'mp-wiki-tab--active' : ''}`}
                                                onClick={() => setWikiTab(t)}
                                            >
                                                {t}
                                            </button>
                                        ))}
                                    </div>

                                    {wikiTab === '세계관' && wiki.world && (
                                        <dl className="mp-dl">
                                            {wiki.world.genre && <><dt>장르</dt><dd>{wiki.world.genre}</dd></>}
                                            {wiki.world.setting && <><dt>배경</dt><dd>{wiki.world.setting}</dd></>}
                                            {wiki.world.description && <><dt>설명</dt><dd>{wiki.world.description}</dd></>}
                                            {wiki.world.rules && <><dt>규칙</dt><dd>{wiki.world.rules}</dd></>}
                                        </dl>
                                    )}

                                    {wikiTab === '등장인물' && (
                                        <div className="mp-relmap">
                                            {wiki.characters.length === 0
                                                ? <p className="mp-empty">등록된 인물이 없어요.</p>
                                                : (() => {
                                                    const ROLE_COLOR = { protagonist: 'var(--theme-color, #c9a87c)', supporting: '#7E9AD6', villain: '#E06C75', narrator: '#9aa0a6' };
                                                    const ROLE_LABEL = { protagonist: '주인공', supporting: '조연', villain: '빌런', narrator: '화자' };
                                                    const all = wiki.characters;
                                                    const SIZE = 380, C = SIZE / 2, R = all.length > 6 ? 150 : 128;
                                                    const single = all.length === 1;
                                                    const posById = {};
                                                    const nameById = {};
                                                    const nodes = all.map((c, i) => {
                                                        const ang = (-90 + (360 / all.length) * i) * Math.PI / 180;
                                                        const x = single ? C : C + R * Math.cos(ang);
                                                        const y = single ? C : C + R * Math.sin(ang);
                                                        posById[c.id] = { x, y };
                                                        nameById[c.id] = c.name;
                                                        return { c, x, y };
                                                    });
                                                    const rolesPresent = [...new Set(all.map(c => c.role))];
                                                    // 곡선 엣지 — 양방향(A→B, B→A) 입력 시 서로 반대쪽으로 휘어 겹치지 않게.
                                                    const NODE_R = 34, CURVE = 26;
                                                    const edgeGeo = relations
                                                        .map((r, idx) => ({ r, idx }))
                                                        .filter(x => posById[x.r.from] && posById[x.r.to])
                                                        .map(({ r, idx }) => {
                                                            const a = posById[r.from], b = posById[r.to];
                                                            const dx = b.x - a.x, dy = b.y - a.y;
                                                            const len = Math.hypot(dx, dy) || 1;
                                                            const ux = dx / len, uy = dy / len;          // 진행 방향 단위벡터
                                                            const nx = -uy, ny = ux;                     // 왼쪽 법선(방향마다 반대쪽 → 양방향 분리)
                                                            const ax = a.x + ux * NODE_R, ay = a.y + uy * NODE_R;   // 노드 밖에서 시작
                                                            const bx = b.x - ux * NODE_R, by = b.y - uy * NODE_R;   // 화살표가 노드 앞에서 멈춤
                                                            const mx = (ax + bx) / 2, my = (ay + by) / 2;
                                                            // 라벨 = 곡선 정점(apex). 드래그 offset(dx,dy)을 apex에 적용하고
                                                            // 제어점은 Q(0.5)=apex 가 되도록 역산 → 선이 라벨을 따라 휘어 한 세트로 움직임.
                                                            const apexX = mx + nx * (CURVE / 2) + (r.dx || 0);
                                                            const apexY = my + ny * (CURVE / 2) + (r.dy || 0);
                                                            const cx = 2 * apexX - mx, cy = 2 * apexY - my;
                                                            return { r, idx, d: `M${ax},${ay} Q${cx},${cy} ${bx},${by}`, lx: apexX, ly: apexY };
                                                        });
                                                    return (
                                                        <>
                                                            <div className="mp-relmap-stage" style={{ width: SIZE, height: SIZE }}>
                                                                <svg className="mp-relmap-svg" width={SIZE} height={SIZE}>
                                                                    <defs>
                                                                        <marker id="mp-rel-arrow" markerWidth="9" markerHeight="9" refX="7.5" refY="3" orient="auto" markerUnits="userSpaceOnUse">
                                                                            <path d="M0,0 L7.5,3 L0,6 Z" fill="var(--theme-color, #c9a87c)" />
                                                                        </marker>
                                                                    </defs>
                                                                    {edgeGeo.map((g) => (
                                                                        <path key={g.idx} d={g.d} fill="none" stroke="var(--theme-color, #c9a87c)"
                                                                            strokeWidth="1.6" strokeOpacity="0.6" markerEnd="url(#mp-rel-arrow)" />
                                                                    ))}
                                                                </svg>
                                                                {edgeGeo.map((g) => g.r.label ? (
                                                                    <span key={`l${g.idx}`} className="mp-relmap-edge-label"
                                                                        style={{ left: g.lx, top: g.ly }}
                                                                        onMouseDown={(ev) => onLabelDragStart(ev, g.idx)}
                                                                        title="드래그해서 선과 함께 이동">{g.r.label}</span>
                                                                ) : null)}
                                                                {nodes.map((n, i) => (
                                                                    <div key={i} className={`mp-relmap-node${n.c.role === 'protagonist' ? ' mp-relmap-node--center' : ''}`}
                                                                        style={{ left: n.x, top: n.y, borderColor: ROLE_COLOR[n.c.role] || '#9aa0a6' }}
                                                                        title={n.c.personality || ''}>
                                                                        <span className="mp-relmap-node__name">{n.c.name}</span>
                                                                        <span className="mp-relmap-node__role">{ROLE_LABEL[n.c.role] || n.c.role}</span>
                                                                    </div>
                                                                ))}
                                                            </div>
                                                            <div className="mp-relmap-legend">
                                                                {rolesPresent.map(r => (
                                                                    <span key={r} className="mp-relmap-legend__item">
                                                                        <span className="mp-relmap-legend__dot" style={{ background: ROLE_COLOR[r] || '#9aa0a6' }} />
                                                                        {ROLE_LABEL[r] || r}
                                                                    </span>
                                                                ))}
                                                                <span className="mp-relmap-legend__hint">선 = 직접 입력한 관계</span>
                                                            </div>

                                                            {/* 관계 직접 입력 */}
                                                            <div className="mp-relmap-editor">
                                                                <div className="mp-relmap-editor__row">
                                                                    <select value={relFrom} onChange={e => setRelFrom(e.target.value)}>
                                                                        <option value="">인물 A</option>
                                                                        {all.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
                                                                    </select>
                                                                    <input value={relLabel} onChange={e => setRelLabel(e.target.value)}
                                                                        placeholder="관계 (예: 첫사랑)" maxLength={40} />
                                                                    <select value={relTo} onChange={e => setRelTo(e.target.value)}>
                                                                        <option value="">인물 B</option>
                                                                        {all.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
                                                                    </select>
                                                                    <button className="mp-relmap-add" onClick={handleSaveRelation}>{editIdx !== null ? '저장' : '추가'}</button>
                                                                    {editIdx !== null && (
                                                                        <button className="mp-relmap-cancel" onClick={resetRelEditor}>취소</button>
                                                                    )}
                                                                </div>
                                                                {relations.length > 0 && (
                                                                    <div className="mp-relmap-rellist">
                                                                        {relations.map((r, i) => (
                                                                            <div key={i} className={`mp-relmap-rel${editIdx === i ? ' mp-relmap-rel--editing' : ''}`}>
                                                                                <span className="mp-relmap-rel__text">
                                                                                    {nameById[r.from] || '(삭제된 인물)'}
                                                                                    <b className="mp-relmap-rel__label">{r.label || '관계'}</b>
                                                                                    <span className="mp-relmap-rel__arrow">→</span>
                                                                                    {nameById[r.to] || '(삭제된 인물)'}
                                                                                </span>
                                                                                <button className="mp-relmap-rel__edit" onClick={() => handleEditRelation(i)} title="수정">✎</button>
                                                                                <button className="mp-relmap-rel__del" onClick={() => handleDeleteRelation(i)} title="삭제">✕</button>
                                                                            </div>
                                                                        ))}
                                                                    </div>
                                                                )}
                                                            </div>

                                                            <div className="mp-relmap-info">
                                                                {all.map(c => (
                                                                    <div key={c.id} className="mp-relmap-card">
                                                                        <div className="mp-relmap-card__head">
                                                                            <span className="mp-relmap-card__dot" style={{ background: ROLE_COLOR[c.role] || '#9aa0a6' }} />
                                                                            <span className="mp-relmap-card__name">{c.name}</span>
                                                                            <span className="mp-relmap-card__role">{ROLE_LABEL[c.role] || c.role}</span>
                                                                        </div>
                                                                        {c.personality && <p className="mp-relmap-card__desc">{c.personality}</p>}
                                                                    </div>
                                                                ))}
                                                            </div>
                                                        </>
                                                    );
                                                })()
                                            }
                                        </div>
                                    )}

                                    {wikiTab === '타임라인' && (
                                        <div className="mp-timeline">
                                            {!wiki.story_summary
                                                ? <p className="mp-empty">아직 줄거리가 없어요. 대화를 이어가면 자동 생성됩니다.</p>
                                                : (
                                                    <>
                                                        <div className="mp-timeline-label">AI가 요약한 줄거리</div>
                                                        {wiki.story_summary.split(/\n|·|•|-\s/).filter(Boolean).map((line, i) => (
                                                            <div key={i} className="mp-timeline-item">
                                                                <div className="mp-timeline-dot" />
                                                                <p className="mp-timeline-text">{line.trim()}</p>
                                                            </div>
                                                        ))}
                                                    </>
                                                )
                                            }
                                        </div>
                                    )}
                                </>
                            )}
                        </div>
                    </div>
                )}

                {/* ── 문장 보관함 ── */}
                {active === '문장 보관함' && (
                    <div className="mp-sentences">
                        {!sentences || sentences.length === 0 ? (
                            <p className="mp-empty">저장된 문장이 없어요.<br />AI 피드백 버블의 💾 버튼으로 저장할 수 있어요.</p>
                        ) : sentences.map(s => (
                            <div key={s.id} className="mp-sentence">
                                <div className="mp-sentence__top">
                                    {s.label && <span className="mp-sentence__label">{s.label}</span>}
                                    <button className="mp-sentence__del" onClick={() => handleDeleteSentence(s.id)}>×</button>
                                </div>
                                <p className="mp-sentence__text">"{s.content}"</p>
                                {s.session_title && <span className="mp-sentence__src">— {s.session_title}</span>}
                            </div>
                        ))}
                    </div>
                )}

                {/* ── 오답노트 (자주 틀린 맞춤법) ── */}
                {active === '오답노트' && (() => {
                    const view = (errorNotebook ?? []).slice().sort((a, b) =>
                        errSort === 'recent' ? (b.last ?? 0) - (a.last ?? 0) : (b.count ?? 0) - (a.count ?? 0)
                    ).slice(0, 10);
                    return (
                        <div className="mp-errnote">
                            <div className="mp-errnote__head">
                                <h2 className="mp-errnote__title">오답노트</h2>
                                <p className="mp-errnote__desc">교정에서 잡힌 맞춤법 실수 상위 10개예요.</p>
                            </div>
                            {!errorNotebook || errorNotebook.length === 0 ? (
                                <p className="mp-empty">아직 기록된 오답이 없어요.<br />채팅·집필 중 교정을 받으면 여기에 쌓여요.</p>
                            ) : (
                                <>
                                    <div className="mp-errnote__sort">
                                        <button
                                            className={`mp-errnote__sortbtn${errSort === 'count' ? ' mp-errnote__sortbtn--on' : ''}`}
                                            onClick={() => setErrSort('count')}
                                        >가장 많이 틀린 순</button>
                                        <button
                                            className={`mp-errnote__sortbtn${errSort === 'recent' ? ' mp-errnote__sortbtn--on' : ''}`}
                                            onClick={() => setErrSort('recent')}
                                        >최신순</button>
                                    </div>
                                    <ul className="mp-errnote__list">
                                        {view.map((e, i) => (
                                            <li key={i} className={`mp-errnote__item${e.count >= 3 ? ' mp-errnote__item--frequent' : ''}`}>
                                                <span className="mp-errnote__wrong">{e.original}</span>
                                                <span className="mp-errnote__arrow">→</span>
                                                <span className="mp-errnote__right">{e.corrected}</span>
                                                {e.type && <span className="mp-errnote__type">{e.type}</span>}
                                                <span className="mp-errnote__count">{e.count}회</span>
                                                <button
                                                    className="mp-errnote__del"
                                                    onClick={() => handleDeleteError(e.original)}
                                                    aria-label="삭제"
                                                    title="이 오답 삭제"
                                                >×</button>
                                            </li>
                                        ))}
                                    </ul>
                                </>
                            )}
                        </div>
                    );
                })()}

                {/* ── AI 작가 기록 (Phase 2) ── */}
                {active === 'AI 작가 기록' && (
                    <div className="mp-author-records">
                        {!authorRecords || authorRecords.length === 0 ? (
                            <p className="mp-empty">아직 작가와 협업한 기록이 없어요.</p>
                        ) : (() => {
                            const totalWorks = profile?.stats?.total_works || 0;
                            return authorRecords.map(r => {
                                const pct = totalWorks > 0 ? Math.round(r.work_count / totalWorks * 100) : 0;
                                return (
                                    <div key={r.author_id} className="mp-author-card">
                                        <div className="mp-author-card__name">{r.name}</div>
                                        <div className="mp-author-pct">
                                            <div className="mp-author-pct__bar">
                                                <div className="mp-author-pct__fill" style={{ width: `${pct}%` }} />
                                            </div>
                                            <span className="mp-author-pct__label">{pct}%</span>
                                        </div>
                                        <div className="mp-author-card__stats">
                                            <div className="mp-author-card__stat">
                                                <span className="mp-author-card__stat-val">{r.work_count}</span>
                                                <span className="mp-author-card__stat-lbl">함께 쓴 작품</span>
                                            </div>
                                            <div className="mp-author-card__stat">
                                                <span className="mp-author-card__stat-val">{r.dialogue_count}</span>
                                                <span className="mp-author-card__stat-lbl">누적 대화</span>
                                            </div>
                                        </div>
                                    </div>
                                );
                            });
                        })()}
                    </div>
                )}

                {/* ── 갤러리 ── */}
                {active === '갤러리' && (() => {
                    const author = VIDEO_AUTHORS.find(a => a.id === selectedVideoAuthor);

                    return (
                        <div className="mp-video-gallery">
                            <div className="mp-video-authors">
                                {VIDEO_AUTHORS.map(a => (
                                    <button
                                        key={a.id}
                                        className={`mp-video-author ${selectedVideoAuthor === a.id ? 'mp-video-author--active' : ''}`}
                                        onClick={() => setSelectedVideoAuthor(a.id)}
                                    >
                                        {a.name}
                                    </button>
                                ))}
                            </div>

                            <div className="mp-video-grid">
                                {REACTION_VIDEOS.map(video => (
                                    <div key={video.key} className="mp-video-card">
                                        <video
                                            className="mp-video"
                                            src={`${author.path}/${video.key}.mp4`}
                                            preload="metadata"
                                            muted
                                            onClick={() => setPreviewVideo(`${author.path}/${video.key}.mp4`)}
                                        />
                                        <div className="mp-video-title">{video.label}</div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    );
                })()}

                {previewVideo && (
                    <VideoPreviewModal
                        src={previewVideo}
                        onClose={() => setPreviewVideo(null)}
                    />
                )}

                {/* ── 업적 (Phase 2) ── */}
                {active === '업적' && (
                    <div className="mp-achievements">
                        {!achievements ? (
                            <p className="mp-empty">불러오는 중...</p>
                        ) : (
                            <>
                                <div className="mp-ach-summary">
                                    달성 {achievements.filter(a => a.unlocked).length} / {achievements.length}
                                </div>
                                <div className="mp-ach-grid">
                                    {achievements.map(a => (
                                        <div key={a.id} className={`mp-ach-card ${a.unlocked ? 'mp-ach-card--unlocked' : ''}`}>
                                            <span className="mp-ach-icon">{a.icon}</span>
                                            <span className="mp-ach-title">{a.title}</span>
                                            <span className="mp-ach-desc">{a.desc}</span>
                                        </div>
                                    ))}
                                </div>
                            </>
                        )}
                    </div>
                )}

                {/* ── 환경설정 ── */}
                {active === '환경설정' && (
                    <div className="mp-settings">
                        <div className="mp-setting-card">
                            <div className="mp-setting-title">
                                배경음악
                            </div>
                            <div className="mp-setting-body">
                                <input
                                    type="range"
                                    min="0"
                                    max="1"
                                    step="0.01"
                                    value={bgmVolume}
                                    onChange={(e) => {
                                        const volume = Number(e.target.value);

                                        setBgmVolume(volume);
                                        localStorage.setItem('bgm_volume', String(volume));

                                        window.dispatchEvent(
                                            new Event('bgm-volume-changed')
                                        );
                                    }}
                                />

                                <button
                                    onClick={() => {
                                        const next = !bgmPlaying;

                                        setBgmPlaying(next);
                                        localStorage.setItem('bgm_playing', String(next));

                                        window.dispatchEvent(
                                            new Event('bgm-playing-changed')
                                        );
                                    }}
                                >
                                    {bgmPlaying ? '🔊' : '🔇'}
                                </button>
                            </div>
                        </div>
                        <div className="mp-setting-card">
                            <div className="mp-setting-title">
                                영상
                            </div>

                            <div className="mp-setting-body">
                                <input
                                    type="range"
                                    min="0"
                                    max="1"
                                    step="0.05"
                                    value={videoVolume}
                                    onChange={(e) => {
                                        const volume = Number(e.target.value);

                                        setVideoVolume(volume);
                                        setGlobalVideoVolume(volume);
                                    }}
                                />

                                <span>
                                    {videoVolume === 0 ? '🔇' : '🔊'}
                                </span>
                            </div>
                        </div>
                    </div>
                )}

                {/* ── 알림설정 ── */}
                {active === '알림설정' && (
                    <div className="mp-placeholder">
                        <p>알림설정은 준비 중이에요.</p>
                    </div>
                )}
            </main>

            {showTasteOnboarding && (
                <TasteOnboarding
                    onComplete={handleTasteComplete}
                    onClose={() => setShowTasteOnboarding(false)}
                />
            )}
        </div>
    );
}

export default MyPage;
