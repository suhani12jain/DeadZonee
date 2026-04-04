import React from 'react'
import { Group, Circle, Arc, Text, Line } from 'react-konva'

/**
 * RouterPin — Konva group rendering a WiFi AP icon on the grid.
 * AI-suggested routers pulse green.
 * Double-click or click opens edit modal.
 */
export default function RouterPin({ router, cellW, cellH, onClick }) {
  const cx = router.col * cellW + cellW / 2
  const cy = router.row * cellH + cellH / 2
  const ai = router.is_suggested

  const strokeColor = ai ? '#06d6a0' : '#63b3ed'
  const fillColor   = ai ? 'rgba(6,214,160,0.12)' : 'rgba(99,179,237,0.10)'

  return (
    <Group x={cx} y={cy} onClick={() => onClick?.(router)} onTap={() => onClick?.(router)}
      style={{ cursor: 'pointer' }}>

      {/* Outer ring */}
      <Circle radius={Math.min(cellW, cellH) * 0.38} fill={fillColor} stroke={strokeColor} strokeWidth={1.2} />

      {/* Signal arcs */}
      {[0.22, 0.30].map((factor, i) => {
        const r = Math.min(cellW, cellH) * factor
        return (
          <Arc key={i}
            innerRadius={r - 1} outerRadius={r}
            angle={120} rotation={-60 - 180}
            fill={strokeColor} opacity={0.55 - i * 0.15}
          />
        )
      })}

      {/* Centre dot */}
      <Circle radius={3} fill={strokeColor} />

      {/* Label */}
      <Text
        text={router.name}
        fontSize={Math.max(7, Math.min(9, cellW * 0.25))}
        fontFamily="IBM Plex Mono"
        fill={strokeColor}
        y={Math.min(cellW, cellH) * 0.4 + 2}
        offsetX={router.name.length * 2.5}
        stroke="rgba(11,14,20,0.8)" strokeWidth={2} fillAfterStrokeEnabled
      />
    </Group>
  )
}
