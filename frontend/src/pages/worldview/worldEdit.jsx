import React, { useEffect, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import {
  getSession, getWorld, getCharacters, getDialogues,
  updateWorld, createCharacter, updateCharacter,
} from '../../lib/worldviewApi';
import { useAuthorTheme, resolveAuthorId } from '../../hooks/useAuthorTheme';
import { toast } from '../../lib/toast';
import { getTemplates, saveTemplate, deleteTemplate } from '../../lib/worldTemplates';
import './worldview.css';
import './worldEdit.css';

const ROLE_OPTIONS = [
  { value: 'protagonist', label: '주인공' },
  { value: 'supporting', label: '조연' },
  { value: 'villain', label: '빌런' },
  { value: 'narrator', label: '내레이터' },
];

const roleKo = (role) => ROLE_OPTIONS.find((r) => r.value === role)?.label ?? role;

let _newCharSeq = 0;

export default function WorldEdit() {
  const location = useLocation();
  const navigate = useNavigate();
  const { chatId, worldId: worldIdFromState, authorId: authorIdRaw, from: fromMode } = location.state ?? {};

  useAuthorTheme(resolveAuthorId(authorIdRaw));

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [showLoadModal, setShowLoadModal] = useState(false);
  const [templates, setTemplates] = useState([]);
  const [worldId, setWorldId] = useState(worldIdFromState ?? null);
  const [hasDialogues, setHasDialogues] = useState(false);

  const [title, setTitle] = useState('');
  const [genre, setGenre] = useState('');
  const [setting, setSetting] = useState('');
  const [description, setDescription] = useState('');
  const [rules, setRules] = useState('');

  // hard 필드 변경 감지용 기준값(로드 시점 원본)
  const [orig, setOrig] = useState({ genre: '', setting: '' });

  // 기존 캐릭터(id 보유) + 신규 캐릭터(tempId, isNew)
  const [characters, setCharacters] = useState([]);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        let wid = worldIdFromState;
        if (!wid && chatId) {
          const session = await getSession(chatId);
          wid = session.world_id;
        }
        if (!wid) throw new Error('세계관 정보를 찾을 수 없어요.');

        const [w, chars] = await Promise.all([getWorld(wid), getCharacters(wid)]);
        if (!alive) return;

        setWorldId(wid);
        setTitle(w.title ?? '');
        setGenre(w.genre ?? '');
        setSetting(w.setting ?? '');
        setDescription(w.description ?? '');
        setRules(w.rules ?? '');
        setOrig({ genre: w.genre ?? '', setting: w.setting ?? '' });
        setCharacters(
          (chars ?? []).map((c) => ({
            key: c.id,
            id: c.id,
            name: c.name,
            role: c.role,
            personality: c.personality ?? '',
            prompt: c.prompt ?? '',
            address_rules: c.address_rules ?? [],
            isNew: false,
          })),
        );

        if (chatId) {
          try {
            const d = await getDialogues(chatId);
            if (alive) setHasDialogues((d?.length ?? 0) > 0);
          } catch { /* 대화 이력 조회 실패는 경고 표시만 생략 */ }
        }
      } catch (e) {
        toast(e.message ?? '불러오기 실패', 'error');
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => { alive = false; };
  }, [chatId, worldIdFromState]);

  // 이미 진행된 이야기가 있는데 장르/배경(hard 필드)을 바꾸면 경고
  const hardChanged =
    hasDialogues &&
    (genre.trim() !== orig.genre.trim() || setting.trim() !== orig.setting.trim());

  const addCharacter = () =>
    setCharacters((prev) => [
      ...prev,
      { key: `new_${_newCharSeq++}`, name: '', role: 'supporting', personality: '', prompt: '', address_rules: [], isNew: true },
    ]);

  const removeCharacter = (key) =>
    setCharacters((prev) => prev.filter((c) => c.key !== key));

  const changeChar = (key, field, value) =>
    setCharacters((prev) => prev.map((c) => (c.key === key ? { ...c, [field]: value } : c)));

  const handleSaveToLibrary = () => {
    if (!title.trim()) { toast('제목을 입력한 후 저장해주세요.', 'error'); return; }
    saveTemplate({
      title: title.trim(), genre: genre.trim(), setting: setting.trim(),
      description: description.trim(), rules: rules.trim(), characters,
    });
    toast('내서재에 저장했어요.', 'success');
  };

  const handleOpenLoadModal = () => {
    setTemplates(getTemplates());
    setShowLoadModal(true);
  };

  const handleApplyTemplate = (tmpl) => {
    setTitle(tmpl.title ?? '');
    setGenre(tmpl.genre ?? '');
    setSetting(tmpl.setting ?? '');
    setDescription(tmpl.description ?? '');
    setRules(tmpl.rules ?? '');
    if (tmpl.characters?.length) {
      setCharacters(
        tmpl.characters.map((c, i) => ({
          key: `tmpl_${Date.now()}_${i}`,
          id: null,
          name: c.name ?? '',
          role: c.role ?? 'supporting',
          personality: c.personality ?? '',
          prompt: c.prompt ?? '',
          address_rules: c.address_rules ?? [],
          isNew: true,
        })),
      );
    }
    setShowLoadModal(false);
    toast('템플릿을 불러왔어요.', 'success');
  };

  const handleDeleteTemplate = (id, e) => {
    e.stopPropagation();
    deleteTemplate(id);
    setTemplates(getTemplates());
  };

  const handleSave = async () => {
    if (!title.trim()) { toast('제목은 비울 수 없어요.', 'error'); return; }
    const newChars = characters.filter((c) => c.isNew);
    if (newChars.some((c) => !c.name.trim())) {
      toast('추가한 인물의 이름을 채워주세요.', 'error');
      return;
    }

    setSaving(true);
    try {
      await updateWorld(worldId, {
        title: title.trim(),
        genre: genre.trim(),
        setting: setting.trim(),
        description: description.trim(),
        rules: rules.trim(),
      });

      // 기존 캐릭터: 이름·역할은 잠금, 성격/행동지시문만 보강
      await Promise.all(
        characters
          .filter((c) => !c.isNew)
          .map((c) => updateCharacter(worldId, c.id, {
            personality: c.personality,
            prompt: c.prompt,
            address_rules: c.address_rules ?? [],
          })),
      );

      // 신규 캐릭터: 생성
      await Promise.all(
        newChars.map((c) => createCharacter(worldId, {
          name: c.name.trim(),
          role: c.role,
          personality: c.personality,
          prompt: c.prompt,
          address_rules: c.address_rules ?? [],
        })),
      );

      toast('세계관을 저장했어요.', 'success');
      // 들어온 모드로 복귀: 채팅→/chat, 집필형→/editor, 그 외(목록 등)→뒤로.
      if (fromMode === 'editor' && chatId) {
        navigate('/editor', { state: { worldId, chatId, authorId: resolveAuthorId(authorIdRaw) } });
      } else if (fromMode === 'chat' && chatId) {
        navigate('/chat', { state: { worldId, chatId, authorId: resolveAuthorId(authorIdRaw) } });
      } else {
        navigate(-1);
      }
    } catch (e) {
      toast(e.message ?? '저장 실패', 'error');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="worldedit-container">
        <p className="worldedit-loading">세계관을 불러오는 중…</p>
      </div>
    );
  }

  return (
    <div className="worldedit-container">
      <div className="worldedit-wrapper">
        <header className="worldedit-header">
          <button className="worldedit-back" onClick={() => navigate(-1)}>‹</button>
          <h2 className="worldedit-title">세계관 수정</h2>
        </header>

        <p className="worldedit-hint">
          줄거리·규칙·설정을 다듬으면 <strong>다음 대화부터 바로 반영</strong>돼요.
        </p>

        {/* 세계관 기본 정보 */}
        <section className="worldedit-section">
          <div className="form-group">
            <label className="form-label">제목</label>
            <input className="form-input" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="세계관 제목" />
          </div>

          <div className="form-group">
            <label className="form-label">
              장르 {hasDialogues && <span className="worldedit-hard-tag">진행 중 변경 주의</span>}
            </label>
            <input className="form-input" value={genre} onChange={(e) => setGenre(e.target.value)} placeholder="예) 로맨스 / 미스터리" />
          </div>

          <div className="form-group">
            <label className="form-label">
              배경(시대·공간) {hasDialogues && <span className="worldedit-hard-tag">진행 중 변경 주의</span>}
            </label>
            <textarea className="form-textarea height-sm" value={setting} onChange={(e) => setSetting(e.target.value)} placeholder="이야기가 펼쳐지는 시대·공간" />
          </div>

          <div className="form-group">
            <label className="form-label">줄거리·요약</label>
            <textarea className="form-textarea" value={description} onChange={(e) => setDescription(e.target.value)} placeholder="세계관의 핵심 설정과 줄거리" />
          </div>

          <div className="form-group">
            <label className="form-label">규칙·설정</label>
            <textarea className="form-textarea height-sm" value={rules} onChange={(e) => setRules(e.target.value)} placeholder="세계관의 규칙(마법 체계, 금기 등)" />
          </div>
        </section>

        {hardChanged && (
          <div className="worldedit-warning">
            ⚠️ 이미 진행된 이야기가 있어요. 장르·배경을 바꾸면 <strong>지금까지 쓴 내용과 어긋날 수 있어요.</strong> 줄거리·규칙 보강은 안전해요.
          </div>
        )}

        {/* 등장인물 */}
        <section className="worldedit-section">
          <div className="worldedit-section-head">
            <h3 className="worldedit-section-title">등장인물</h3>
            <button className="btn-add" onClick={addCharacter}>+ 인물 추가</button>
          </div>
          <p className="worldedit-char-note">
            기존 인물은 <strong>이름·역할 고정</strong>(진행된 이야기 보호) — 성격·특성만 보강할 수 있어요. 새 인물은 자유롭게 추가하세요.
          </p>

          <div className="character-card-list">
            {characters.map((c, idx) => (
              <div key={c.key} className="character-card">
                <div className="char-card-header">
                  <span className="char-index">#{idx + 1}</span>
                  {c.isNew ? (
                    <span className="char-sub-label worldedit-new-badge">새 인물</span>
                  ) : (
                    <span className="char-sub-label">{c.name} · {roleKo(c.role)}</span>
                  )}
                  {c.isNew && (
                    <button className="btn-remove" onClick={() => removeCharacter(c.key)}>삭제</button>
                  )}
                </div>

                {c.isNew ? (
                  <>
                    <div className="form-group">
                      <label className="form-label">이름</label>
                      <input className="form-input" value={c.name} onChange={(e) => changeChar(c.key, 'name', e.target.value)} placeholder="인물 이름" />
                    </div>
                    <div className="form-group">
                      <label className="form-label">역할</label>
                      <select className="form-select" value={c.role} onChange={(e) => changeChar(c.key, 'role', e.target.value)}>
                        {ROLE_OPTIONS.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}
                      </select>
                    </div>
                  </>
                ) : (
                  <div className="form-group">
                    <label className="form-label">이름 / 역할</label>
                    <input className="form-input" value={`${c.name} (${roleKo(c.role)})`} readOnly />
                  </div>
                )}

                <div className="form-group">
                  <label className="form-label">성격</label>
                  <textarea className="form-textarea height-xs" value={c.personality} onChange={(e) => changeChar(c.key, 'personality', e.target.value)} placeholder="성격·말투·특징" />
                </div>
                <div className="form-group">
                  <label className="form-label">특성(선택)</label>
                  <textarea className="form-textarea height-xs" value={c.prompt} onChange={(e) => changeChar(c.key, 'prompt', e.target.value)} placeholder="AI가 이 인물을 연기할 때 반드시 따를 지시" />
                </div>
                <div className="form-group">
                  <label className="form-label">호칭 규칙 <span className="char-sub-hint">({c.name || '이 캐릭터'}이 상대를 부르는 호칭)</span></label>
                  {(c.address_rules || []).map((rule, rIdx) => (
                    <div key={rIdx} className="address-rule-row">
                      <select
                        className="form-select address-rule-select"
                        value={rule.target_name}
                        onChange={(e) => {
                          const updated = [...(c.address_rules || [])];
                          updated[rIdx] = { ...rule, target_name: e.target.value };
                          changeChar(c.key, 'address_rules', updated);
                        }}
                      >
                        <option value="">상대 캐릭터</option>
                        {characters
                          .filter(other => other.key !== c.key && other.name.trim())
                          .map(other => (
                            <option key={other.key} value={other.name}>{other.name}</option>
                          ))}
                      </select>
                      <span className="address-rule-arrow">를</span>
                      <input
                        type="text"
                        className="form-input address-rule-input"
                        placeholder="이렇게 부름"
                        value={rule.address}
                        onChange={(e) => {
                          const updated = [...(c.address_rules || [])];
                          updated[rIdx] = { ...rule, address: e.target.value };
                          changeChar(c.key, 'address_rules', updated);
                        }}
                      />
                      <button
                        type="button"
                        className="btn-rule-remove"
                        onClick={() => {
                          const updated = (c.address_rules || []).filter((_, i) => i !== rIdx);
                          changeChar(c.key, 'address_rules', updated);
                        }}
                      >✕</button>
                    </div>
                  ))}
                  <button
                    type="button"
                    className="btn-add-rule"
                    onClick={() => {
                      const updated = [...(c.address_rules || []), { target_name: '', address: '' }];
                      changeChar(c.key, 'address_rules', updated);
                    }}
                  >+ 호칭 추가</button>
                </div>
              </div>
            ))}
          </div>
        </section>

        <div className="worldedit-actions">
          <div className="worldedit-actions__library">
            <button className="worldedit-lib-btn" onClick={handleSaveToLibrary} disabled={saving}>내서재 저장</button>
            <button className="worldedit-lib-btn" onClick={handleOpenLoadModal} disabled={saving}>불러오기</button>
          </div>
          <div className="worldedit-actions__right">
            <button className="worldedit-cancel" onClick={() => navigate(-1)} disabled={saving}>취소</button>
            <button className="worldedit-save" onClick={handleSave} disabled={saving}>
              {saving ? '저장 중…' : '저장'}
            </button>
          </div>
        </div>
      </div>

      {/* 내서재 불러오기 모달 */}
      {showLoadModal && (
        <div className="we-modal-overlay" onClick={() => setShowLoadModal(false)}>
          <div className="we-modal" onClick={e => e.stopPropagation()}>
            <div className="we-modal__header">
              <span className="we-modal__title">세계관 보관함</span>
              <button className="we-modal__close" onClick={() => setShowLoadModal(false)}>✕</button>
            </div>
            {templates.length === 0 ? (
              <p className="we-modal__empty">저장된 세계관이 없어요.<br />내서재 저장 버튼으로 저장해보세요.</p>
            ) : (
              <div className="we-modal__list">
                {templates.map(t => (
                  <div key={t.id} className="we-modal__item" onClick={() => handleApplyTemplate(t)}>
                    <div className="we-modal__item-top">
                      <span className="we-modal__item-title">{t.title}</span>
                      {t.genre && <span className="we-modal__item-badge">{t.genre}</span>}
                      <button
                        className="we-modal__item-del"
                        onClick={e => handleDeleteTemplate(t.id, e)}
                        title="삭제"
                      >✕</button>
                    </div>
                    {t.description && <p className="we-modal__item-desc">{t.description}</p>}
                    <div className="we-modal__item-meta">
                      {t.characters?.length > 0 && <span>인물 {t.characters.length}명</span>}
                      <span>{new Date(t.saved_at).toLocaleDateString('ko-KR')}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
