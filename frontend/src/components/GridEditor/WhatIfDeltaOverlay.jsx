import React, { useMemo } from 'react'
import { Rect } from 'react-konva'

/**
 * WhatIfDeltaOverlay — shows simulation delta (after − before) or dead-zone flips.
 * Green: stronger signal or recovered from dead. Red: weaker or newly dead.
 */
export default function WhatIfDeltaOverlay({
  viewMode,
  deltaMatrix,
  newDeadMask,
  recoveredMask,
  cellW,
  cellH,
  opacity = 0.55,
}) {
  const rects = useMemo(() => {
    if (!deltaMatrix?.length) return []
    const rows = deltaMatrix.length
    const cols = deltaMatrix[0]?.length ?? 0
    const out = []
    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        let fill = null
        if (viewMode === 'delta') {
          const d = Number(deltaMatrix[r][c])
          if (!Number.isFinite(d) || Math.abs(d) < 0.15) continue
          const a = Math.min(0.9, 0.2 + Math.min(Math.abs(d) / 30, 0.55))
          fill = d > 0 ? `rgba(34,197,94,${a})` : `rgba(239,68,68,${a})`
        } else if (viewMode === 'new_dead' && newDeadMask?.[r]?.[c]) {
          fill = `rgba(220,38,38,${opacity})`
        } else if (viewMode === 'recovered' && recoveredMask?.[r]?.[c]) {
          fill = `rgba(22,163,74,${opacity})`
        }
        if (fill) out.push({ key: `wi-${r}-${c}`, x: c * cellW, y: r * cellH, fill })
      }
    }
    return out
  }, [viewMode, deltaMatrix, newDeadMask, recoveredMask, cellW, cellH, opacity])

  return (
    <>
      {rects.map(({ key, x, y, fill }) => (
        <Rect key={key} x={x} y={y} width={cellW} height={cellH} fill={fill} listening={false} />
      ))}
    </>
  )
}
