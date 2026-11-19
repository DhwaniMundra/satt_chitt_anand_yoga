plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.compose.compiler)
}

/**
 * The studio's notes (English and Marathi) and its classes, copied from content/ into the app's assets at build time,
 * so the companion on the phone reads the same files the backend is built from.
 */
abstract class CopyStudioContent : DefaultTask() {
    @get:InputFiles
    @get:PathSensitive(PathSensitivity.NAME_ONLY)
    abstract val files: ConfigurableFileCollection

    @get:OutputDirectory
    abstract val outputDir: DirectoryProperty

    @TaskAction
    fun copy() {
        val out = outputDir.get().asFile.resolve("studio")
        out.deleteRecursively()
        out.mkdirs()
        files.forEach { it.copyTo(out.resolve(it.name), overwrite = true) }
    }
}

val content = rootDir.resolve("../content")
val copyStudioContent = tasks.register<CopyStudioContent>("copyStudioContent") {
    files.from(content.resolve("knowledge/yoga_health.md"), content.resolve("knowledge/yoga_health.mr.md"), content.resolve("studio.json"))
}

android {
    namespace = "com.sattchittanand.yoga"
    compileSdk = 36
    defaultConfig {
        applicationId = "com.sattchittanand.yoga"
        minSdk = 26
        targetSdk = 36
        versionCode = 1
        versionName = "0.6"
        // Where the app looks for the backend until changed in the app. 10.0.2.2 is the laptop as seen from the
        // emulator; for phones on the same Wi-Fi build with -PscaServer=http://<laptop IP>:8000.
        val server = providers.gradleProperty("scaServer").getOrElse("http://10.0.2.2:8000")
        buildConfigField("String", "DEFAULT_SERVER", "\"$server\"")
        // Where the phone downloads Gemma 4 E2B from: the studio's Google Drive copy, unless built with -PmodelUrl=<url>
        // (a laptop serving the file to the emulator, say). The public Hugging Face copy is the fallback (GemmaFile.kt).
        // confirm=t: without it, Drive answers a large file with an HTML page ("can't scan for viruses").
        val studioDrive = "https://drive.usercontent.google.com/download?id=1GeqxZAFGzkdbkTRQMvuyHJkaIG9ByJVV&export=download&confirm=t"
        val modelUrl = providers.gradleProperty("modelUrl").getOrElse(studioDrive)
        buildConfigField("String", "MODEL_URL", "\"$modelUrl\"")
    }
    buildTypes {
        release {
            isMinifyEnabled = true
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    buildFeatures {
        compose = true
        buildConfig = true
    }
    testOptions {
        unitTests.isReturnDefaultValues = true
    }
}

androidComponents {
    onVariants { variant ->
        variant.sources.assets?.addGeneratedSourceDirectory(copyStudioContent, CopyStudioContent::outputDir)
    }
}

dependencies {
    implementation(platform(libs.androidx.compose.bom))
    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.activity.compose)
    implementation(libs.androidx.lifecycle.viewmodel.compose)
    implementation(libs.androidx.compose.ui)
    implementation(libs.androidx.compose.material3)
    implementation(libs.androidx.compose.material.icons.extended)
    implementation(libs.litertlm.android)
    testImplementation(libs.junit)
}
