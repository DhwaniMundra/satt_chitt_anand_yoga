import java.util.Properties

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

// The backend's address is fixed at build time. Debug builds use the dev backend on the laptop (10.0.2.2 is the laptop
// as the emulator sees it; for a phone on the same Wi-Fi, -PscaServer=http://<laptop IP>:8000). Release builds use
// the live web app, passed in by scripts/build_app.sh --release from a file kept out of git.
val server = providers.gradleProperty("scaServer")
// scripts/build_app.sh --release passes the signing key's properties file (storeFile, storePassword, keyAlias,
// keyPassword), kept out of git with the key.
val signing = providers.gradleProperty("signing").orNull?.let { path -> Properties().apply { file(path).inputStream().use(::load) } }

android {
    namespace = "com.sattchittanand.yoga"
    compileSdk = 36
    defaultConfig {
        applicationId = "com.sattchittanand.yoga"
        minSdk = 26
        targetSdk = 36
        versionCode = 2
        versionName = "1.0"
        // Where the phone downloads Gemma 4 E2B from: the studio's Google Drive copy, unless built with -PmodelUrl=<url>
        // (a laptop serving the file to the emulator, say). The public Hugging Face copy is the fallback (GemmaFile).
        // confirm=t: without it, Drive answers a large file with an HTML page ("can't scan for viruses").
        val studioDrive = "https://drive.usercontent.google.com/download?id=1GeqxZAFGzkdbkTRQMvuyHJkaIG9ByJVV&export=download&confirm=t"
        buildConfigField("String", "MODEL_URL", "\"${providers.gradleProperty("modelUrl").getOrElse(studioDrive)}\"")
    }
    signingConfigs {
        if (signing != null) {
            create("release") {
                storeFile = file(signing.getProperty("storeFile"))
                storePassword = signing.getProperty("storePassword")
                keyAlias = signing.getProperty("keyAlias")
                keyPassword = signing.getProperty("keyPassword")
            }
        }
    }
    buildTypes {
        debug {
            buildConfigField("String", "SERVER", "\"${server.getOrElse("http://10.0.2.2:8000")}\"")
            manifestPlaceholders["cleartext"] = "true" // the dev backend speaks plain HTTP
        }
        release {
            buildConfigField("String", "SERVER", "\"${server.getOrElse("")}\"")
            manifestPlaceholders["cleartext"] = "false"
            isMinifyEnabled = true
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
            signingConfig = signingConfigs.findByName("release")
            // Phones run arm64-v8a. -Pabi=x86_64 builds a release for the emulator, to test the shrunk app there.
            ndk { abiFilters += providers.gradleProperty("abi").getOrElse("arm64-v8a") }
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

tasks.matching { it.name == "preReleaseBuild" }.configureEach {
    doFirst { check(server.isPresent && signing != null) { "build the release with scripts/build_app.sh --release" } }
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
