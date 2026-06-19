// src/components/loadingVideo.jsx
import { useEffect, useMemo, useRef, useState } from 'react';
import { getGlobalVideoVolume, setGlobalVideoVolume, applyGlobalVideoVolume } from '../lib/videoVolume';

const wrapStyle = {
    position: 'fixed',
    inset: 0,
    zIndex: 9999,
    display: 'flex',
    justifyContent: 'center',
    alignItems: 'center',
    // 흰 바탕 대신 '어두운 반투명 + 블러' — 뒤 페이지(테마색)를 어둡게 가려
    // 핑크/앰버가 안 비치게 함(흰 반투명은 밝은 핑크가 비쳐서 불투명으로 막았던 것).
    background: 'rgba(18, 16, 26, 0.72)',
    backdropFilter: 'blur(10px)',
    WebkitBackdropFilter: 'blur(10px)',
};

const videoBoxStyle = {
    position: 'relative',
    height: '80%',
    aspectRatio: '16 / 9',
    borderRadius: '24px',
    overflow: 'hidden',
};

const videoStyle = {
    width: '100%',
    height: '100%',
    objectFit: 'cover',
    borderRadius: '24px',
};

const volumeStyle = {
    position: 'absolute',
    right: '20px',
    bottom: '20px',
    zIndex: 2,
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    padding: '8px 12px',
    borderRadius: '999px',
    background: 'rgba(0, 0, 0, 0.45)',
    color: '#fff',
};

const tips = [
    `[ TIP ] 대사는 큰따옴표 안에 쓰세요\n예) "왜 그러는 거야?"`,
    `[ TIP ] 독백·속마음은 작은따옴표 안에 쓰세요\n예) '이 사람, 뭔가 숨기고 있어.'`,
    `[ TIP ] 행동·서술은 따옴표 없이 그냥 쓰세요\n예) 스카프를 건네며 고개를 돌린다`,
    `[ TIP ] @등장인물은 특정 인물 시점으로 전환돼요\n예) @에드워드 "무슨 일이야?"`,
];

const subtitleStyle = {
    position: 'absolute',
    left: '50%',
    bottom: '20px',
    transform: 'translateX(-50%)',
    zIndex: 2,
    maxWidth: '80%',
    padding: '12px 18px',
    color: '#fff',
    fontSize: '18px',
    lineHeight: 1.5,
    textAlign: 'center',
    whiteSpace: 'pre-line',
    wordBreak: 'keep-all',
};

function LoadingVideo({ loading = true, minDuration = 5000, onFinish }) {
    const startTimeRef = useRef(Date.now());
    const videoRef = useRef(null);
    const [volume, setVolume] = useState(() => getGlobalVideoVolume());

    const videoSrc = useMemo(() => {
        const authorId = Math.floor(Math.random() * 4) + 1;
        return `/assets/author${authorId}/loading.mp4`;
    }, []);

    useEffect(() => {
        const video = videoRef.current;
        if (!video) return;

        setGlobalVideoVolume(volume);
        applyGlobalVideoVolume(video);
    }, [volume]);

    const tipText = useMemo(() => {
        return tips[Math.floor(Math.random() * tips.length)];
    }, []);

    useEffect(() => {
        if (loading) return;

        const elapsed = Date.now() - startTimeRef.current;
        const remain = Math.max(0, minDuration - elapsed);

        const timer = setTimeout(() => {
            onFinish?.();
        }, remain);

        return () => clearTimeout(timer);
    }, [loading, minDuration, onFinish]);

    return (
        <div style={wrapStyle}>
            <div style={videoBoxStyle}>
                <video
                    ref={videoRef}
                    style={videoStyle}
                    src={videoSrc}
                    autoPlay
                    playsInline
                    preload="auto"
                />

                <div style={subtitleStyle}>
                    {tipText}
                </div>

                <div style={volumeStyle}>
                    <span>{volume === 0 ? '🔇' : '🔊'}</span>
                    <input
                        type="range"
                        min="0"
                        max="1"
                        step="0.05"
                        value={volume}
                        onChange={(e) => setVolume(Number(e.target.value))}
                    />
                </div>
            </div>
        </div>
    );
}

export default LoadingVideo;