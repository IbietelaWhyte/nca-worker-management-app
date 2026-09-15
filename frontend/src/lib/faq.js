/**
 * The help page's questions and answers.
 *
 * Kept here, React-free like lib/rota.js and lib/dashboard.js, so the copy can be reviewed and
 * corrected without reading JSX — the people most likely to edit this file are the ones who
 * answer these questions for real, not the ones building the page.
 *
 * The copy is written for volunteers, not for staff: it names what you tap and what happens
 * next, and it never says "assignment" where "duty" will do.
 *
 * `audience: 'everyone'` shows to every signed-in user. `'heads'` sections are appended for
 * admins, HODs and assistant HODs — they get both halves rather than a separate page, because a
 * head of department also serves on rotas and gets the same texts as everybody else.
 */

export const FAQ_SECTIONS = [
    {
        id: 'everyone',
        title: 'For everyone',
        audience: 'everyone',
        items: [
            {
                question: 'How do I tell the app when I cannot serve?',
                answer: 'Open Availability and tap a date. The first tap marks it as a date you can serve, a second marks you unavailable, and a third clears it again. You only need to mark the exceptions — a date you have left alone already counts as available.',
            },
            {
                question: 'I got a text saying I have been scheduled. What do I do?',
                answer: 'Tap the link in the message and confirm or decline. You do not need to sign in, and one link covers every date in that text. Closer to the day you will get a second text reminding you.',
            },
            {
                question: 'I said yes, but now I cannot make it.',
                answer: 'Open your dashboard and press "Can\'t make it" on that duty, or use the link from your text again. Your head of department is told, but nobody is put in your place automatically — so the earlier you say, the easier it is to find cover.',
            },
            {
                question: 'How does the app decide who serves?',
                answer: 'It leaves out anyone who has marked themselves unavailable and anyone already serving elsewhere that same day, then works down from whoever served least recently. A quiet month usually means you were unavailable, already booked, or the team is bigger than the number of places.',
            },
            {
                question: 'How do I change my phone number or my password?',
                answer: 'Both are on the Account page. Keep your phone number up to date — every reminder and confirmation link is sent to it by text.',
            },
        ],
    },
    {
        id: 'team',
        title: 'Setting up your team',
        audience: 'heads',
        items: [
            {
                question: 'What is the difference between a subteam and a role?',
                answer: 'A subteam is a group that serves together, like Team A and Team B, and can have its own number of workers per service. A role is the job somebody does on the day, like Head Usher. A worker can have both, or neither.',
            },
            {
                question: 'Where do I set how many workers are scheduled per service?',
                answer: 'On the department. A subteam can override it with its own number, and a whole-department schedule fills each subteam to its own figure rather than sharing one total between them.',
            },
            {
                question: 'Can I add my whole team at once?',
                answer: 'Yes. Open the department and choose to import a CSV. Download the sample file, fill it in and upload it — you get a row-by-row preview before anything is saved. One bad row stops the whole import, and people already on your roster are flagged as duplicates rather than errors, so re-uploading a roster is safe.',
            },
            {
                question: 'Somebody needs to sign in to the app.',
                answer: 'Ask an administrator to create their account; only administrators can. A worker does not need one to be scheduled — their duties, reminders and confirmation links reach them by text either way.',
            },
        ],
    },
    {
        id: 'rota',
        title: 'Building the rota',
        audience: 'heads',
        items: [
            {
                question: 'What do the three scopes mean when I create a schedule?',
                answer: 'Subteam schedules one group. Department only schedules the members who are not in any subteam. Whole department schedules everybody, filling each subteam to its own number of workers.',
            },
            {
                question: 'Can I plan a whole month in one go?',
                answer: 'Yes. Generating a month shows you every date first, with the workers it would pick and who is spare. Nothing is saved until you commit, and you can drop any date you do not want.',
            },
            {
                question: 'Why was a date skipped or left understaffed?',
                answer: 'Either too few people were left once unavailability and same-day clashes were taken out, or a schedule already exists for that department and date. The preview gives the reason beside each date.',
            },
            {
                question: 'Can I change a rota after it has been generated?',
                answer: "Yes. Open the schedule to change somebody's role or take them off and pick another worker. There can only be one schedule per department, date and subteam, so adjust the existing one rather than generating a second.",
            },
        ],
    },
    {
        id: 'messages',
        title: 'Keeping workers informed',
        audience: 'heads',
        items: [
            {
                question: 'When do workers actually get a text?',
                answer: 'Once soon after the schedule is created, listing every date they are on, and again a few days before the service itself. You set that lead time on each schedule. Reminders go out in the morning.',
            },
            {
                question: 'How do I collect availability from my team?',
                answer: 'Open the department and send an availability request. You can send it now or have it go out each month on a day you choose. Workers get a link that works without signing in, so it reaches the ones with no account too. Each message costs money to send, so it is never sent automatically on your behalf.',
            },
            {
                question: 'Somebody declined. What happens next?',
                answer: 'Nothing automatic. The decline appears at the top of your dashboard with their name and the date, and you choose the replacement yourself.',
            },
            {
                question: 'How do I share the rota with people who do not use the app?',
                answer: 'Open the schedule and export the month as an image, then send it on however your team already talks. It is laid out to stay readable in a group chat.',
            },
        ],
    },
]

/**
 * The sections a given user should see.
 *
 * @param {boolean} isDepartmentHead True for admins, HODs and assistant HODs.
 * @returns {typeof FAQ_SECTIONS} Everyone's questions, followed by the management ones when they apply.
 */
export function faqSectionsFor(isDepartmentHead) {
    return FAQ_SECTIONS.filter(section => section.audience === 'everyone' || isDepartmentHead)
}
