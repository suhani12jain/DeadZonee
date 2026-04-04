import React, { useMemo } from 'react'
import { Rect } from 'react-konva'

/**
 * InterferenceOverlay — purple Rect for cells with interference_score > 0.5.
 */
export default function InterferenceOverlay({ interferenceMatrix, cellW, cellH, opacity }) {
  const rects = useMemo(() => {
    if (!interferenceMatrix?.length) return []
    const out = []
    for (let r = 0; r < interferenceMatrix.length; r++) {
      for (let c = 0; c < interferenceMatrix[r].length; c++) {
        const score = interferenceMatrix[r][c]
        if (score > 0.5) {
          out.push({ key: `${r}-${c}`, x: c * cellW, y: r * cellH, alpha: Math.min(score * 0.6, 0.85) })
        }
      }
    }
    return out
  }, [interferenceMatrix, cellW, cellH])

  return (
    <>
      {rects.map(({ key, x, y, alpha }) => (
        <Rect key={key} x={x} y={y} width={cellW} height={cellH}
          fill="#a855f7" opacity={opacity * alpha} listening={false} />
      ))}
    </>
  )
}
