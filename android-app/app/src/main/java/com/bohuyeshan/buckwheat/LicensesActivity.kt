package com.bohuyeshan.buckwheat

import android.content.Context
import android.content.Intent
import android.os.Bundle
import androidx.appcompat.app.AppCompatActivity
import com.google.android.material.appbar.MaterialToolbar

class LicensesActivity : AppCompatActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_licenses)

        val toolbar: MaterialToolbar = findViewById(R.id.licenses_toolbar)
        toolbar.setNavigationOnClickListener { finish() }
    }

    companion object {
        fun open(context: Context) {
            context.startActivity(Intent(context, LicensesActivity::class.java))
        }
    }
}
