package org.xuexi.shicishikong

// 桩:Capacitor 自写插件「XuexiNative」的 Android 实现骨架。未编译、未在真机验证。
// 对应 capabilities.ts:AudioPlayer / Recorder / Storage(安全部分) / 设备内存。
// 放置位置:cap add android 之后拷到 android/app/src/main/java/org/xuexi/shicishikong/,并在 MainActivity 里
//   registerPlugin(XuexiNativePlugin::class.java)(必须在 super.onCreate 之前)。
// 原则:任何一个方法失败都 reject,由 JS 侧吞掉并回落到 Web 实现;不得因为原生异常崩溃。

import android.Manifest
import android.app.ActivityManager
import android.content.Context
import android.media.AudioAttributes
import android.media.AudioFocusRequest
import android.media.AudioManager
import android.media.MediaPlayer
import android.media.MediaRecorder
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import com.getcapacitor.JSArray
import com.getcapacitor.JSObject
import com.getcapacitor.Plugin
import com.getcapacitor.PluginCall
import com.getcapacitor.PluginMethod
import com.getcapacitor.annotation.CapacitorPlugin
import com.getcapacitor.annotation.Permission
import java.io.File
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

@CapacitorPlugin(
    name = "XuexiNative",
    permissions = [Permission(strings = [Manifest.permission.RECORD_AUDIO], alias = "microphone")]
)
class XuexiNativePlugin : Plugin() {

    private val audioManager get() = context.getSystemService(Context.AUDIO_SERVICE) as AudioManager
    private var player: MediaPlayer? = null
    private var focusRequest: AudioFocusRequest? = null
    private var ducked = false
    private var resumeAfterInterrupt = false

    // ---------- 音频:焦点、ducking、被抢占即暂停 ----------
    private val focusListener = AudioManager.OnAudioFocusChangeListener { change ->
        when (change) {
            AudioManager.AUDIOFOCUS_LOSS -> { player?.pause(); notifyInterrupt(true) }              // 被别的 App 长期抢走:不自动恢复
            AudioManager.AUDIOFOCUS_LOSS_TRANSIENT -> { player?.pause(); notifyInterrupt(true) }    // 来电等:可恢复
            AudioManager.AUDIOFOCUS_LOSS_TRANSIENT_CAN_DUCK -> player?.setVolume(0.25f, 0.25f)
            AudioManager.AUDIOFOCUS_GAIN -> {
                player?.setVolume(if (ducked) 0.25f else 1f, if (ducked) 0.25f else 1f)
                if (resumeAfterInterrupt && player?.isPlaying == false) { player?.start(); notifyInterrupt(false) }
            }
        }
    }

    private fun notifyInterrupt(paused: Boolean) {
        notifyListeners("audioInterrupt", JSObject().put("paused", paused))
    }

    @PluginMethod
    fun audioPlay(call: PluginCall) {
        val url = call.getString("url") ?: return call.reject("url required")
        resumeAfterInterrupt = call.getBoolean("resumeAfterInterrupt", false) ?: false
        val attrs = AudioAttributes.Builder()
            .setUsage(AudioAttributes.USAGE_MEDIA)                       // 媒体音量,不走铃声通道
            .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
            .build()
        focusRequest = AudioFocusRequest.Builder(AudioManager.AUDIOFOCUS_GAIN)
            .setAudioAttributes(attrs).setOnAudioFocusChangeListener(focusListener).build()
        if (audioManager.requestAudioFocus(focusRequest!!) != AudioManager.AUDIOFOCUS_REQUEST_GRANTED) {
            return call.reject("audio focus denied")                    // JS 侧据此显示字幕文本,不是报错页
        }
        try {
            player?.release()
            player = MediaPlayer().apply {
                setAudioAttributes(attrs); setDataSource(url)            // TODO: file:// 与 https://localhost 之外的 URL 一律拒绝
                setVolume(if (ducked) 0.25f else 1f, if (ducked) 0.25f else 1f)
                setOnCompletionListener { abandonFocus() }
                prepare(); start()
            }
            call.resolve()
        } catch (e: Exception) { abandonFocus(); call.reject("audio play failed", e) }
    }

    @PluginMethod fun audioPause(call: PluginCall) { player?.pause(); call.resolve() }
    @PluginMethod fun audioStop(call: PluginCall) { player?.stop(); player?.release(); player = null; abandonFocus(); call.resolve() }
    @PluginMethod
    fun audioSetDuck(call: PluginCall) {
        ducked = call.getBoolean("enabled", false) ?: false
        player?.setVolume(if (ducked) 0.25f else 1f, if (ducked) 0.25f else 1f); call.resolve()
    }
    private fun abandonFocus() { focusRequest?.let { audioManager.abandonAudioFocusRequest(it) }; focusRequest = null }

    override fun handleOnPause() { player?.pause(); notifyInterrupt(true) }   // 后台暂停,不做后台播放(v1)

