package com.sattchittanand.yoga.companion

import android.app.ActivityManager
import android.app.DownloadManager
import android.content.Context
import android.net.Uri
import android.os.Build
import android.os.StatFs
import android.util.Log
import com.google.ai.edge.litertlm.Backend
import com.google.ai.edge.litertlm.Content
import com.google.ai.edge.litertlm.Contents
import com.google.ai.edge.litertlm.ConversationConfig
import com.google.ai.edge.litertlm.Engine
import com.google.ai.edge.litertlm.EngineConfig
import com.google.ai.edge.litertlm.Message
import com.google.ai.edge.litertlm.NoRepeatNgramConfig
import com.google.ai.edge.litertlm.SamplerConfig
import com.google.ai.edge.litertlm.SuppressTokensConfig
import com.google.ai.edge.litertlm.ToolSet
import com.google.ai.edge.litertlm.tool
import com.sattchittanand.yoga.BuildConfig
import com.sattchittanand.yoga.R
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.asCoroutineDispatcher
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File
import java.security.MessageDigest
import java.util.concurrent.Executors

/** The model file: Gemma 4 E2B for LiteRT-LM. */
object GemmaFile {
    const val NAME = "gemma-4-E2B-it.litertlm"
    const val SIZE = 2_588_147_712L
    const val SHA256 = "181938105e0eefd105961417e8da75903eacda102c4fce9ce90f50b97139a63c"
    /** The public copy, used when the studio's copy (BuildConfig.MODEL_URL) fails or sends something else. */
    const val HUGGING_FACE = "https://huggingface.co/litert-community/gemma-4-E2B-it-litert-lm/resolve/main/gemma-4-E2B-it.litertlm"
    /** Room for the weight cache the CPU runtime writes on its first start (about 0.8 GB for E2B), beyond the file. */
    const val CACHE_ROOM = 1_000_000_000L
    /** A phone sold with 6 GB reports about 5.5 GB of total memory; below 5 GiB, Gemma does not fit beside Android. */
    const val MIN_MEMORY = 5L * 1024 * 1024 * 1024

    val urls: List<String> get() = listOf(BuildConfig.MODEL_URL, HUGGING_FACE).filter { it.isNotBlank() }.distinct()
}

/** Where Gemma on this phone stands, for the Ask screen. */
sealed interface GemmaState {
    data class TooLittleMemory(val totalBytes: Long) : GemmaState
    data object NotDownloaded : GemmaState
    data class Downloading(val done: Long, val total: Long, val waiting: Waiting?) : GemmaState
    data class Checking(val done: Long, val total: Long) : GemmaState
    data object Loading : GemmaState
    data object Ready : GemmaState
    data class Failed(val problem: Problem) : GemmaState
}

enum class Waiting { WIFI, NETWORK }
enum class Problem { NO_SPACE, WRONG_FILE, DOWNLOAD, START }

/**
 * Gemma 4 E2B on this phone: the one-time download (Android's DownloadManager, which resumes after a dropped
 * connection and goes on when the app is closed), the check of the file, and the LiteRT-LM engine. One per process.
 * LiteRT-LM is not thread-safe, so every engine call runs on one thread; the companion's tools run on it too.
 */
class GemmaOnPhone private constructor(private val context: Context) {
    companion object {
        private const val TAG = "SCA-Gemma"
        // No 8-token sequence may repeat within 16 tokens: that stops a word loop, and a list may still say "8:00" on each line.
        private const val CHAT_NGRAM_WINDOW = 16

        @Volatile private var instance: GemmaOnPhone? = null
        fun get(context: Context): GemmaOnPhone =
            instance ?: synchronized(this) { instance ?: GemmaOnPhone(context.applicationContext).also { instance = it } }
    }

    private val prefs = context.getSharedPreferences("gemma", Context.MODE_PRIVATE)
    private val downloads = context.getSystemService(DownloadManager::class.java)
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private val thread = Executors.newSingleThreadExecutor { Thread(it, "gemma") }.asCoroutineDispatcher()
    private val dir: File get() = context.getExternalFilesDir("models")!!.apply { mkdirs() }
    private val file: File get() = File(dir, GemmaFile.NAME)
    private var engine: Engine? = null
    private var watching: Job? = null
    private var foreign: List<Int>? = null

    private val totalMemory: Long = ActivityManager.MemoryInfo().also { context.getSystemService(ActivityManager::class.java).getMemoryInfo(it) }.totalMem
    private val _state = MutableStateFlow<GemmaState>(
        if (totalMemory < GemmaFile.MIN_MEMORY) GemmaState.TooLittleMemory(totalMemory) else GemmaState.NotDownloaded,
    )
    val state: StateFlow<GemmaState> = _state

