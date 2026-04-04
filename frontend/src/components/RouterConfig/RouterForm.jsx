import React, { useState, useEffect } from 'react'
import useStore from '../../store/useStore'
import { useRouters } from '../../hooks/useRouters'

const FREQ_OPTIONS = [
  { label: '2.4 GHz', value: 2400 },
  { label: '5 GHz',   value: 5000 },
  { label: '6 GHz',   value: 6000 },
]

/**
 * RouterForm — modal for placing or editing a router.
 * Opened by double-clicking an allow_router=true cell, or clicking an existing pin.
 */
export default function RouterForm() {
  const { routerModal, closeRouterModal, routers, cells } = useStore()
  const { createRouter, removeRouterById, editRouter } = useRouters()

  const editMode = routerModal?.editMode
  const [form, setForm] = useState({
    name: '', tx_power_dbm: 20, frequency_mhz: 2400, channel: 1, range_m: 50, cost: 2000,
  })

  const chOptions = form.frequency_mhz < 3000 ? [1, 6, 11] :
    form.frequency_mhz < 5900 ? [36, 40, 44, 48, 149, 153, 157, 161] : [1, 5, 9, 13]

  useEffect(() => {
    if (!routerModal) return
    if (editMode) {
      setForm({
        name: routerModal.name ?? '',
        tx_power_dbm: routerModal.tx_power_dbm ?? 20,
        frequency_mhz: routerModal.frequency_mhz ?? 2400,
        channel: routerModal.channel ?? 1,
        range_m: routerModal.range_m ?? 50,
        cost: routerModal.cost ?? 2000,
      })
    } else {
      setForm(f => ({ ...f, name: `R${Math.floor(routerModal.row)}-AP${String(routers.length + 1).padStart(2, '0')}` }))
    }
  }, [routerModal])

  if (!routerModal) return null

  const set = (k, v) => setForm(f => ({ ...f, [k]: v }))

  const cell = !editMode && cells.find(c => c.row === routerModal.row && c.col === routerModal.col)

  const handleSubmit = async () => {
    if (!form.name.trim()) return
    if (editMode) {
      await editRouter(routerModal.router_id, form)
    } else {
      await createRouter({ ...form, row: routerModal.row, col: routerModal.col })
    }
    closeRouterModal()
  }

  const handleDelete = async () => {
    if (editMode) {
      await removeRouterById(routerModal.router_id, routerModal.name)
    }
    closeRouterModal()
  }

  return (
    <div className="modal-backdrop" onClick={closeRouterModal}>
      <div className="modal-box fade-up" onClick={e => e.stopPropagation()}>

        <div className="modal-head">
          <div className="modal-head-left">
            <span className="modal-icon">⬡</span>
            <div>
              <p className="modal-title">{editMode ? `Edit ${routerModal.name}` : 'Place Router'}</p>
              <p className="modal-sub">
                {editMode
                  ? `Row ${routerModal.row} · Col ${routerModal.col}`
                  : `Row ${routerModal.row} · Col ${routerModal.col}${cell ? ` · ${cell.zone_type}` : ''}`}
              </p>
            </div>
          </div>
          <button className="btn btn-sm" onClick={closeRouterModal}>✕</button>
        </div>

        <div className="modal-body">
          <div className="form-grid">
            <div className="field" style={{ gridColumn: '1/-1' }}>
              <label>Router Name</label>
              <input value={form.name} onChange={e => set('name', e.target.value)} placeholder="R1-AP01" />
            </div>

            <div className="field">
              <label>TX Power (dBm)</label>
              <input type="number" min={1} max={30} value={form.tx_power_dbm}
                onChange={e => set('tx_power_dbm', parseFloat(e.target.value))} />
            </div>

            <div className="field">
              <label>Range (m)</label>
              <input type="number" min={5} max={500} value={form.range_m}
                onChange={e => set('range_m', parseFloat(e.target.value))} />
            </div>

            <div className="field">
              <label>Frequency</label>
              <select value={form.frequency_mhz} onChange={e => {
                const f = parseFloat(e.target.value)
                set('frequency_mhz', f)
                set('channel', f < 3000 ? 1 : 36)
              }}>
                {FREQ_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
            </div>

            <div className="field">
              <label>Channel</label>
              <select value={form.channel} onChange={e => set('channel', parseInt(e.target.value))}>
                {chOptions.map(c => <option key={c} value={c}>{c}</option>)}
              </select>
            </div>

            <div className="field" style={{ gridColumn: '1/-1' }}>
              <label>Cost (₹)</label>
              <input type="number" min={0} value={form.cost}
                onChange={e => set('cost', parseFloat(e.target.value))} />
            </div>
          </div>
        </div>

        <div className="modal-foot">
          {editMode && <button className="btn btn-danger btn-sm" onClick={handleDelete}>Remove</button>}
          <span style={{ flex: 1 }} />
          <button className="btn btn-sm" onClick={closeRouterModal}>Cancel</button>
          <button className="btn btn-primary" onClick={handleSubmit}>
            {editMode ? 'Save' : 'Place Router'}
          </button>
        </div>
      </div>

      <style>{`
        .modal-backdrop {
          position: fixed; inset: 0; z-index: 200;
          background: rgba(0,0,0,0.65); backdrop-filter: blur(6px);
          display: flex; align-items: center; justify-content: center;
        }
        .modal-box {
          background: var(--bg-elevated);
          border: 1px solid var(--border-bright);
          border-radius: var(--radius-xl);
          width: 400px; max-width: 94vw;
          box-shadow: 0 24px 80px rgba(0,0,0,0.6), 0 0 30px rgba(99,179,237,0.08);
        }
        .modal-head {
          display: flex; align-items: center; justify-content: space-between;
          padding: 16px 18px; border-bottom: 1px solid var(--border);
        }
        .modal-head-left { display: flex; align-items: center; gap: 10px; }
        .modal-icon { font-size: 20px; color: var(--accent); }
        .modal-title { font-family: var(--font-display); font-size: 14px; font-weight: 700; color: var(--text-primary); }
        .modal-sub { font-size: 9px; color: var(--text-muted); margin-top: 2px; }
        .modal-body { padding: 18px; }
        .form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
        .modal-foot {
          display: flex; align-items: center; gap: 8px;
          padding: 12px 18px; border-top: 1px solid var(--border);
        }
      `}</style>
    </div>
  )
}
