/** BgmPlayer의 audio 엘리먼트를 SettingsModal 등 외부에서 직접 제어하기 위한 모듈.
 *  window.dispatchEvent를 통한 간접 호출은 브라우저 autoplay 정책에 막히므로,
 *  사용자 제스처 컨텍스트(onClick) 안에서 직접 호출해야 함. */

let _audio = null;

export function registerBgmAudio(audio) {
  _audio = audio;
}

export function bgmPlay() {
  if (!_audio) return Promise.resolve();
  return _audio.play();
}

export function bgmPause() {
  if (!_audio) return;
  _audio.pause();
}
