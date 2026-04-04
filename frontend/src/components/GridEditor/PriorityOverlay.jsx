import React, { useMemo } from 'react'
import { Rect } from 'react-konva'

/**
 * PriorityOverlay — amber heat map showing zone priority weights.
 * Helps visualise where coverage is most important.
 */
export default function PriorityOverlay({ cells, gridRows, gridCols, cellW, cellH, opacity }) {
  const rects = useMemo(() => {
    if (!cells?.length) return []
    // Build a lookup for fast row/col access
    const map = {}
    cells.forEach(c => { map[`${c.row}_${c.col}`] = c.priority_weight ?? 0 })

    const out = []
    for (let r = 0; r < gridRows; r++) {
      for (let c = 0; c < gridCols; c++) {
        const pw = map[`${r}_${c}`] ?? 0
        if (pw > 0) {
          out.push({ key: `${r}-${c}`, x: c * cellW, y: r * cellH, pw })
        }
      }
    }
    return out
  }, [cells, gridRows, gridCols, cellW, cellH])

  const maxPw = Math.max(...rects.map(r => r.pw), 1)

  return (
    <>
      {rects.map(({ key, x, y, pw }) => (
        <Rect key={key} x={x} y={y} width={cellW} height={cellH}
          fill="#f59e0b" opacity={opacity * (pw / maxPw) * 0.6} listening={false} />
      ))}
    </>
  )
}
