import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import { existsSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

// @neondatabase/neon-js(로그인 의존성, 건혁)가 아직 설치 불가일 때, 로그인 모듈을
// 빈 스텁으로 우회해 앱이 뜨게 한다(로그인만 비활성). 패키지가 설치돼 있으면 alias를
// 끄고 실제 패키지를 쓴다 → 정상 설치되는 순간 자동 복구(이 블록 삭제 불필요).
const neonInstalled = existsSync(
  fileURLToPath(new URL('./node_modules/@neondatabase/neon-js', import.meta.url)),
)
const neonStub = fileURLToPath(new URL('./src/lib/neonStub.jsx', import.meta.url))
const neonStubCss = fileURLToPath(new URL('./src/lib/neonStub.css', import.meta.url))
const neonAlias = neonInstalled ? [] : [
  { find: '@neondatabase/neon-js/ui/css', replacement: neonStubCss },
  { find: '@neondatabase/neon-js/auth/react', replacement: neonStub },
  { find: '@neondatabase/neon-js/auth', replacement: neonStub },
]

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const apiTarget = (env.VITE_API_BASE_URL || 'http://localhost:8000/api').replace('/api', '')

  return {
    plugins: [react()],
    resolve: { alias: neonAlias },
    server: {
      proxy: {
        '/api/v1': {
          target: apiTarget,
          changeOrigin: true,
          headers: {
            'ngrok-skip-browser-warning': 'true',
          },
        },
        '/health': {
          target: apiTarget,
          changeOrigin: true,
        },
        '/api/tts': {
          target: 'http://localhost:3000',
          changeOrigin: true,
        },
      },
    },
  }
})
