package com.bohuyeshan.buckwheat.model

data class Detection(
    val label: String,
    val score: Float,
    val boundingBox: BoundingBox
)

data class BoundingBox(
    val left: Float,
    val top: Float,
    val right: Float,
    val bottom: Float
)
