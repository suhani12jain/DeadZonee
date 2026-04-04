import React, { useMemo } from 'react'
import { Rect, Line } from 'react-konva'

/**
 * DeadzoneOverlay — black Rect + cross-hatch pattern on dead cells.
 */
export default function DeadzoneOverlay({ deadZoneMask, cellW, cellH, opacity }) {
  const items = useMemo(() => {
    if (!deadZoneMask?.length) return []
    const out = []
    for (let r = 0; r < deadZoneMask.length; r++) {
      for (let c = 0; c < deadZoneMask[r].length; c++) {
        if (deadZoneMask[r][c]) {
          const x = c * cellW, y = r * cellH
          out.push({ key: `${r}-${c}`, x, y })
        }
      }
    }
    return out
  }, [deadZoneMask, cellW, cellH])

  return (
    <>
      {items.map(({ key, x, y }) => (
        <React.Fragment key={key}>
          <Rect x={x} y={y} width={cellW} height={cellH} fill="#000000" opacity={opacity * 0.75} listening={false} />
          {/* cross-hatch lines */}
          <Line points={[x, y, x + cellW, y + cellH]} stroke="#ff4d6d" strokeWidth={0.6} opacity={opacity * 0.5} listening={false} />
          <Line points={[x + cellW, y, x, y + cellH]} stroke="#ff4d6d" strokeWidth={0.6} opacity={opacity * 0.5} listening={false} />
        </React.Fragment>
      ))}
    </>
  )
}
