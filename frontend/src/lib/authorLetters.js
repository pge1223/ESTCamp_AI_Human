// 오늘의 작가 편지
// 편지 구조: { paragraphs: ['문단1', '문단2', ...] }
// 줄바꿈은 문단 내 \n 사용, CSS에서 white-space: pre-line 처리

const AUTHOR_IDS = ['hanyeoreum', 'charoun', 'baekya', 'kimdohyeon'];

export const AUTHOR_DISPLAY_NAMES = {
    hanyeoreum: '한여름',
    charoun:    '차로운',
    baekya:     '백야',
    kimdohyeon: '김도현',
};

// ── 일반 편지 (매일 로테이션) ────────────────────────────────
export const REGULAR = {
    hanyeoreum: [
        {
            paragraphs: [
                '오늘은 사건보다 감정을 먼저 써보세요.',
                '독자는 누가 무엇을 했는지보다,\n그 순간 어떤 마음이었는지를 더 오래 기억하거든요.',
            ],
        },
        {
            paragraphs: [
                '당신이 멈춰 있는 동안에도\n{protagonist}은(는) 그 장면에 그대로 서 있어요.',
                '오늘은 한 문장이라도 그를 앞으로 걸어가게 해주세요.',
            ],
        },
    ],
    charoun: [
        {
            paragraphs: [
                '좋은 추리는 정답이 아니라 의심에서 시작됩니다.',
                '지금 당신의 이야기에\n독자가 의심할 만한 단서는 충분한가요?',
            ],
        },
        {
            paragraphs: [
                '아직 해결되지 않은 질문이 하나쯤 남아있어야 합니다.',
                '독자가 다음 장을 넘기게 만드는 건\n사건보다 궁금증이니까요.',
            ],
        },
    ],
    baekya: [
        {
            paragraphs: [
                '공포는 괴물이 아니라 침묵에서 태어납니다.',
                '오늘은 설명을 하나 지우고,\n그 빈자리를 어둠으로 채워보세요.',
            ],
        },
        {
            paragraphs: [
                '아무 일도 일어나지 않는 장면은 의외로 무섭습니다.',
                '독자는 이유를 모르는 불안을 가장 오래 기억하니까요.',
            ],
        },
    ],
    kimdohyeon: [
        {
            paragraphs: [
                '좋은 문장은 멋있게 쓰는 것이 아니라\n솔직하게 쓰는 것에서 시작됩니다.',
                '오늘은 당신이 진짜 느낀 것을 적어보세요.',
            ],
        },
        {
            paragraphs: [
                '모든 이야기는 결국 사람에 대한 기록입니다.',
                '사건보다 사람을 바라보면\n문장은 스스로 길을 찾기 시작합니다.',
            ],
        },
    ],
};

// ── 상황별 편지 ───────────────────────────────────────────────
export const SITUATION = {

    // 3일 미접속 (author 랜덤)
    absence: {
        hanyeoreum: {
            paragraphs: [
                '요즘 바쁜가요?',
                '괜찮아요.\n이야기는 도망가지 않으니까요.',
                '다만 당신이 돌아왔을 때,\n주인공들이 반갑게 맞아줄 수 있도록 너무 오래 기다리게 하진 말아주세요.',
            ],
        },
        charoun: {
            paragraphs: [
                '마지막 장면 이후 72시간.',
                '사건은 아직 해결되지 않았습니다.',
                '미뤄둔 단서가 있다면,\n오늘 다시 한 번 살펴보는 건 어떨까요?',
            ],
        },
        baekya: {
            paragraphs: [
                '조용하군요.',
                '너무 조용해서 오히려 불안할 정도입니다.',
                '당신의 이야기는 아직 끝나지 않았습니다.',
            ],
        },
        kimdohyeon: {
            paragraphs: [
                '잠시 멈춰 있는 것도 창작의 일부입니다.',
                '하지만 너무 오래 멈추면,\n문장보다 망설임이 더 익숙해질지도 모릅니다.',
            ],
        },
    },

    // 집필 완료 (해당 작가)
    completed: {
        hanyeoreum: {
            paragraphs: [
                '축하해요.',
                '이제 이 이야기는 당신만의 것이 아닙니다.',
                '누군가의 마음속에서 다시 살아갈 준비를 마쳤네요.',
            ],
        },
        charoun: {
            paragraphs: [
                '모든 복선이 회수되었나요?',
                '아니어도 괜찮습니다.',
                '완벽한 결말보다 중요한 건 끝까지 써냈다는 사실이니까요.',
            ],
        },
        baekya: {
            paragraphs: [
                '끝났군요.',
                '마지막 문장을 적은 순간,\n당신은 이 세계를 떠났습니다.',
                '하지만 독자는 이제 막 들어가고 있겠죠.',
            ],
        },
        kimdohyeon: {
            paragraphs: [
                '한 편의 이야기가 끝났다는 건\n한 사람의 시간이 기록되었다는 뜻입니다.',
                '수고 많았습니다.',
            ],
        },
    },

    // 슬럼프 (최근 이용 작가)
    slump: {
        hanyeoreum: {
            paragraphs: [
                '모든 장면이 설레야 하는 건 아니에요.',
                '오늘은 좋은 문장 대신\n평범한 문장 하나만 써도 충분합니다.',
            ],
        },
        charoun: {
            paragraphs: [
                '지금 필요한 건 영감이 아니라 다음 질문입니다.',
                '"그 다음엔 무슨 일이 일어날까?"',
                '그 답부터 적어보세요.',
            ],
        },
        baekya: {
            paragraphs: [
                '막막함도 이야기의 일부입니다.',
                '어쩌면 지금 당신은\n가장 어두운 장면을 지나고 있는지도 모르겠군요.',
            ],
        },
        kimdohyeon: {
            paragraphs: [
                '쓰고 싶은 마음이 없을 때도 있습니다.',
                '그럴 땐 쓰려고 하지 말고,\n왜 쓰기 시작했는지를 떠올려보세요.',
            ],
        },
    },

    // 1만자 달성 (함께 달성한 작가)
    milestone_10k: {
        hanyeoreum: {
            paragraphs: [
                '벌써 1만 자네요.',
                '{protagonist}도 이제 제법 이야기에 익숙해졌을 것 같은데요?',
            ],
        },
        charoun: {
            paragraphs: [
                '1만 자는 꽤 많은 분량입니다.',
                '이제 독자는 당신이 준비한 함정에\n조금씩 걸려들고 있을지도 모르겠군요.',
            ],
        },
        baekya: {
            paragraphs: [
                '이야기는 조금씩 깊어지고 있습니다.',
                '아직은 입구일 뿐이지만요.',
            ],
        },
        kimdohyeon: {
            paragraphs: [
                '1만 자는 단순한 숫자가 아닙니다.',
                '당신이 포기하지 않았다는 기록입니다.',
            ],
        },
    },

    // 첫 작품 생성 (해당 작가)
    first_work: {
        hanyeoreum: {
            paragraphs: [
                '반가워요.',
                '오늘부터 우리는 함께 사랑 이야기를 만들어갈 거예요.',
                '너무 완벽하려고 하지 말고,\n먼저 마음을 써보세요.',
            ],
        },
        charoun: {
            paragraphs: [
                '첫 사건이 시작되었습니다.',
                '범인보다 먼저,\n독자의 호기심을 설계해봅시다.',
            ],
        },
        baekya: {
            paragraphs: [
                '새로운 문이 열렸군요.',
                '안쪽에는 무엇이 있을지,\n아직 아무도 모릅니다.',
            ],
        },
        kimdohyeon: {
            paragraphs: [
                '첫 문장은 언제나 어렵습니다.',
                '하지만 가장 중요한 건\n좋은 시작이 아니라 시작했다는 사실입니다.',
            ],
        },
    },
};

