import { useEffect, useRef, useState } from 'react';
import { registerBgmAudio } from '../lib/bgmController';

const AUTHORS = {
    author1: '백야',
    author2: '차로운',
    author3: '한여름',
    author4: '김도현',
};

const VOLUME_KEY = 'bgm_volume';
const PLAYING_KEY = 'bgm_playing';
const TIME_KEY = 'bgm_time';
const LAST_AUTHOR_KEY = 'bgm_last_author';

const playerStyle = {
    position: 'fixed',
    top: '16px',
    right: '16px',
    zIndex: 9998,
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'flex-end',
};

const toggleStyle = {
    border: 'none',
    borderRadius: '999px',
    padding: '10px 14px',
    cursor: 'pointer',
    background: 'color-mix(in srgb, var(--theme-color) 30%, var(--card-main))',
    color: 'var(--text-main)',
    boxShadow: '0 4px 14px rgba(0,0,0,0.18)',
};

const panelStyle = {
    marginTop: '8px',
    width: '180px',
    padding: '14px',
    borderRadius: '16px',
    background: 'rgba(255,255,255,0.92)',
    boxShadow: '0 4px 18px rgba(0,0,0,0.18)',
    backdropFilter: 'blur(8px)',
};

const titleStyle = {
    fontWeight: 700,
    marginBottom: '4px',
};

const playButtonStyle = {
    width: '100%',
    border: 'none',
    borderRadius: '10px',
    padding: '8px 10px',
    cursor: 'pointer',
    background: 'var(--color-main, #222)',
    color: '#fff',
    marginBottom: '10px',
};

const volumeStyle = {
    width: '100%',
};

function getCurrentAuthor() {
    const attr = document.documentElement.getAttribute('data-author');
    const saved = localStorage.getItem('selectedTheme');

    if (AUTHORS[attr]) return attr;
    if (AUTHORS[saved]) return saved;

    return 'author4'; // 기본 BGM: 김도현
}

