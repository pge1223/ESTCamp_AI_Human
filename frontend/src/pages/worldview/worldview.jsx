/* src/pages/worldview/worldview.jsx */
import React, { useState, useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import '../../index.css';
import './worldview.css';
import { WriteIcon, ExitIcon, ChevronRight, ShuffleIcon } from '../../components/icons';
import { createWorldview, generateHiddenFacts } from '../../lib/worldviewApi';
import { getAuthor, getQuestions } from '../../lib/authorsApi';
import { getRandomWorldExamples } from '../../lib/worldExampleApi';
import { useAuthorTheme, resolveAuthorId } from '../../hooks/useAuthorTheme';
import IntroVideo from '../../components/IntroVideo';
import { toast } from '../../lib/toast';
import { getTemplates, deleteTemplate } from '../../lib/worldTemplates';

function Worldview() {
    const location = useLocation();
    const navigate = useNavigate();

    const authorId = resolveAuthorId(location.state?.authorId);
    useAuthorTheme(authorId);

    const [currentStep, setCurrentStep] = useState(1);
    // 1. 세계관(worlds) 테이블 관련 상태
    const [title, setTitle] = useState('');
    const [description, setDescription] = useState('');
    const [genre, setGenre] = useState('');
    const [setting, setSetting] = useState('');
    const [rules, setRules] = useState('');
    const [questions, setQuestions] = useState([]);
    const [typedText, setTypedText] = useState('');

    const [worldExample, setWorldExample] = useState(null);
    const [exampleModalOpen, setExampleModalOpen] = useState(false);
    const [randomExamples, setRandomExamples] = useState([]);
    const [selectedExample, setSelectedExample] = useState(null);
    const [loadModalOpen, setLoadModalOpen] = useState(false);
    const [myTemplates, setMyTemplates] = useState([]);
    const [openingConfirm, setOpeningConfirm] = useState(false);
    const [pendingNav, setPendingNav] = useState(null);

    // 2. 등장인물(characters) 테이블 스키마에 맞춘 초기 구조 정의    
    const createNewCharacter = (index = 0) => ({
        id: Date.now() + Math.random(), // 임시 고유 키
        name: '',
        role: index === 0 ? 'protagonist' : 'supporting',
        personality: '',
        system_prompt: '',
        address_rules: [],
    });

    const [characters, setCharacters] = useState([createNewCharacter(0)]);
    const [selectedAuthor, setSelectedAuthor] = useState(null);
    const [isLoading, setIsLoading] = useState(true);
    const [showIntro, setShowIntro] = useState(true);
    const [saving, setSaving] = useState(false);
    const [savingStep, setSavingStep] = useState('');
    const currentDialogue = questions.find((question) => question.step === currentStep);
    const [look, setLook] = useState({ x: 0, y: 0 });
    const stateRef = React.useRef(null);

    useEffect(() => {
        const fetchData = async () => {
            try {
                const authorData = await getAuthor(authorId);
                setSelectedAuthor(authorData);

                const questionsData = await getQuestions(authorId);

                setQuestions(
                    questionsData.dialogues || questionsData || []
                );

                const examples = await getRandomWorldExamples(authorId, 1);
                setWorldExample(examples[0]);
            } catch (error) {
                console.error("Error fetching data:", error);
                toast("작가 정보를 불러오지 못했습니다.", "error");
            } finally {
                setIsLoading(false);
            }
        };

        if (authorId) {
            fetchData();
        }
    }, [authorId]);

    useEffect(() => {
        if (selectedAuthor && !genre) {
            setGenre(selectedAuthor.genre);
        }
    }, [selectedAuthor, genre]);

    useEffect(() => {
        const handleMouseMove = (e) => {
            const x = (e.clientX / window.innerWidth - 0.5);
            const y = (e.clientY / window.innerHeight - 0.5);

            setLook({ x, y });
        };

        window.addEventListener('mousemove', handleMouseMove);

        return () => {
            window.removeEventListener('mousemove', handleMouseMove);
        };
    }, []);

    useEffect(() => {
        const fullText = currentDialogue?.text || '';
        setTypedText('');

        let index = 0;

        const timer = setInterval(() => {
            setTypedText(fullText.slice(0, index + 1));
            index += 1;

            if (index >= fullText.length) {
                clearInterval(timer);
            }
        }, 100);

        return () => clearInterval(timer);
    }, [currentDialogue?.text]);

    // 등장인물 핸들러
    const handleAddCharacter = () => {
        setCharacters((prev) => [...prev, createNewCharacter(prev.length)]);
    };

    const handleRemoveCharacter = (id) => {
        if (characters.length > 1) {
            setCharacters((prev) => prev.filter((char) => char.id !== id));
        }
    };

    const handleCharacterChange = (id, field, value) => {
        setCharacters((prev) =>
            prev.map((char) =>
                char.id === id ? { ...char, [field]: value } : char
            )
        );
    };

    const validateCurrentStep = () => {
        if (currentStep === 2 && !title.trim()) {
            toast('세계관 제목을 입력해주세요.');
            return false;
        }

        if (currentDialogue?.field === 'characters') {
            const protagonist = characters[0];
            if (!protagonist || !protagonist.name.trim()) {
                toast('주인공의 이름을 반드시 입력해야 합니다.');
                return false;
            }
        }

        return true;
    };

    const handleNext = () => {
        if (!validateCurrentStep()) return;

        if (currentStep < questions.length) {
            setCurrentStep((prev) => prev + 1);
        }
    };

    const handlePrev = () => {
        if (currentStep > 1) {
            setCurrentStep((prev) => prev - 1);
        }
    };

    const handleSave = async () => {
        if (!title.trim()) {
            toast('세계관 제목을 입력해주세요.');
            const titleStep = questions.find(q => q.field === 'title')?.step || 2;
            setCurrentStep(titleStep);
            return;
        }

        const protagonist = characters[0];
        if (!protagonist || !protagonist.name.trim()) {
            toast('주인공의 이름을 반드시 입력해야 합니다.');
            const characterStep = questions.find(q => q.field === 'characters')?.step || 6;
            setCurrentStep(characterStep);
            return;
        }

        const validCharacters = characters
            .filter((char) => char.name.trim())
            .map(({ id, ...charData }) => charData);

        setSaving(true);
        setSavingStep('세계관 저장 중...');

        try {
            const { worldId, sessionId } = await createWorldview({
                world: { title, description, genre, setting, rules },
                characters: validCharacters,
                authorId,
            });

            if (authorId === 2) {
                setSavingStep('추리 설정 생성 중...');
                try {
                    await generateHiddenFacts(worldId);
                } catch {
                    // 생성 실패해도 진행
                }
            }

            setPendingNav({ worldId, sessionId, authorId });
            setOpeningConfirm(true);
        } catch (err) {
            toast(`저장 실패: ${err.message}`, "error");
        } finally {
            setSaving(false);
            setSavingStep('');
        }
    };

    const handleCancel = () => {
        if (window.confirm("작성 중인 내용이 저장되지 않습니다. 뒤로 가시겠습니까?")) {
            navigate(-1);
        }
    };

    const handleOpenExampleModal = async () => {
        try {
            const examples = await getRandomWorldExamples(authorId, 3);
            setRandomExamples(examples);
            setSelectedExample(null);
            setExampleModalOpen(true);
        } catch (error) {
            toast("랜덤 예시를 불러오지 못했습니다.", "error");
        }
    };

    const handleOpenLoadModal = () => {
        setMyTemplates(getTemplates());
        setLoadModalOpen(true);
    };

    const handleApplyMyTemplate = (tmpl) => {
        setTitle(tmpl.title ?? '');
        setDescription(tmpl.description ?? '');
        setSetting(tmpl.setting ?? '');
        setGenre(tmpl.genre ?? '');
        setRules(Array.isArray(tmpl.rules) ? tmpl.rules.join('\n') : (tmpl.rules ?? ''));
        if (tmpl.characters?.length) {
            setCharacters(
                tmpl.characters.map((c, i) => ({
                    id: Date.now() + Math.random() + i,
                    name: c.name ?? '',
                    role: c.role ?? (i === 0 ? 'protagonist' : 'supporting'),
                    personality: c.personality ?? '',
                    system_prompt: c.prompt ?? '',
                    address_rules: c.address_rules ?? [],
                })),
            );
        }
        setLoadModalOpen(false);
        toast('세계관을 불러왔어요.', 'success');
    };

    const handleDeleteMyTemplate = (id, e) => {
        e.stopPropagation();
        deleteTemplate(id);
        setMyTemplates(getTemplates());
    };

    const handleApplyExample = () => {
        if (!selectedExample) return;

        setTitle(selectedExample.title || '');
        setDescription(selectedExample.description || '');
        setSetting(selectedExample.setting || '');

        setRules(
            Array.isArray(selectedExample.rules)
                ? selectedExample.rules.join('\n')
                : selectedExample.rules || ''
        );

        setCharacters(
            (selectedExample.characters || []).map((char, index) => ({
                id: Date.now() + Math.random() + index,
                name: char.name || '',
                role: index === 0 ? 'protagonist' : 'supporting',
                personality: char.personality || '',
                system_prompt: char.system_prompt || ''
            }))
        );

        const confirmStep = questions.find(q => q.field === 'confirm')?.step || questions.length;
        setCurrentStep(confirmStep);
        setExampleModalOpen(false);
    };

    stateRef.current = { currentDialogue, handleNext, handleSave };

    useEffect(() => {
        const handleGlobalKeyDown = (e) => {
            if (e.key === 'Enter') {
                // 한글 입력 조합 중복 방지
                if (e.isComposing) return;

                // 현재 포커스가 textarea에 가 있다면 줄바꿈을 해야 하므로 전역 엔터 동작을 막음
                if (document.activeElement && document.activeElement.tagName === 'TEXTAREA') {
                    return;
                }

                // ref를 통해 안전하게 최신 함수와 대화 정보 가져오기
                if (!stateRef.current) return;
                const { currentDialogue: activeDialogue, handleNext: nextFn, handleSave: saveFn } = stateRef.current;

                if (activeDialogue?.field === 'confirm') {
                    saveFn();
                } else {
                    e.preventDefault(); // 기본 엔터 동작 방지
                    nextFn();
                }
            }
        };

        window.addEventListener('keydown', handleGlobalKeyDown);
        return () => {
            window.removeEventListener('keydown', handleGlobalKeyDown);
        };
    }, []);

    const renderStepInput = () => {
        switch (currentDialogue?.field) {
            case 'intro':
                return (
                    <div className="form-group">
                        <div className="label-header">
                            <label className="form-label">안내</label>
                            <div style={{ display: 'flex', gap: 6 }}>
                                <button type="button" className="btn-add" onClick={handleOpenExampleModal}>
                                    랜덤예시
                                </button>
                                <button type="button" className="btn-add" onClick={handleOpenLoadModal}>
                                    불러오기
                                </button>
                            </div>
                        </div>
                        <div className="intro-guide-box">
                            <p>작가와 대화하듯이 세계관을 하나씩 설정합니다.</p>
                            <p>준비되었다면 아래 버튼을 눌러 시작해주세요.</p>
                        </div>
                    </div>
                );

            case 'title':
                return (
                    <div className="form-group">
                        <label className="form-label">세계관 제목</label>
                        <input
                            type="text"
                            className="form-input"
                            placeholder={worldExample?.title
                                ? `예: ${worldExample.title}`
                                : "예: 무림외전, 네오 서울 2026"}
                            value={title}
                            onChange={(e) => setTitle(e.target.value)}
                        />
                    </div>
                );

            case 'description':
                return (
                    <div className="form-group">
                        <label className="form-label">세계관 요약 설명</label>
                        <textarea
                            className="form-textarea"
                            rows={4}
                            placeholder={
                                worldExample?.description
                                    ? `예: ${worldExample.description}`
                                    : "이 세계관을 관통하는 요약 한 줄을 적어주세요."
                            }
                            value={description}
                            onChange={(e) => setDescription(e.target.value)}
                        />
                    </div>
                );

            case 'setting':
                return (
                    <div className="form-group">
                        <label className="form-label">시대 및 공간 배경</label>
                        <textarea
                            className="form-textarea"
                            rows={4}
                            placeholder={
                                worldExample?.setting
                                    ? `예: ${worldExample.setting}`
                                    : "가상의 역사, 지리적 특징, 시대 분위기 등을 적어주세요."
                            }
                            value={setting}
                            onChange={(e) => setSetting(e.target.value)}
                        />
                    </div>
                );

            case 'rules':
                return (
                    <div className="form-group">
                        <label className="form-label">세계관 특별 규칙</label>
                        <textarea
                            className="form-textarea"
                            rows={5}
                            placeholder={
                                Array.isArray(worldExample?.rules)
                                    ? `예: ${worldExample.rules.join("\n")}`
                                    : "개념, 마법 법칙, 사회적 제약 사항 등을 적어주세요."
                            }
                            value={rules}
                            onChange={(e) => setRules(e.target.value)}
                        />
                    </div>
                );

            case 'characters':
                return (
                    <div className="form-group">
                        <div className="label-header">
                            <label className="form-label">등장인물 설정</label>
                            <button type="button" className="btn-add" onClick={handleAddCharacter}>
                                + 캐릭터 추가
                            </button>
                        </div>

                        <div className="character-card-list">
                            {characters.map((char, index) => (
                                <div key={char.id} className="character-card">
                                    <div className="char-card-header">
                                        <span className="char-index">
                                            # {index === 0 ? '주인공' : `${index + 1}번째 인물`}
                                        </span>
                                        <button
                                            type="button"
                                            className="btn-card-remove"
                                            onClick={() => handleRemoveCharacter(char.id)}
                                            disabled={characters.length === 1 || index === 0}
                                        >
                                            삭제
                                        </button>
                                    </div>

                                    <div className="form-row align-end">
                                        <div className="flex-2">
                                            <label className="char-sub-label">이름</label>
                                            <input
                                                type="text"
                                                className="form-input"
                                                placeholder={
                                                    worldExample?.characters?.[index]?.name
                                                        ? `예: ${worldExample.characters[index].name}`
                                                        : (index === 0 ? "주인공 이름 (필수)" : "캐릭터 이름")
                                                }
                                                value={char.name}
                                                onChange={(e) =>
                                                    handleCharacterChange(char.id, 'name', e.target.value)
                                                }
                                            />
                                        </div>

                                        <div className="flex-2">
                                            <label className="char-sub-label">성격</label>
                                            <input
                                                type="text"
                                                className="form-input"
                                                placeholder={
                                                    worldExample?.characters?.[index]?.personality
                                                        ? `예: ${worldExample.characters[index].personality}`
                                                        : "예: 냉철함, 츤데레, 다정함"
                                                }
                                                value={char.personality}
                                                onChange={(e) =>
                                                    handleCharacterChange(char.id, 'personality', e.target.value)
                                                }
                                            />
                                        </div>

                                        <div className="flex-2">
                                            <label className="char-sub-label">역할</label>
                                            <select
                                                className="form-select"
                                                value={char.role}
                                                disabled={true}
                                                onChange={(e) =>
                                                    handleCharacterChange(char.id, 'role', e.target.value)
                                                }
                                            >
                                                <option value="protagonist">주인공</option>
                                                <option value="supporting">조연</option>
                                            </select>
                                        </div>
                                    </div>

                                    <div className="flex-2">
                                        <label className="char-sub-label">특성</label>
                                        <textarea
                                            className="form-textarea"
                                            placeholder={
                                                worldExample?.characters?.[index]?.system_prompt
                                                    ? `예: ${worldExample.characters[index].system_prompt}`
                                                    : "AI가 이 역할을 연기할 때 지켜야 할 어조나 규칙"
                                            }
                                            value={char.system_prompt}
                                            onChange={(e) =>
                                                handleCharacterChange(char.id, 'system_prompt', e.target.value)
                                            }
                                        />
                                    </div>

                                    {/* 호칭 규칙 */}
                                    <div className="flex-2">
                                        <label className="char-sub-label">호칭 규칙 <span className="char-sub-hint">({char.name || '이 캐릭터'}이 상대를 부르는 호칭)</span></label>
                                        {(char.address_rules || []).map((rule, rIdx) => (
                                            <div key={rIdx} className="address-rule-row">
                                                <select
                                                    className="form-select address-rule-select"
                                                    value={rule.target_name}
                                                    onChange={(e) => {
                                                        const updated = [...(char.address_rules || [])];
                                                        updated[rIdx] = { ...rule, target_name: e.target.value };
                                                        handleCharacterChange(char.id, 'address_rules', updated);
                                                    }}
                                                >
                                                    <option value="">상대 캐릭터</option>
                                                    {characters
                                                        .filter(c => c.id !== char.id && c.name.trim())
                                                        .map(c => (
                                                            <option key={c.id} value={c.name}>{c.name}</option>
                                                        ))}
                                                </select>
                                                <span className="address-rule-arrow">를</span>
                                                <input
                                                    type="text"
                                                    className="form-input address-rule-input"
                                                    placeholder="이렇게 부름"
                                                    value={rule.address}
                                                    onChange={(e) => {
                                                        const updated = [...(char.address_rules || [])];
                                                        updated[rIdx] = { ...rule, address: e.target.value };
                                                        handleCharacterChange(char.id, 'address_rules', updated);
                                                    }}
                                                />
                                                <button
                                                    type="button"
                                                    className="btn-rule-remove"
                                                    onClick={() => {
                                                        const updated = (char.address_rules || []).filter((_, i) => i !== rIdx);
                                                        handleCharacterChange(char.id, 'address_rules', updated);
                                                    }}
                                                >✕</button>
                                            </div>
                                        ))}
                                        <button
                                            type="button"
                                            className="btn-add-rule"
                                            onClick={() => {
                                                const updated = [...(char.address_rules || []), { target_name: '', address: '' }];
                                                handleCharacterChange(char.id, 'address_rules', updated);
                                            }}
                                        >+ 호칭 추가</button>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                );

            case 'confirm':
                return (
                    <div className="form-group">
                        <label className="form-label">세계관</label>
                        <div className="summary-box">
                            <p><strong>장르</strong> {genre || '-'}</p>
                            <p><strong>제목</strong> {title || '-'}</p>
                            <p><strong>요약</strong> {description || '-'}</p>
                            <p><strong>배경</strong> {setting || '-'}</p>
                            <p><strong>규칙</strong> {rules || '-'}</p>
                            <p><strong>등장인물</strong> {characters.filter((char) => char.name.trim()).length}명</p>
                        </div>
                    </div>
                );

            default:
                return null;
        }
    };

    if (!authorId) {
        return (
            <div className="error-container">
                <p>선택된 작가가 없습니다. 메인 페이지로 돌아갑니다.</p>
                <button onClick={() => navigate('/')}>메인으로 가기</button>
            </div>
        );
    }

    return (
        <>
        <div className="app-container">
            {showIntro && (
                <IntroVideo
                    authorId={authorId}
                    onCancel={() => navigate('/')}
                    onSelect={() => setShowIntro(false)}
                />
            )}

            <div className="app-wrapper">
                <header className="header">
                    <img src="/assets/logo.png" alt="NodeVelture Logo" className="header-image" />
                    <h1 className="logo" onClick={() => navigate('/')} style={{ cursor: 'pointer' }}>
                        NodeVelture
                    </h1>
                </header>

                {selectedAuthor && (
                    <div className="selected-author-banner">
                        <img src={selectedAuthor.image} alt={selectedAuthor.name} className="banner-avatar" />
                        <div className="banner-info">
                            <span className="banner-genre">{selectedAuthor.genre}</span>
                            <h3 className="banner-name">{selectedAuthor.name} 작가와 세계관 설계</h3>
                        </div>
                    </div>
                )}

                <div className="worldview-content">
                    <div className="worldview-chat-layout">
                        <div className="author-side">
                            <div
                                className="author-bg-layer"
                                style={{ backgroundImage: `url(${selectedAuthor?.bgImage})` }}
                            />
                            <div
                                className="avatar-wrapper"
                                style={{
                                    transform: `
                                        perspective(1000px)
                                        rotateY(${look.x * 20}deg)
                                        rotateX(${-look.y * 15}deg)
                                        translate(${look.x * 30}px, ${look.y * 15}px)
                                    `
                                }}
                            >
                                <img
                                    src={currentDialogue?.image || selectedAuthor?.image}
                                    alt={selectedAuthor?.name || '작가'}
                                    className="worldview-author-image avatar breathing"
                                />
                            </div>
                            <div className="worldview-step-indicator">
                                {currentStep} / {questions.length}
                            </div>
                        </div>

                        <div className="input-side">
                            <div className="author-dialogue-box">
                                {typedText}
                            </div>

                            <div className="step-input-area">
                                {renderStepInput()}
                            </div>

                            <div className="action-buttons">
                                <button
                                    type="button"
                                    className="btn-cancel"
                                    onClick={currentStep === 1 ? handleCancel : handlePrev}
                                >
                                    <ExitIcon /> {currentStep === 1 ? '취소하기' : '이전'}
                                </button>

                                {currentDialogue?.field === 'confirm' ? (
                                    <button
                                        type="button"
                                        className="btn-save"
                                        onClick={handleSave}
                                        disabled={saving}
                                    >
                                        <WriteIcon /> {saving ? (savingStep || '저장 중...') : '세계관 생성'}
                                    </button>
                                ) : (
                                    <button
                                        type="button"
                                        className="btn-save"
                                        onClick={handleNext}
                                    >
                                        다음 <ChevronRight />
                                    </button>
                                )}
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            {exampleModalOpen && (
                <div className="example-modal-overlay">
                    <div className="example-modal">
                        {!selectedExample ? (
                            <>
                                <div className="example-modal-header">
                                    <div>랜덤 세계관 예시</div>

                                    <button
                                        type="button"
                                        className="btn-add"
                                        onClick={handleOpenExampleModal}
                                    >
                                        <ShuffleIcon />
                                    </button>
                                </div>

                                <div className="example-title-list">
                                    {randomExamples.map((example) => (
                                        <button
                                            key={example.id || example.title}
                                            type="button"
                                            className="example-title-button"
                                            onClick={() => setSelectedExample(example)}
                                        >
                                            제목 : {example.title}
                                        </button>
                                    ))}
                                </div>

                                <div className="example-modal-actions">
                                    <button type="button" className="btn-cancel" onClick={() => setExampleModalOpen(false)}>
                                        취소
                                    </button>
                                </div>
                            </>
                        ) : (
                            <>
                                <h3>{selectedExample.title}</h3>

                                <div className="example-detail-box">
                                    <p>
                                        <strong>요약</strong><br />
                                        - {selectedExample.description}
                                    </p>
                                    <p>
                                        <strong>배경</strong><br />
                                        - {selectedExample.setting}
                                    </p>
                                    <p>
                                        <strong>규칙</strong><br />
                                        {Array.isArray(selectedExample.rules)
                                            ? selectedExample.rules.map((rule, index) => (
                                                <span key={index}>- {rule}<br /></span>
                                            ))
                                            : selectedExample.rules}
                                    </p>
                                    <p>
                                        <strong>등장인물</strong><br />
                                        {(selectedExample.characters || []).map((char, index) => (
                                            <div key={index} className="example-character-box">
                                                - {char.name} ( {char.personality} )
                                                <div className="example-character-prompt">
                                                    특성 : {char.system_prompt}
                                                </div>
                                            </div>
                                        ))}
                                    </p>
                                </div>

                                <div className="example-modal-actions">
                                    <button type="button" className="btn-cancel" onClick={() => setSelectedExample(null)}>
                                        취소
                                    </button>
                                    <button type="button" className="btn-save" onClick={handleApplyExample}>
                                        적용
                                    </button>
                                </div>
                            </>
                        )}
                    </div>
                </div>
            )}
        </div>

        {/* 오프닝 자동 생성 확인 팝업 */}
        {openingConfirm && pendingNav && (
            <div className="example-modal-overlay">
                <div className="example-modal" style={{ maxWidth: 360, padding: '28px 24px', textAlign: 'center' }}>
                    <p style={{ fontSize: 16, fontWeight: 700, marginBottom: 8 }}>첫 장면을 자동으로 생성할까요?</p>
                    <p style={{ fontSize: 13, color: 'var(--text-muted)', lineHeight: 1.7, marginBottom: 24 }}>
                        세계관 정보를 바탕으로 오프닝 나레이션을 자동 생성합니다.<br />
                        나중에 직접 입력하려면 아니오를 선택하세요.
                    </p>
                    <div style={{ display: 'flex', gap: 10, justifyContent: 'center' }}>
                        <button
                            type="button"
                            className="example-modal-close"
                            style={{ padding: '10px 24px', border: '1px solid var(--text-muted)', borderRadius: 10, fontSize: 14, cursor: 'pointer' }}
                            onClick={() => {
                                setOpeningConfirm(false);
                                navigate('/chat', { state: { worldId: pendingNav.worldId, chatId: pendingNav.sessionId, authorId: pendingNav.authorId, generateOpening: false } });
                            }}
                        >아니오</button>
                        <button
                            type="button"
                            className="btn-save"
                            style={{ padding: '10px 28px', borderRadius: 10, fontSize: 14, flex: 'none' }}
                            onClick={() => {
                                setOpeningConfirm(false);
                                navigate('/chat', { state: { worldId: pendingNav.worldId, chatId: pendingNav.sessionId, authorId: pendingNav.authorId, generateOpening: true } });
                            }}
                        >예</button>
                    </div>
                </div>
            </div>
        )}

        {/* 내서재 불러오기 모달 */}
        {loadModalOpen && (
            <div className="example-modal-overlay" onClick={() => setLoadModalOpen(false)}>
                <div className="example-modal" onClick={e => e.stopPropagation()}>
                    <div className="example-modal-header">
                        <div>내서재 세계관 보관함</div>
                        <button type="button" className="example-modal-close" onClick={() => setLoadModalOpen(false)}>✕</button>
                    </div>
                    {myTemplates.length === 0 ? (
                        <p style={{ padding: '32px 20px', textAlign: 'center', color: 'var(--text-muted)', fontSize: 14, lineHeight: 1.7 }}>
                            저장된 세계관이 없어요.<br />세계관 수정 화면에서 내서재 저장을 해보세요.
                        </p>
                    ) : (
                        <div className="example-title-list">
                            {myTemplates.map(t => (
                                <div
                                    key={t.id}
                                    style={{ display: 'flex', alignItems: 'center', gap: 8 }}
                                >
                                    <button
                                        type="button"
                                        className="example-title-item"
                                        style={{ flex: 1, textAlign: 'left' }}
                                        onClick={() => handleApplyMyTemplate(t)}
                                    >
                                        <span style={{ fontWeight: 700 }}>{t.title}</span>
                                        {t.genre && <span style={{ marginLeft: 8, fontSize: 12, opacity: 0.7 }}>{t.genre}</span>}
                                        <span style={{ display: 'block', fontSize: 12, opacity: 0.6, marginTop: 2 }}>
                                            {t.characters?.length > 0 && `인물 ${t.characters.length}명 · `}
                                            {new Date(t.saved_at).toLocaleDateString('ko-KR')}
                                        </span>
                                    </button>
                                    <button
                                        type="button"
                                        style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', fontSize: 13, padding: '4px 8px' }}
                                        onClick={e => handleDeleteMyTemplate(t.id, e)}
                                    >✕</button>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            </div>
        )}
        </>
    );
}

export default Worldview;