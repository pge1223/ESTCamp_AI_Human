// src/components/icons.jsx
import React from 'react';

// 로그아웃 아이콘
export const ExitIcon = ({ size = 20, color = "#FFFFFF", className = "" }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" className={className}    >
        <path d="M13 4H7C5.89543 4 5 4.89543 5 6V18C5 19.1046 5.89543 20 7 20H13" stroke={color} strokeWidth="2" strokeLinecap="round" />
        <path d="M10 12H21M21 12L17 8M21 12L17 16" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
);

// 작성/편집 아이콘
export const WriteIcon = ({ size = 20, color = "#ffffff", className = "" }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" className={className}>
        <path d="M13.5 7L17 10.5M4 20L5.5 15.5L16.5 4.5C17.3284 3.67157 18.6716 3.67157 19.5 4.5C20.3284 5.32843 20.3284 6.67157 19.5 7.5L8.5 18.5L4 20Z" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
        <path d="M15 20H20" stroke={color} strokeWidth="2" strokeLinecap="round" />
    </svg>
);

// 화살표 아이콘 (버튼 우측)
export const ChevronRight = ({ width = 10, height = 15, color = "#ffffff", className = "" }) => (
    <svg width={width} height={height} viewBox="0 0 10 20" fill="none" xmlns="http://www.w3.org/2000/svg" className={className}    >
        <path d="M2 2L8 10L2 18" stroke={color} strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
);

// 랜덤 / 소용돌이 아이콘
export const ShuffleIcon = ({ size = 20, color = "#ffffff", className = "" }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" className={className} >
        <path d="M20 12A8 8 0 1 1 17.5 6.2" stroke={color} strokeWidth="2" strokeLinecap="round" />
        <path d="M20 4V9H15" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
);