// ── 상황 감지 ─────────────────────────────────────────────────
/**
 * dashboard, profile, works 데이터를 받아 편지 상황과 작가를 결정합니다.
 * @returns {{ situation: string, authorId: string }}
 */
export function determineSituation(dashboard, profile, works) {
    const dayIndex = Math.floor(Math.random() * 10000);
    const mostRecentAuthor = dashboard?.resume_work?.author_id ?? null;
    const totalChars  = profile?.stats?.total_chars  ?? 0;
    const totalWorks  = profile?.stats?.total_works  ?? 0;

    // 첫 작품 (작품 1개 + 글자 수 매우 적음)
    if (totalWorks === 1 && totalChars < 200) {
        return { situation: 'first_work', authorId: mostRecentAuthor };
    }

    // 1만자 달성 (10000~11000 구간)
    if (totalChars >= 10000 && totalChars < 11000) {
        return { situation: 'milestone_10k', authorId: mostRecentAuthor };
    }

    // 집필 완료 (가장 최근 작품이 completed)
    if (dashboard?.resume_work && works) {
        const latest = works.find(w => w.session_id === dashboard.resume_work.session_id);
        if (latest?.status === 'completed') {
            return { situation: 'completed', authorId: mostRecentAuthor };
        }
    }

    // 3일 미접속 (랜덤 작가)
    if (dashboard?.days_since_active !== null && dashboard?.days_since_active >= 3) {
        const randomAuthor = AUTHOR_IDS[dayIndex % AUTHOR_IDS.length];
        return { situation: 'absence', authorId: randomAuthor };
    }

    // 슬럼프 (작품 있는데 이번 주 글자 수 0)
    if (totalWorks > 0 && (dashboard?.weekly_chars ?? 0) === 0) {
        return { situation: 'slump', authorId: mostRecentAuthor };
    }

    // 기본 (최근 작가 기준 로테이션)
    return { situation: 'regular', authorId: mostRecentAuthor };
}

// ── 편지 반환 ─────────────────────────────────────────────────
/**
 * @param {string} situation
 * @param {string|null} authorId
 * @param {string|null} protagonistName - 최근 작품 주인공 이름 ({protagonist} 플레이스홀더 치환)
 * @returns {{ author: string, paragraphs: string[] }}
 */
export function getDailyLetter(situation, authorId, protagonistName) {
    const dayIndex = Math.floor(Math.random() * 10000);

    // regular는 항상 랜덤 로테이션, 상황별 편지만 해당 작가 고정
    const aid = (situation !== 'regular' && authorId && AUTHOR_IDS.includes(authorId))
        ? authorId
        : AUTHOR_IDS[dayIndex % AUTHOR_IDS.length];

    const displayName = AUTHOR_DISPLAY_NAMES[aid];

    let rawParagraphs;
    if (situation === 'regular') {
        const letters = REGULAR[aid];
        rawParagraphs = letters[dayIndex % letters.length].paragraphs;
    } else {
        const bucket = SITUATION[situation];
        if (!bucket) return getDailyLetter('regular', aid, protagonistName);
        rawParagraphs = (bucket[aid] ?? bucket[AUTHOR_IDS[0]]).paragraphs;
    }

    const paragraphs = protagonistName
        ? rawParagraphs.map(p => p.replace(/\{protagonist\}/g, protagonistName))
        : rawParagraphs.map(p => p.replace(/\{protagonist\}은\(는\)/g, '주인공은').replace(/\{protagonist\}/g, '주인공'));

    return { author: displayName, paragraphs };
}
