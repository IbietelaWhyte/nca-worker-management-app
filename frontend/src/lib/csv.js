/**
 * CSV as a spreadsheet actually reads it. Pure and React-free, like rota.js and staffing.js.
 *
 * Three things a naive join(',') gets wrong, all of which this app hits:
 *
 * 1. **Formula injection.** Excel and Google Sheets execute any cell beginning =, +, - or @.
 *    Worker names are user-entered — the CSV import lets anyone type one — so a name is
 *    untrusted input arriving in a spreadsheet, the same way FeedbackService._fence_for treats
 *    typed text arriving in GitHub markdown. A leading apostrophe defuses it and every
 *    spreadsheet strips it on display.
 * 2. **Quoting.** A comma, a quote, a newline or an edge space has to be quoted with inner
 *    quotes doubled. Department and subteam names contain commas in practice.
 * 3. **The BOM.** Excel on Windows reads a BOM-less file as the system codepage, so accented
 *    names arrive mangled. Three bytes fix it and nothing else notices.
 */

const RISKY = /^[=+\-@\t\r]/
const NEEDS_QUOTES = /[",\n\r]|^\s|\s$/

const cell = value => {
    if (value === null || value === undefined) return ''
    let text = String(value)
    if (RISKY.test(text)) text = `'${text}`
    return NEEDS_QUOTES.test(text) ? `"${text.replace(/"/g, '""')}"` : text
}

/** Rows as a CSV string. CRLF because that is what every spreadsheet writes. */
export const toCsv = (headers, rows) =>
    [headers, ...rows].map(row => row.map(cell).join(',')).join('\r\n')

/** Hand the browser a file. No dependency: a Blob, an object URL and a click. */
export const downloadCsv = (filename, text) => {
    // \uFEFF, written as an escape so the source file itself does not carry a BOM — see note 3 above.
    const blob = new Blob(['\uFEFF', text], { type: 'text/csv;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = filename
    link.click()
    // Without this the blob stays pinned for the life of the document.
    URL.revokeObjectURL(url)
}