    /** Picks up where things stand: a download under way or finished while the app was closed, or a checked file to
     *  load (when Ask opens; [loadModel] false when the app merely comes back, so 2.6 GB is not loaded unasked). */
    fun refresh(loadModel: Boolean = true) {
        val now = _state.value
        if (now is GemmaState.TooLittleMemory || now is GemmaState.Loading || now is GemmaState.Ready || now is GemmaState.Checking) return
        when {
            verified() -> if (loadModel) load()
            prefs.contains("download") -> watch()
            now !is GemmaState.Failed -> _state.value = GemmaState.NotDownloaded
        }
    }

    private fun verified(): Boolean = file.isFile && prefs.getString("verified", null) == "${file.length()}:${file.lastModified()}"

    // ---------- the download ----------

    /** Starts the download from the first address (or [from]); on Wi-Fi only unless [mobileData]. */
    fun download(mobileData: Boolean = false, from: Int = 0) {
        prefs.getLong("download", -1L).takeIf { it >= 0 }?.let { downloads.remove(it) }
        prefs.edit().remove("download").apply()
        file.delete()
        val urls = GemmaFile.urls
        if (from >= urls.size) {
            _state.value = GemmaState.Failed(Problem.DOWNLOAD)
            return
        }
        if (StatFs(dir.path).availableBytes < GemmaFile.SIZE + GemmaFile.CACHE_ROOM) {
            _state.value = GemmaState.Failed(Problem.NO_SPACE)
            return
        }
        val request = DownloadManager.Request(Uri.parse(urls[from]))
            .setTitle(context.getString(R.string.gemma_download_title))
            .setDescription(context.getString(R.string.gemma_download_note))
            .setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE)
            .setDestinationInExternalFilesDir(context, "models", GemmaFile.NAME)
            .setAllowedOverMetered(mobileData)
            .setAllowedOverRoaming(false)
        val id = downloads.enqueue(request)
        prefs.edit().putLong("download", id).putInt("from", from).putBoolean("mobile", mobileData).remove("verified").apply()
        _state.value = GemmaState.Downloading(0, GemmaFile.SIZE, null)
        watch()
    }

    /** Stops the download and deletes what came so far. */
    fun cancel() {
        prefs.getLong("download", -1L).takeIf { it >= 0 }?.let { downloads.remove(it) }
        prefs.edit().remove("download").apply()
        watching?.cancel()
        file.delete()
        _state.value = GemmaState.NotDownloaded
    }

    /** Goes on with the download over mobile data (DownloadManager cannot change a request: it starts again). */
    fun useMobileData() = download(mobileData = true, from = prefs.getInt("from", 0))

    /** Follows the download under way, and the next one after a failed or wrong file, until there is none. */
    private fun watch() {
        if (watching?.isActive == true) return
        watching = scope.launch {
            while (true) {
                val id = prefs.getLong("download", -1L)
                if (id < 0) return@launch // done, cancelled, or no address left
                val row = downloads.query(DownloadManager.Query().setFilterById(id))
                val status = row.use { c ->
                    if (!c.moveToFirst()) null else Triple(
                        c.getInt(c.getColumnIndexOrThrow(DownloadManager.COLUMN_STATUS)),
                        c.getInt(c.getColumnIndexOrThrow(DownloadManager.COLUMN_REASON)),
                        c.getLong(c.getColumnIndexOrThrow(DownloadManager.COLUMN_BYTES_DOWNLOADED_SO_FAR)) to
                            c.getLong(c.getColumnIndexOrThrow(DownloadManager.COLUMN_TOTAL_SIZE_BYTES)),
                    )
                }
                if (status == null) { // removed from outside the app (the Downloads app, say)
                    prefs.edit().remove("download").apply()
                    _state.value = GemmaState.NotDownloaded
                    return@launch
                }
                val (code, reason, bytes) = status
                val total = bytes.second.takeIf { it > 0 } ?: GemmaFile.SIZE
                when (code) {
                    DownloadManager.STATUS_SUCCESSFUL -> {
                        prefs.edit().remove("download").apply()
                        verify(next = prefs.getInt("from", 0) + 1) // a wrong file starts the next address, watched below
                        continue
                    }
                    DownloadManager.STATUS_FAILED -> {
                        Log.w(TAG, "download $id failed: reason $reason")
                        download(prefs.getBoolean("mobile", false), prefs.getInt("from", 0) + 1) // the next address, if any
                        continue
                    }
                    DownloadManager.STATUS_PAUSED -> _state.value = GemmaState.Downloading(bytes.first, total,
                        if (reason == DownloadManager.PAUSED_QUEUED_FOR_WIFI) Waiting.WIFI else Waiting.NETWORK)
                    else -> _state.value = GemmaState.Downloading(bytes.first, total, null)
                }
                delay(1000)
            }
        }
    }

    /** The file is Gemma only if it has the right size and SHA-256 (a Drive link without confirm=t sends a web page). */
    private fun verify(next: Int) {
        val size = file.length()
        if (size != GemmaFile.SIZE) {
            Log.w(TAG, "downloaded $size bytes, not ${GemmaFile.SIZE}")
            fail(next)
            return
        }
        _state.value = GemmaState.Checking(0, size)
        val digest = MessageDigest.getInstance("SHA-256")
        val buffer = ByteArray(1 shl 20)
        var done = 0L
        file.inputStream().use { input ->
            while (true) {
                val n = input.read(buffer)
                if (n < 0) break
                digest.update(buffer, 0, n)
                done += n
                if (done % (64L shl 20) < n) _state.value = GemmaState.Checking(done, size)
            }
        }
        val hex = digest.digest().joinToString("") { "%02x".format(it) }
        if (hex != GemmaFile.SHA256) {
            Log.w(TAG, "SHA-256 $hex is not Gemma's")
            fail(next)
            return
        }
        prefs.edit().putString("verified", "${file.length()}:${file.lastModified()}").apply()
        load()
    }

    /** A wrong file: tries the next address, or says so when there is none. */
    private fun fail(next: Int) {
        file.delete()
        if (next < GemmaFile.urls.size) download(prefs.getBoolean("mobile", false), next) else _state.value = GemmaState.Failed(Problem.WRONG_FILE)
    }

    // ---------- the engine ----------

    private fun onEmulator() = Build.HARDWARE == "ranchu" || Build.FINGERPRINT.contains("generic") || Build.PRODUCT.contains("sdk")

    /** GPU first on a phone, then CPU. A GPU start that crashed the app last time is not tried again. */
    private fun backends(): List<String> = when {
        onEmulator() -> listOf("CPU") // the emulator's GPU does not run LiteRT-LM
        prefs.getBoolean("gpu_crashed", false) || prefs.getBoolean("gpu_trying", false) -> listOf("CPU")
        else -> listOf("GPU", "CPU")
    }

    private fun load() {
        if (_state.value is GemmaState.Loading || engine != null) return
        if (prefs.getBoolean("gpu_trying", false)) prefs.edit().putBoolean("gpu_crashed", true).apply()
        _state.value = GemmaState.Loading
        scope.launch(thread) {
            for (backend in backends()) {
                try {
                    if (backend == "GPU") prefs.edit().putBoolean("gpu_trying", true).commit()
                    engine = start(backend)
                    _state.value = GemmaState.Ready
                    return@launch
                } catch (t: Throwable) {
                    Log.w(TAG, "start on $backend failed", t)
                } finally {
                    prefs.edit().remove("gpu_trying").apply()
                }
            }
            _state.value = GemmaState.Failed(Problem.START)
        }
    }

    private fun start(backend: String): Engine {
        val e = Engine(
            EngineConfig(
                modelPath = file.path,
                backend = if (backend == "GPU") Backend.GPU() else Backend.CPU(),
                visionBackend = null, // text only: no image or audio encoders in memory
                audioBackend = null,
                maxNumTokens = 8192, // room for the tools, the notes handed over and six earlier messages
                cacheDir = context.cacheDir.path,
            ),
        )
        e.initialize()
        if (backend == "GPU") { // a GPU can start and still fail at first use
            try {
                e.createConversation(ConversationConfig(maxOutputToken = 4)).use { it.sendMessage("Say OK.") }
            } catch (t: Throwable) {
                e.close()
                throw t
            }
        }
        return e
    }

    /** Tokens with a letter or digit that is neither Latin nor Devanagari, banned from Marathi answers (listed from the
     *  model by scripts/foreign_tokens.py, since the Android API cannot turn a token back into text). */
    private fun foreignTokens(): List<Int> = foreign ?: context.assets.open("gemma4_foreign_tokens.bin").use { it.readBytes() }.let { bits ->
        (0 until bits.size * 8).filter { (bits[it / 8].toInt() shr (it % 8)) and 1 == 1 }
    }.also { foreign = it }

    /**
     * One reply in a conversation that starts with [preface] (earlier messages: from the student?, text) and may call
     * [tools], which the runtime runs for Gemma until it has its answer. Greedy decoding.
     */
    suspend fun reply(system: String, preface: List<Pair<Boolean, String>>, message: String, tools: List<ToolSet>, banForeign: Boolean): String =
        withContext(thread) {
            val e = engine ?: error("Gemma is not loaded")
            val config = ConversationConfig(
                systemInstruction = Contents.of(system),
                initialMessages = preface.map { (student, text) -> if (student) Message.user(text) else Message.model(text) },
                tools = tools.map { tool(it) },
                samplerConfig = SamplerConfig(topK = 1, topP = 1.0, temperature = 1.0),
                automaticToolCalling = true,
                maxOutputToken = 400,
            )
            e.createConversation(config).use { conversation ->
                val answer = conversation.sendMessage(
                    message,
                    noRepeatNgramConfig = NoRepeatNgramConfig(8, CHAT_NGRAM_WINDOW),
                    suppressTokensConfig = if (banForeign) SuppressTokensConfig(foreignTokens()) else null,
                )
                answer.contents.contents.filterIsInstance<Content.Text>().joinToString("") { it.text }.trim()
            }
        }
}
