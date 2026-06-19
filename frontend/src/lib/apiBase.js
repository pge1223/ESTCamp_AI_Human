// 개발: Vite 프록시(vite.config.js)가 /api/v1 → 백엔드로 넘기므로 상대경로 사용.
// 배포(Vercel 등 정적 호스팅): 프록시가 없으니 VITE_API_BASE_URL(절대 백엔드 주소, …/api)에
// /v1을 붙여 백엔드를 직접 호출한다. (SSE 스트리밍도 백엔드로 바로 연결돼야 하므로 직접 호출)
const base = import.meta.env.VITE_API_BASE_URL?.replace(/\/+$/, '');
export const API_BASE_URL = (import.meta.env.PROD && base) ? `${base}/v1` : '/api/v1';