    // ---------- 设备信息:真实内存(MB) ----------
    @PluginMethod
    fun deviceInfo(call: PluginCall) {
        val mi = ActivityManager.MemoryInfo()
        (context.getSystemService(Context.ACTIVITY_SERVICE) as ActivityManager).getMemoryInfo(mi)
        call.resolve(JSObject().put("memoryMB", mi.totalMem / (1024 * 1024)))
    }

    // ---------- 安全存储:Keystore AES-GCM + 私有 SharedPreferences(allowBackup=false) ----------
    private val prefs get() = context.getSharedPreferences("xuexi_secure", Context.MODE_PRIVATE)
    private fun key(): SecretKey {
        val ks = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        (ks.getKey("xuexi_master", null) as? SecretKey)?.let { return it }
        return KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore").apply {
            init(KeyGenParameterSpec.Builder("xuexi_master", KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM).setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE).build())
        }.generateKey()
    }
    @PluginMethod
    fun secureSet(call: PluginCall) {
        val k = call.getString("key") ?: return call.reject("key required")
        val v = call.getString("value") ?: ""
        try {
            val c = Cipher.getInstance("AES/GCM/NoPadding").apply { init(Cipher.ENCRYPT_MODE, key()) }
            val blob = c.iv + c.doFinal(v.toByteArray())
            prefs.edit().putString(k, Base64.encodeToString(blob, Base64.NO_WRAP)).apply(); call.resolve()
        } catch (e: Exception) { call.reject("secure set failed", e) }
    }
    @PluginMethod
    fun secureGet(call: PluginCall) {
        val k = call.getString("key") ?: return call.reject("key required")
        val raw = prefs.getString(k, null) ?: return call.resolve(JSObject())
        try {
            val b = Base64.decode(raw, Base64.NO_WRAP)
            val c = Cipher.getInstance("AES/GCM/NoPadding").apply { init(Cipher.DECRYPT_MODE, key(), GCMParameterSpec(128, b.copyOfRange(0, 12))) }
            call.resolve(JSObject().put("value", String(c.doFinal(b.copyOfRange(12, b.size)))))
        } catch (e: Exception) { prefs.edit().remove(k).apply(); call.resolve(JSObject()) }   // 密钥失效 = 当作没有
    }
    @PluginMethod fun secureRemove(call: PluginCall) { call.getString("key")?.let { prefs.edit().remove(it).apply() }; call.resolve() }
    @PluginMethod fun secureKeys(call: PluginCall) { call.resolve(JSObject().put("keys", JSArray(prefs.all.keys.toList()))) }

    // ---------- 录音:只落 App 私有目录,不上传;v1 未接通(Web 版也刻意不接) ----------
    private var recorder: MediaRecorder? = null
    private var recordingFile: File? = null
    private fun recDir() = File(context.noBackupFilesDir, "recordings").apply { mkdirs() }

    @PluginMethod
    fun recorderStart(call: PluginCall) {
        // localOnly 必须为 true,否则拒绝:产品规则「录音默认只落本地」。
        if (call.getBoolean("localOnly", false) != true) return call.reject("localOnly must be true")
        if (getPermissionState("microphone") != com.getcapacitor.PermissionState.GRANTED) {
            return requestPermissionForAlias("microphone", call, "onMicPermission")   // 系统弹窗文案取自 Manifest 之外的应用内说明页(见 docs)
        }
        startRecording(call)
    }
    @com.getcapacitor.annotation.PermissionCallback
    fun onMicPermission(call: PluginCall) {
        if (getPermissionState("microphone") == com.getcapacitor.PermissionState.GRANTED) startRecording(call)
        else call.reject("microphone denied")                                            // 拒绝 = 文字复述,不是错误页
    }
    private fun startRecording(call: PluginCall) {
        try {
            val f = File(recDir(), "rec-${System.currentTimeMillis()}.m4a")
            recorder = MediaRecorder(context).apply {
                setAudioSource(MediaRecorder.AudioSource.MIC); setOutputFormat(MediaRecorder.OutputFormat.MPEG_4)
                setAudioEncoder(MediaRecorder.AudioEncoder.AAC); setOutputFile(f.absolutePath); prepare(); start()
            }
            recordingFile = f; call.resolve()
        } catch (e: Exception) { call.reject("record start failed", e) }
    }
    @PluginMethod
    fun recorderStop(call: PluginCall) {
        try {
            recorder?.stop(); recorder?.release(); recorder = null
            val f = recordingFile ?: return call.reject("not recording")
            call.resolve(JSObject().put("assetId", f.name).put("bytes", f.length()))
        } catch (e: Exception) { call.reject("record stop failed", e) }
    }
    @PluginMethod
    fun recorderDelete(call: PluginCall) {
        val id = call.getString("assetId") ?: return call.reject("assetId required")
        File(recDir(), File(id).name).delete(); call.resolve()                          // File(id).name 防路径穿越
    }
    // TODO recorderPlayback:复用 audioPlay 的播放器,数据源为 recDir()/assetId。
}
