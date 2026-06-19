import React, { useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Main from './pages/main/main';
import Worldview from './pages/worldview/worldview';
import WorldEdit from './pages/worldview/worldEdit';
import Chat from './pages/chat/ui';
import Editor from './pages/editor/ui';
import StoryList from './pages/storylist/storylist';
import ReadNovel from './pages/read/read';
import Login from './pages/login/login';
import VoiceProfile from './pages/voice/voice';
import TokenDashboard from './pages/tokenDashboard/tokenDashboard';
import MyPage from './pages/mypage/mypage';
import { ToastHost } from './lib/toast';
import BgmPlayer from './components/BgmPlayer';

function App() {
  useEffect(() => {
    // 앱이 처음 켜질 때 로컬 스토리지에서 테마를 읽어와 html 태그에 세팅
    const savedTheme = localStorage.getItem('selectedTheme');
    if (savedTheme) {
      document.documentElement.setAttribute('data-author', savedTheme);
    } else {
      // 값이 없으면 기본값인 author1 (백야) 셋팅
      document.documentElement.setAttribute('data-author', 'author1');
    }
  }, []);

  return (
    <Router>
      <ToastHost />
      <BgmPlayer />
      <Routes>
        <Route path="/" element={<Main />} />
        <Route path="/worldview" element={<Worldview />} />
        <Route path="/worldedit" element={<WorldEdit />} />
        <Route path="/chat" element={<Chat />} />
        <Route path="/editor" element={<Editor />} />
        <Route path="/storylist" element={<StoryList />} />
        <Route path="/read/:storyId" element={<ReadNovel />} />
        <Route path="/login/*" element={<Login />} />
        <Route path="/auth/*" element={<Login />} />
        <Route path="/voice-profile" element={<VoiceProfile />} />
        <Route path="/tokenDashboard" element={<TokenDashboard />} />
        <Route path="/mypage" element={<MyPage />} />
      </Routes>
    </Router>
  );
}

export default App;