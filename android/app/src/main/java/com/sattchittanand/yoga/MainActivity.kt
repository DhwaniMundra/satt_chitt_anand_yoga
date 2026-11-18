package com.sattchittanand.yoga

import android.content.Context
import android.content.res.Configuration
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.viewModels
import com.sattchittanand.yoga.ui.App
import com.sattchittanand.yoga.ui.YogaTheme
import java.util.Locale

class MainActivity : ComponentActivity() {
    private val vm: AppViewModel by viewModels()

    /** Loads the app in the language chosen inside it (English, Hindi or Marathi), whatever the phone's language. */
    override fun attachBaseContext(newBase: Context) {
        val locale = Locale.forLanguageTag(Prefs.lang(newBase))
        Locale.setDefault(locale)
        val config = Configuration(newBase.resources.configuration).apply { setLocale(locale) }
        super.attachBaseContext(newBase.createConfigurationContext(config))
    }

    override fun onResume() {
        super.onResume()
        vm.onResume()
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            YogaTheme {
                App(vm) { lang ->
                    vm.setLanguage(lang)
                    if (vm.user != null) vm.refresh() // class names come from the server in the chosen language
                    recreate()
                }
            }
        }
    }
}
