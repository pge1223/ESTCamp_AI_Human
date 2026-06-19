// src/components/IntroVideo.jsx
import { useEffect, useRef, useState } from 'react';
import { getGlobalVideoVolume, setGlobalVideoVolume, applyGlobalVideoVolume } from '../lib/videoVolume';
import { ExitIcon, ChevronRight } from './icons';

const wrapStyle = {
    position: 'fixed',
    inset: 0,
    zIndex: 9999,
    display: 'flex',
    justifyContent: 'center',
    alignItems: 'center',
    background: 'rgba(255, 255, 255, 0.8)',
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

const buttonStyle = {
    position: 'absolute',
    left: '50%',
    bottom: '20px',
    transform: 'translateX(-50%)',
    zIndex: 2,
    display: 'flex',
    gap: '12px',
};

const cancelButtonStyle = {
    minWidth: '180px',
    height: '56px',
    padding: '0 24px',
    borderRadius: '8px',
    fontSize: '1.1rem',
    fontWeight: 600,
    cursor: 'pointer',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: '8px',
    transition: 'opacity 0.2s',
    background: '#222',
    border: '1px solid rgba(255, 255, 255, 0.15)',
    color: '#ccc',
};

const submitButtonStyle = {
    minWidth: '180px',
    height: '56px',
    padding: '0 24px',
    borderRadius: '8px',
    fontSize: '1.1rem',
    fontWeight: 600,
    cursor: 'pointer',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: '8px',
    transition: 'opacity 0.2s',
    background: 'var(--theme-color)',
    border: 'none',
    color: '#fff',
};

function IntroVideo({ authorId, onCancel, onSelect }) {
    const videoRef = useRef(null);
    const [volume, setVolume] = useState(() => getGlobalVideoVolume());

    const videoSrc = `/assets/author${authorId}/intro.mp4`;

    useEffect(() => {
        const video = videoRef.current;
        if (!video) return;

        setGlobalVideoVolume(volume);
        applyGlobalVideoVolume(video);
    }, [volume]);

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

                <div style={buttonStyle}>
                    <button style={cancelButtonStyle} onClick={onCancel}>
                        <ExitIcon /> 취소
                    </button>

                    <button style={submitButtonStyle} onClick={onSelect}>
                        선택 <ChevronRight />
                    </button>
                </div>
            </div>
        </div>
    );
}

export default IntroVideo;