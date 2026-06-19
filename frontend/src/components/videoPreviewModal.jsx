import { useEffect, useRef, useState } from 'react';
import {
    getGlobalVideoVolume,
    setGlobalVideoVolume,
    applyGlobalVideoVolume
} from '../lib/videoVolume';

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

const closeButtonStyle = {
    position: 'absolute',
    top: '20px',
    right: '20px',
    zIndex: 2,
    width: '48px',
    height: '48px',
    borderRadius: '50%',
    border: 'none',
    background: 'rgba(0, 0, 0, 0.45)',
    color: '#fff',
    fontSize: '24px',
    cursor: 'pointer',
};

function VideoPreviewModal({ src, onClose }) {
    const videoRef = useRef(null);
    const [volume, setVolume] = useState(() => getGlobalVideoVolume());

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
                    src={src}
                    autoPlay
                    loop
                    playsInline
                    preload="auto"
                />

                <button
                    style={closeButtonStyle}
                    onClick={onClose}
                >
                    ✕
                </button>

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

export default VideoPreviewModal;