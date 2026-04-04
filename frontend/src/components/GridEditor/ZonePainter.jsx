/**
 * ZonePainter — stateless helper that computes cell paint/erase logic.
 * Used by GridCanvas to handle mouse events.
 *
 * No JSX — this is a logic module, not a rendered component.
 * GridCanvas imports and calls these helpers directly.
 */
import { ZONE_CONFIG, getZone } from '../../constants/zoneConfig'

/**
 * Returns an updated cell object after painting.
 * @param {Object} cell   - existing cell from store
 * @param {string} zoneKey - active zone key
 * @param {string} tool    - 'paint' | 'erase'
 */
export function applyPaint(cell, zoneKey, tool) {
  if (tool === 'erase') {
    const noZone = ZONE_CONFIG.no_zone
    return {
      ...cell,
      zone_type:       'no_zone',
      attenuation:     noZone.attenuation,
      priority_weight: noZone.priority_weight,
      allow_router:    noZone.allow_router,
    }
  }
  const z = getZone(zoneKey)
  return {
    ...cell,
    zone_type:       zoneKey,
    attenuation:     z.attenuation,
    priority_weight: z.priority_weight,
    allow_router:    z.allow_router,
  }
}

/**
 * Given a pixel position on the Konva stage and canvas dimensions,
 * returns { row, col } or null if out of bounds.
 */
export function pixelToCell(x, y, cellW, cellH, gridRows, gridCols) {
  const col = Math.floor(x / cellW)
  const row = Math.floor(y / cellH)
  if (row < 0 || row >= gridRows || col < 0 || col >= gridCols) return null
  return { row, col }
}
