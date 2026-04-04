/**
 * zoneConfig.js — Zone type definitions
 * Exactly as specified in the PDF (Section 9, HOUR 2-4).
 * attenuation_db, priority_weight, allow_router drive all ML calculations.
 */
export const ZONE_CONFIG = {
    office:       { attenuation: 6.0,  priority_weight: 1.5, allow_router: true,  color: '#60A5FA', label: 'Office' },
    meeting_room: { attenuation: 5.0,  priority_weight: 1.2, allow_router: true,  color: '#A78BFA', label: 'Meeting Room' },
    bathroom:     { attenuation: 7.0,  priority_weight: 0.3, allow_router: false, color: '#F87171', label: 'Bathroom' },
    corridor:     { attenuation: 2.0,  priority_weight: 0.8, allow_router: true,  color: '#34D399', label: 'Corridor' },
    lobby:        { attenuation: 3.0,  priority_weight: 1.0, allow_router: true,  color: '#FBBF24', label: 'Lobby' },
    server_room:  { attenuation: 9.0,  priority_weight: 2.2, allow_router: false, color: '#6366F1', label: 'Server Room' },
    staircase:    { attenuation: 4.0,  priority_weight: 0.4, allow_router: false, color: '#9CA3AF', label: 'Staircase' },
    storage:      { attenuation: 5.0,  priority_weight: 0.3, allow_router: false, color: '#D97706', label: 'Storage' },
    outdoor:      { attenuation: 1.0,  priority_weight: 0.5, allow_router: true,  color: '#4ADE80', label: 'Outdoor' },
    no_zone:      { attenuation: 99.0, priority_weight: 0.0, allow_router: false, color: '#374151', label: 'No Zone' },
  }
  
  export const ZONE_KEYS = Object.keys(ZONE_CONFIG)
  
  /** Get zone config safely, falling back to no_zone */
  export function getZone(zoneType) {
    return ZONE_CONFIG[zoneType] ?? ZONE_CONFIG.no_zone
  }
  
  /** Signal quality thresholds → label + colour */
  export const SIGNAL_QUALITY = [
    { label: 'EXCELLENT', min: -50,       color: '#10B981' },
    { label: 'GOOD',      min: -67,       color: '#F59E0B' },
    { label: 'FAIR',      min: -75,       color: '#F97316' },
    { label: 'POOR',      min: -85,       color: '#EF4444' },
    { label: 'DEAD',      min: -Infinity, color: '#000000' },
  ]
  
  export function signalColor(dbm) {
    for (const { min, color } of SIGNAL_QUALITY) {
      if (dbm >= min) return color
    }
    return '#000000'
  }
  
  export function signalLabel(dbm) {
    for (const { min, label } of SIGNAL_QUALITY) {
      if (dbm >= min) return label
    }
    return 'DEAD'
  }
  