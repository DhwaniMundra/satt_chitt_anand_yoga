plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.compose.compiler)
}

android {
    namespace = "com.sattchittanand.yoga"
    compileSdk = 36
    defaultConfig {
        applicationId = "com.sattchittanand.yoga"
        minSdk = 26
        targetSdk = 36
        versionCode = 1
        versionName = "0.1"
        // The emulator's address for the laptop running the backend; change it in the app under Me > Server.
        buildConfigField("String", "DEFAULT_SERVER", "\"http://10.0.2.2:8000\"")
    }
    buildTypes {
        release {
            isMinifyEnabled = true
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"))
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
}

dependencies {
    implementation(platform(libs.androidx.compose.bom))
    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.activity.compose)
    implementation(libs.androidx.lifecycle.viewmodel.compose)
    implementation(libs.androidx.compose.ui)
    implementation(libs.androidx.compose.material3)
    implementation(libs.androidx.compose.material.icons.extended)
}
