/**
 * Where each department's rota-export subteam order is remembered: this browser's localStorage.
 *
 * Deliberately per-device rather than stored on the department. It only arranges an image a head
 * is about to share, so a head on another device seeing the default order costs them one tap on
 * "Subteam order", and it needs no migration. If heads start asking for it to follow them between
 * devices, a nullable `subteams.display_order` column is the upgrade.
 *
 * Storage can be missing or throw (private windows, blocked site data), so every access is
 * guarded and any failure reads as "no saved order" — the export falls back to alphabetical.
 */

const storageKey = departmentId => `nca:rota-order:${departmentId}`

/**
 * The saved group keys for a department, or an empty list.
 *
 * @param {string} departmentId
 * @returns {Array<string>} Group keys: subteam ids, and '' for the Department group.
 */
export function loadRotaOrder(departmentId) {
    if (!departmentId) return []
    try {
        const parsed = JSON.parse(window.localStorage.getItem(storageKey(departmentId)) ?? '[]')
        return Array.isArray(parsed) ? parsed.filter(key => typeof key === 'string') : []
    } catch {
        return []
    }
}

/**
 * Remember a department's group order on this device. Fails silently: the order still applies
 * to the export open on screen, it just will not be there next time.
 *
 * @param {string} departmentId
 * @param {Array<string>} keys
 */
export function saveRotaOrder(departmentId, keys) {
    if (!departmentId) return
    try {
        window.localStorage.setItem(storageKey(departmentId), JSON.stringify(keys))
    } catch {
        // Storage unavailable or full; nothing to do.
    }
}
