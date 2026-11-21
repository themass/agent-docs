/**
 * 注入适配层(经典脚本,无模块、无依赖)。由 scripts/prepare-web.mjs 拼进 dist/web/public/runtime-config.js,
 * 在 index.html 的 <script src="/public/runtime-config.js"> 处先于 src/main.js 执行。
 *
 * 它只做一件事:在页面加载前把「原生能力」放到 window.XUEXI_NATIVE。frontend/src/platform.js 发现它就用,
 * 没有就用 platform-web(纯 Web)。scene-runtime 内核不改,platform-web 不改。
 *
 * 约束:
 *  - 只在 Capacitor 原生环境(window.Capacitor.isNativePlatform())里安装;浏览器里什么都不做。
 *  - 任一原生调用失败都不能让页面起不来:出错时对应能力回落为 undefined,platform.js 用 Web 版。
 *  - 不打印、不上报学生内容;只有匿名设备标识会进入安全存储。
 */
(function () {
  'use strict';
  var cap = window.Capacitor;
  if (!cap || typeof cap.isNativePlatform !== 'function' || !cap.isNativePlatform()) return;

  var kind = cap.getPlatform(); // 'android' | 'ios'
  var Native = cap.registerPlugin('XuexiNative');   // 自写插件(native/android-plugin)
  var App = cap.Plugins.App;                         // 核心插件 @capacitor/app:返回键、切后台
  var Share = cap.Plugins.Share;                     // @capacitor/share

  var swallow = function () {};

  // ---- 安全存储:对 createKv 暴露「同步 localStorage 形状」,真实数据放 Keychain/Keystore ----
  // 启动时 hydrate() 一次性把键值读进内存;之后同步读写内存,写操作异步落到原生安全存储。
  var mem = new Map();
  var secureStorage = {
    get length() { return mem.size; },
    key: function (i) { return Array.from(mem.keys())[i] || null; },
    getItem: function (k) { return mem.has(k) ? mem.get(k) : null; },
    setItem: function (k, v) { mem.set(k, String(v)); Native.secureSet({ key: k, value: String(v) }).catch(swallow); },
    removeItem: function (k) { mem.delete(k); Native.secureRemove({ key: k }).catch(swallow); },
  };

  var ready = Native.secureKeys()
    .then(function (r) {
      return Promise.all((r.keys || []).map(function (k) {
        return Native.secureGet({ key: k }).then(function (g) { if (g && g.value != null) mem.set(k, g.value); });
      }));
    })
    .catch(swallow)   // 读不到就当空仓库:孩子重新同意一次,而不是白屏
    .then(function () { return undefined; });

  // ---- 音频:原生处理音频焦点、静音开关、后台暂停 ----
  var interruptListeners = new Set();
  Native.addListener('audioInterrupt', function (e) {
    interruptListeners.forEach(function (cb) { try { cb(!!e.paused); } catch (_) {} });
  });
  var audio = {
    play: function (url, opts) { return Native.audioPlay({ url: url, resumeAfterInterrupt: !!(opts && opts.resumeAfterInterrupt) }); },
    pause: function () { Native.audioPause().catch(swallow); },
    stop: function () { Native.audioStop().catch(swallow); },
    onInterrupt: function (cb) { interruptListeners.add(cb); return function () { interruptListeners.delete(cb); }; },
    setDuck: function (on) { Native.audioSetDuck({ enabled: !!on }).catch(swallow); },
  };

  // ---- 设备内存:原生给出真实值(MB),替代 navigator.deviceMemory 的粗粒度/缺失 ----
  var memoryMB = null;
  Native.deviceInfo().then(function (i) { if (i && typeof i.memoryMB === 'number') memoryMB = i.memoryMB; }).catch(swallow);

  // ---- 分享:系统分享面板;家长闸由原生页接管前先不提供(platform.js 保持 Web 版算术题) ----
  var share = {
    shareUrl: function (url, title) { return Share.share({ url: url, title: title }); },
  };

  // ---- 返回键(Android):能后退就后退,否则退到后台,不直接杀进程 ----
  App.addListener('backButton', function (e) {
    if (e && e.canGoBack) window.history.back(); else App.minimizeApp().catch(swallow);
  });
  // ---- 切后台:通知前端暂停音频;回前台不自动续播(由 AudioPlayer.onInterrupt 的语义决定) ----
  App.addListener('appStateChange', function (s) {
    if (s && s.isActive === false) { interruptListeners.forEach(function (cb) { try { cb(true); } catch (_) {} }); }
  });

  window.XUEXI_NATIVE = {
    kind: kind,
    ready: ready,
    storage: secureStorage,           // platform.js: createKv(native.storage ...)
    audio: audio,                     // platform.js: audio: native.audio
    share: share,
    deviceMemoryMB: function () { return memoryMB; },
  };
})();
