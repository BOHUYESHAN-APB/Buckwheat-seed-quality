package com.bohuyeshan.buckwheat.util

import android.animation.AnimatorInflater
import android.animation.AnimatorSet
import android.content.Context
import android.view.MotionEvent
import android.view.View
import androidx.interpolator.view.animation.FastOutSlowInInterpolator

fun View.enablePressScale(context: Context) {
    val scaleDown = AnimatorInflater.loadAnimator(context, com.bohuyeshan.buckwheat.R.animator.press_scale) as AnimatorSet
    scaleDown.setTarget(this)
    val scaleUp = AnimatorInflater.loadAnimator(context, com.bohuyeshan.buckwheat.R.animator.press_scale) as AnimatorSet
    scaleUp.setTarget(this)

    // Reverse for scaleUp: just play property back to 1 using interpolator
    this.setOnTouchListener { v, event ->
        when (event.actionMasked) {
            MotionEvent.ACTION_DOWN -> {
                v.animate().scaleX(0.94f).scaleY(0.94f).setDuration(80).setInterpolator(FastOutSlowInInterpolator()).start()
            }
            MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL -> {
                v.animate().scaleX(1f).scaleY(1f).setDuration(120).setInterpolator(FastOutSlowInInterpolator()).start()
            }
        }
        // return false so click events still propagate
        false
    }
}
