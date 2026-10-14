import { useCallback, useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'

const SEARCH_DEBOUNCE_MS = 300

/**
 * Search, filter and page state for a list page, kept in the URL so refresh, back and a shared
 * link all land on the same view.
 *
 * `q` and `page` are always handled; `filterKeys` names the page's other params. Changing the
 * search or any filter returns to page 1 — page 4 of an old result means nothing in a new one.
 * The search box updates immediately; the URL (and so the request) follows after a short pause.
 */
export function useListParams(filterKeys = []) {
    const [searchParams, setSearchParams] = useSearchParams()
    const q = searchParams.get('q') ?? ''
    const page = Math.max(1, Number(searchParams.get('page')) || 1)
    const filters = Object.fromEntries(filterKeys.map(k => [k, searchParams.get(k) ?? '']))

    const [searchText, setSearchText] = useState(q)

    const update = useCallback(
        changes =>
            setSearchParams(
                prev => {
                    const next = new URLSearchParams(prev)
                    for (const [k, v] of Object.entries(changes)) {
                        if (v && v !== 1) next.set(k, String(v))
                        else next.delete(k)
                    }
                    if (!('page' in changes)) next.delete('page')
                    return next
                },
                { replace: true }
            ),
        [setSearchParams]
    )

    // Follows the URL when it changes underneath the box (back/forward, Clear filters), but leaves
    // the box alone when only whitespace differs, or a pause after "john " would eat the space.
    useEffect(() => setSearchText(prev => (prev.trim() === q ? prev : q)), [q])

    useEffect(() => {
        if (searchText.trim() === q) return
        const timer = setTimeout(() => update({ q: searchText.trim() }), SEARCH_DEBOUNCE_MS)
        return () => clearTimeout(timer)
    }, [searchText, q, update])

    const hasFilters = Boolean(q) || Object.values(filters).some(Boolean)
    const setFilter = useCallback((key, value) => update({ [key]: value }), [update])
    const setPage = useCallback(next => update({ page: next }), [update])
    const filterKeyList = filterKeys.join(',')
    const clear = useCallback(
        () =>
            update(
                Object.fromEntries(
                    ['q', ...filterKeyList.split(',').filter(Boolean)].map(k => [k, ''])
                )
            ),
        [update, filterKeyList]
    )

    return {
        q,
        page,
        filters,
        searchText,
        setSearchText,
        hasFilters,
        setFilter,
        setPage,
        clear,
    }
}
