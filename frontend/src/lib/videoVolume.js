// src/lib/videoVolume.js

// 로딩 영상 볼륨
export const VIDEO_VOLUME_KEY = 'global_video_volume';
export const VIDEO_VOLUME_EVENT = 'video-volume-changed';

export const getGlobalVideoVolume = () => {
    const saved = localStorage.getItem(VIDEO_VOLUME_KEY);
    return saved !== null ? Number(saved) : 0.3;
};

export const setGlobalVideoVolume = (volume) => {
    localStorage.setItem(VIDEO_VOLUME_KEY, String(volume));
    window.dispatchEvent(new Event(VIDEO_VOLUME_EVENT));
};

export const applyGlobalVideoVolume = (video) => {
    if (!video) return;
    const volume = getGlobalVideoVolume();
    video.volume = volume;
    video.muted = volume === 0;
};

// 리액션 영상 볼륨 (작가 패널 우측 상단 영상)
export const REACTION_VIDEO_VOLUME_KEY = 'reaction_video_volume';
export const REACTION_VIDEO_VOLUME_EVENT = 'reaction-video-volume-changed';

export const getReactionVideoVolume = () => {
    const saved = localStorage.getItem(REACTION_VIDEO_VOLUME_KEY);
    return saved !== null ? Number(saved) : 0.3;
};

export const setReactionVideoVolume = (volume) => {
    localStorage.setItem(REACTION_VIDEO_VOLUME_KEY, String(volume));
    window.dispatchEvent(new Event(REACTION_VIDEO_VOLUME_EVENT));
};

export const applyReactionVideoVolume = (video) => {
    if (!video) return;
    const volume = getReactionVideoVolume();
    video.volume = volume;
    video.muted = volume === 0;
};