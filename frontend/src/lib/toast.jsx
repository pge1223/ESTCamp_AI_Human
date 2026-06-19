// 공용 토스트 — 네이티브 alert() 대체(논블로킹, 라우팅 넘어가도 유지).
// 사용: import { toast } from '../../lib/toast';  → toast('메시지')  / toast('실패', 'error')
// App 루트에 <ToastHost /> 한 번만 렌더(Routes 밖 → 페이지 이동에도 유지).
import { useEffect, useState } from 'react';
import './toast.css';

let _listeners = [];
let _toasts = [];
let _id = 0;

function _emit() { _listeners.forEach((l) => l(_toasts)); }

export function toast(message, type = 'info', duration = 3000) {
  const t = { id: ++_id, message, type };
  _toasts = [..._toasts, t];
  _emit();
  setTimeout(() => {
    _toasts = _toasts.filter((x) => x.id !== t.id);
    _emit();
  }, duration);
}

export function ToastHost() {
  const [items, setItems] = useState(_toasts);
  useEffect(() => {
    _listeners.push(setItems);
    return () => { _listeners = _listeners.filter((l) => l !== setItems); };
  }, []);
  return (
    <div className="toast-host" role="status" aria-live="polite">
      {items.map((t) => (
        <div
          key={t.id}
          className={`toast toast--${t.type}`}
          data-message={t.message}
        />
      ))}
    </div>
  );
}
