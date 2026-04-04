import React, { useRef, useState, useCallback, useEffect } from 'react'
import { Stage, Layer, Rect, Line, Group, Circle, Text } from 'react-konva'
import useStore from '../../store/useStore'
import { useGrid } from '../../hooks/useGrid'
import { getZone } from '../../constants/zoneConfig'
import { applyPaint, pixelToCell } from './ZonePainter'
import HeatmapOverlay from './HeatmapOverlay'
import DeadzoneOverlay from './DeadzoneOverlay'
import InterferenceOverlay from './InterferenceOverlay'
import PriorityOverlay from './PriorityOverlay'
import RouterPin from './RouterPin'

const CANVAS_PAD = 0   // px padding inside container

/**
 * GridCanvas — the core Konva stage.
 * Renders zone-painted grid + all overlays + router pins + AI suggestion pin.
 *
 * KEY FORMULA (must match backend grid_builder.py):
 *   const cell_w = canvasWidth / grid_cols
 *   const cell_h = canvasHeight / grid_rows
 *   const clickRow = Math.floor(mouseY / cell_h)
 *   const clickCol = Math.floor(mouseX / cell_w)
 */
export default function GridCanvas({ containerWidth = 800, containerHeight = 600 }) {
  const {
    gridMeta, cells, routers, suggestion,
    activeZone, activeTool, isPainting, setIsPainting,
    overlays, overlayOpacity,
    signalMatrix, deadZoneMask, interferenceMatrix,
    updateCell, setHoveredCell, hoveredCell,
    openRouterModal, pushToast,
  } = useStore()

  const { persistZones } = useGrid()
  const stageRef = useRef()
  const [pendingCells, setPendingCells] = useState([])   // cells changed in current stroke
  const [scale, setScale] = useState(1)
  const [stagePos, setStagePos] = useState({ x: 0, y: 0 })

  if (!gridMeta) return null

  const { grid_rows, grid_cols } = gridMeta
  const cellW = (containerWidth  - CANVAS_PAD * 2) / grid_cols
  const cellH = (containerHeight - CANVAS_PAD * 2) / grid_rows
  const stageW = containerWidth
  const stageH = containerHeight

  // Build zone color lookup from cells for fast rendering
  const cellMap = {}
  cells.forEach(c => { cellMap[`${c.row}_${c.col}`] = c })

  // ── Paint helpers ──────────────────────────────────────────────────────────
  const paintCell = useCallback((row, col) => {
    const cell = cellMap[`${row}_${col}`]
    if (!cell) return

    // Can't place router in no-zone during paint — just zone it
    const updated = applyPaint(cell, activeZone, activeTool)
    updateCell(row, col, updated)
    setPendingCells(prev => {
      const key = `${row}_${col}`
      const exists = prev.find(c => `${c.row}_${c.col}` === key)
      if (exists) return prev.map(c => `${c.row}_${c.col}` === key ? updated : c)
      return [...prev, updated]
    })
  }, [cellMap, activeZone, activeTool, updateCell])

  const getPointerCell = useCallback((e) => {
    const stage = stageRef.current
    if (!stage) return null
    const pos = stage.getPointerPosition()
    if (!pos) return null
    // Account for stage transform
    const x = (pos.x - stagePos.x) / scale
    const y = (pos.y - stagePos.y) / scale
    return pixelToCell(x, y, cellW, cellH, grid_rows, grid_cols)
  }, [stagePos, scale, cellW, cellH, grid_rows, grid_cols])

  // ── Event handlers ─────────────────────────────────────────────────────────
  const handleMouseDown = (e) => {
    // Middle mouse / alt = pan
    if (e.evt.button === 1 || e.evt.altKey) return
    const cell = getPointerCell(e)
    if (!cell) return

    if (activeTool === 'select') {
      // double-click handled separately
      return
    }
    setIsPainting(true)
    paintCell(cell.row, cell.col)
  }

  const handleMouseMove = (e) => {
    const cell = getPointerCell(e)
    setHoveredCell(cell)
    if (isPainting && (activeTool === 'paint' || activeTool === 'erase')) {
      if (cell) paintCell(cell.row, cell.col)
    }
  }

  const handleMouseUp = async () => {
    if (!isPainting) return
    setIsPainting(false)
    if (pendingCells.length > 0) {
      // Persist changed cells to backend
      const allCells = cells.map(c => {
        const pKey = `${c.row}_${c.col}`
        const pending = pendingCells.find(p => `${p.row}_${p.col}` === pKey)
        return pending ?? c
      })
      await persistZones(allCells)
      setPendingCells([])
    }
  }

  const handleDblClick = (e) => {
    const cell = getPointerCell(e)
    if (!cell) return
    const c = cellMap[`${cell.row}_${cell.col}`]
    if (!c) return
    if (!c.allow_router) {
      pushToast(`${getZone(c.zone_type).label} — routers not allowed here`, 'warning')
      return
    }
    openRouterModal({ row: cell.row, col: cell.col })
  }

  // Wheel zoom
  const handleWheel = (e) => {
    e.evt.preventDefault()
    const stage = stageRef.current
    if (!stage) return

    if (!e.evt.ctrlKey && !e.evt.metaKey) {
      setStagePos(prev => ({
        x: prev.x - e.evt.deltaX * 0.6,
        y: prev.y - e.evt.deltaY * 0.6,
      }))
      return
    }

    const scaleBy = 1.08
    const oldScale = scale
    const pointer = stage.getPointerPosition()
    if (!pointer) return
    const mousePointTo = {
      x: (pointer.x - stagePos.x) / oldScale,
      y: (pointer.y - stagePos.y) / oldScale,
    }
    const newScale = e.evt.deltaY < 0 ? oldScale * scaleBy : oldScale / scaleBy
    const clamped = Math.max(0.3, Math.min(newScale, 10))
    setScale(clamped)
    setStagePos({
      x: pointer.x - mousePointTo.x * clamped,
      y: pointer.y - mousePointTo.y * clamped,
    })
  }

  // ── Render zone cells ──────────────────────────────────────────────────────
  const zoneCells = cells.map(c => {
    const z = getZone(c.zone_type)
    return (
      <Rect key={`z-${c.row}-${c.col}`}
        x={c.col * cellW} y={c.row * cellH}
        width={cellW} height={cellH}
        fill={z.color}
        opacity={c.zone_type === 'no_zone' ? 0.12 : 0.25}
        listening={false}
      />
    )
  })

  // ── Render grid lines ──────────────────────────────────────────────────────
  const gridLines = []
  for (let c = 0; c <= grid_cols; c++) {
    gridLines.push(
      <Line key={`v${c}`}
        points={[c * cellW, 0, c * cellW, grid_rows * cellH]}
        stroke="rgba(99,179,237,0.10)" strokeWidth={0.5} listening={false} />
    )
  }
  for (let r = 0; r <= grid_rows; r++) {
    gridLines.push(
      <Line key={`h${r}`}
        points={[0, r * cellH, grid_cols * cellW, r * cellH]}
        stroke="rgba(99,179,237,0.10)" strokeWidth={0.5} listening={false} />
    )
  }

  // ── Hover highlight ────────────────────────────────────────────────────────
  const hoverRect = hoveredCell ? (
    <Rect
      x={hoveredCell.col * cellW} y={hoveredCell.row * cellH}
      width={cellW} height={cellH}
      fill="rgba(99,179,237,0.08)"
      stroke="rgba(99,179,237,0.55)" strokeWidth={1}
      listening={false}
    />
  ) : null

  // ── AI suggestion ghost pin ────────────────────────────────────────────────
  const suggestPin = suggestion ? (
    <Group
      x={suggestion.suggested_col * cellW + cellW / 2}
      y={suggestion.suggested_row * cellH + cellH / 2}
    >
      <Circle radius={Math.min(cellW, cellH) * 0.45}
        fill="rgba(6,214,160,0.06)" stroke="#06d6a0" strokeWidth={1.2}
        dash={[3, 2]} />
      <Circle radius={5} fill="#06d6a0" opacity={0.9} />
      <Text text="AI" fontSize={8} fontFamily="IBM Plex Mono" fill="#06d6a0"
        y={Math.min(cellW, cellH) * 0.47} offsetX={6}
        stroke="rgba(11,14,20,0.8)" strokeWidth={2} fillAfterStrokeEnabled />
    </Group>
  ) : null

  return (
    <div className="grid-canvas-wrap blueprint-bg">
      <Stage
        ref={stageRef}
        width={stageW} height={stageH}
        scaleX={scale} scaleY={scale}
        x={stagePos.x} y={stagePos.y}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
        onDblClick={handleDblClick}
        onWheel={handleWheel}
        style={{ cursor: activeTool === 'erase' ? 'cell' : activeTool === 'select' ? 'pointer' : 'crosshair' }}
        draggable={false}
      >
        {/* Layer 1 — Zone colours (background) */}
        <Layer>
          {overlays.zones && zoneCells}
        </Layer>

        {/* Layer 2 — ML overlays */}
        <Layer listening={false}>
          {overlays.heatmap && signalMatrix && (
            <HeatmapOverlay signalMatrix={signalMatrix} cellW={cellW} cellH={cellH} opacity={overlayOpacity} />
          )}
          {overlays.deadzone && deadZoneMask && (
            <DeadzoneOverlay deadZoneMask={deadZoneMask} cellW={cellW} cellH={cellH} opacity={overlayOpacity} />
          )}
          {overlays.interference && interferenceMatrix && (
            <InterferenceOverlay interferenceMatrix={interferenceMatrix} cellW={cellW} cellH={cellH} opacity={overlayOpacity} />
          )}
          {overlays.priority && (
            <PriorityOverlay cells={cells} gridRows={grid_rows} gridCols={grid_cols}
              cellW={cellW} cellH={cellH} opacity={overlayOpacity} />
          )}
        </Layer>

        {/* Layer 3 — Grid lines + hover */}
        <Layer listening={false}>
          {gridLines}
          {hoverRect}
        </Layer>

        {/* Layer 4 — Routers + AI pin (interactive) */}
        <Layer>
          {routers.map(r => (
            <RouterPin key={r.router_id} router={r} cellW={cellW} cellH={cellH}
              onClick={router => openRouterModal({ ...router, editMode: true })} />
          ))}
          {suggestPin}
        </Layer>
      </Stage>

      {/* Controls overlay */}
      <div className="canvas-controls">
        <button className="btn btn-sm" onClick={() => setScale(s => Math.min(s * 1.2, 10))}>+</button>
        <button className="btn btn-sm" onClick={() => setScale(s => Math.max(s / 1.2, 0.3))}>−</button>
        <button className="btn btn-sm" onClick={() => { setScale(1); setStagePos({ x: 0, y: 0 }) }}>⊙</button>
      </div>

      {hoveredCell && (
        <div className="canvas-coords">
          [{hoveredCell.row}, {hoveredCell.col}]
        </div>
      )}

      <style>{`
        .grid-canvas-wrap { position: relative; flex: 1; overflow: hidden; }
        .canvas-controls {
          position: absolute; top: 10px; right: 10px;
          display: flex; flex-direction: column; gap: 3px;
          z-index: 10;
        }
        .canvas-coords {
          position: absolute; bottom: 10px; left: 10px;
          font-family: var(--font-mono); font-size: 10px;
          color: var(--accent); background: rgba(11,14,20,0.7);
          border: 1px solid var(--border-bright); border-radius: var(--radius-sm);
          padding: 2px 8px; pointer-events: none;
        }
      `}</style>
    </div>
  )
}