export default function BgmPlayer() {
    const audioRef = useRef(null);

    const [author, setAuthor] = useState(getCurrentAuthor);
    const [open, setOpen] = useState(false);
    const [playing, setPlaying] = useState(() => {
        const saved = localStorage.getItem(PLAYING_KEY);
        if (saved === null) return true;
        return saved === 'true';
    });
    const [volume, setVolume] = useState(() => {
        const saved = localStorage.getItem(VOLUME_KEY);
        return saved !== null ? Number(saved) : 0.2;
    });

    const bgmSrc = `/assets/${author}/bgm.mp3`;

    // 페이지 로드 직후엔 브라우저 autoplay 정책으로 재생 불가 →
    // 첫 사용자 제스처(클릭·터치·키) 시점에 한 번만 재생 시도
    useEffect(() => {
        const tryPlay = () => {
            const audio = audioRef.current;
            if (!audio) return;
            const shouldPlay = localStorage.getItem(PLAYING_KEY);
            if (shouldPlay === null || shouldPlay === 'true') {
                audio.play()
                    .then(() => setPlaying(true))
                    .catch(() => {});
            }
            document.removeEventListener('click', tryPlay);
            document.removeEventListener('keydown', tryPlay);
            document.removeEventListener('touchstart', tryPlay);
        };
        document.addEventListener('click', tryPlay);
        document.addEventListener('keydown', tryPlay);
        document.addEventListener('touchstart', tryPlay);
        return () => {
            document.removeEventListener('click', tryPlay);
            document.removeEventListener('keydown', tryPlay);
            document.removeEventListener('touchstart', tryPlay);
        };
    }, []);

    useEffect(() => {
        const observer = new MutationObserver(() => {
            const nextAuthor = getCurrentAuthor();

            setAuthor((prev) => {
                if (prev === nextAuthor) return prev;

                const audio = audioRef.current;
                if (audio) {
                    localStorage.setItem(TIME_KEY, String(audio.currentTime || 0));
                    localStorage.setItem(LAST_AUTHOR_KEY, prev);
                }

                return nextAuthor;
            });
        });

        observer.observe(document.documentElement, {
            attributes: true,
            attributeFilter: ['data-author'],
        });

        return () => observer.disconnect();
    }, []);

    // localStorage 쓰기는 SettingsModal이 전담 — 여기서 playing 상태 변화로 덮어쓰면
    // autoplay 실패 시 사용자 preference가 소실되는 버그 발생하므로 제거

    useEffect(() => {
        const audio = audioRef.current;
        if (!audio) return;

        audio.volume = volume;
        localStorage.setItem(VOLUME_KEY, String(volume));
    }, [volume]);

    useEffect(() => {
        const audio = audioRef.current;
        if (!audio) return;

        audio.pause();
        audio.src = bgmSrc;
        audio.loop = true;
        audio.volume = volume;

        const handleLoadedMetadata = () => {
            const lastAuthor = localStorage.getItem(LAST_AUTHOR_KEY);
            const savedTime = Number(localStorage.getItem(TIME_KEY) || 0);

            if (lastAuthor === author && savedTime > 0 && savedTime < audio.duration) {
                audio.currentTime = savedTime;
            } else {
                audio.currentTime = 0;
            }

            localStorage.setItem(LAST_AUTHOR_KEY, author);

            const _saved = localStorage.getItem(PLAYING_KEY);
            if (_saved === null || _saved === 'true') { // null = 첫 방문, 기본 ON
                audio.play()
                    .then(() => setPlaying(true))
                    .catch(() => {
                        setPlaying(false);
                    });
            }
        };

        audio.addEventListener('loadedmetadata', handleLoadedMetadata);
        audio.load();

        return () => {
            audio.removeEventListener('loadedmetadata', handleLoadedMetadata);
        };
    }, [author]);

    useEffect(() => {
        const audio = audioRef.current;
        if (!audio) return;

        const saveTime = () => {
            localStorage.setItem(TIME_KEY, String(audio.currentTime || 0));
            localStorage.setItem(LAST_AUTHOR_KEY, author);
        };

        const interval = setInterval(saveTime, 1000);

        window.addEventListener('beforeunload', saveTime);

        return () => {
            clearInterval(interval);
            window.removeEventListener('beforeunload', saveTime);
            saveTime();
        };
    }, [author]);

    useEffect(() => {
        const syncVolume = () => {
            const saved = localStorage.getItem(VOLUME_KEY);

            if (saved !== null) {
                setVolume(Number(saved));
            }
        };

        window.addEventListener('bgm-volume-changed', syncVolume);

        return () => {
            window.removeEventListener('bgm-volume-changed', syncVolume);
        };
    }, []);

    useEffect(() => {
        const syncPlaying = () => {
            const audio = audioRef.current;
            if (!audio) return;

            const shouldPlay = localStorage.getItem(PLAYING_KEY) === 'true';

            if (shouldPlay) {
                audio.play()
                    .then(() => setPlaying(true))
                    .catch(() => {
                        // 재생 실패해도 localStorage preference는 건드리지 않음
                        setPlaying(false);
                    });
            } else {
                audio.pause();
                setPlaying(false);
            }
        };

        window.addEventListener(
            'bgm-playing-changed',
            syncPlaying
        );

        return () => {
            window.removeEventListener(
                'bgm-playing-changed',
                syncPlaying
            );
        };
    }, []);

    const togglePlay = async () => {
        const audio = audioRef.current;
        if (!audio) return;

        if (playing) {
            audio.pause();
            setPlaying(false);
            return;
        }

        try {
            await audio.play();
            setPlaying(true);
        } catch (error) {
            console.warn('BGM 재생 실패:', error);
            setPlaying(false);
        }
    };

    return (
        <div style={playerStyle}>
            <audio ref={(el) => { audioRef.current = el; registerBgmAudio(el); }} />
            {/*
            <button
                type="button"
                style={toggleStyle}
                onClick={() => setOpen((prev) => !prev)}
            >
                {open ? '♪ 접기' : '♪'}
            </button>

            {open && (
                <div style={panelStyle}>
                    <div style={titleStyle}>
                        {AUTHORS[author]}
                    </div>

                    <button
                        type="button"
                        style={playButtonStyle}
                        onClick={togglePlay}
                    >
                        {playing ? '일시정지' : '재생'}
                    </button>

                    <input
                        style={volumeStyle}
                        type="range"
                        min="0"
                        max="1"
                        step="0.01"
                        value={volume}
                        onChange={(e) => setVolume(Number(e.target.value))}
                    />
                </div>
            )}
            */}
        </div>
    );
}