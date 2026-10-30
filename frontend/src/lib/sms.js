/**
 * Explaining why a worker's texts are not getting through.
 *
 * Pure and React-free, like attendance.js. The backend stamps `sms_blocked_at` when Twilio refuses
 * a number for good, and stops texting it; this turns Twilio's code into something a head can act
 * on. Saving the worker's phone in Edit clears the block, so every hint ends there.
 */

// Twilio: the recipient replied STOP to our number.
const OPTED_OUT = 21610

/** Null when texts can reach the worker, otherwise { label, hint } for a badge and its tooltip. */
export function smsBlock(worker) {
    if (!worker?.sms_blocked_at) return null
    if (worker.sms_error_code === OPTED_OUT) {
        return {
            label: 'Replied STOP',
            hint: 'They replied STOP to our texts. Once they text START to the same number, save their phone in Edit to resume.',
        }
    }
    return {
        label: 'Texts failing',
        hint: "This number can't receive texts. Correct it in Edit to resume.",
    }
}
