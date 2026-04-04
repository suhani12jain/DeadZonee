import React, { useMemo } from 'react'
import { Rect } from 'react-konva'
import { signalColor } from '../../constants/zoneConfig'

/**
 * HeatmapOverlay — Konva Rect per cell coloured by signal dBm.
 * Colours from spec: >-50 green, -50to-67 yellow, -67to-75 orange, -75to-85 red, <-85 black.
 */
export default function HeatmapOverlay({ signalMatrix, cellW, cellH, opacity }) {
  const rects = useMemo(() => {
    if (!signalMatrix?.length) return []
    const out = []
    for (let r = 0; r < signalMatrix.length; r++) {
      for (let c = 0; c < signalMatrix[r].length; c++) {
        out.push({ key: `${r}-${c}`, x: c * cellW, y: r * cellH, fill: signalColor(signalMatrix[r][c]) })
      }
    }
    return out
  }, [signalMatrix, cellW, cellH])

  return (
    <>
      {rects.map(({ key, x, y, fill }) => (
        <Rect key={key} x={x} y={y} width={cellW} height={cellH} fill={fill} opacity={opacity} listening={false} />
      ))}
    </>
  )
}
