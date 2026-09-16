import { execSync } from 'node:child_process'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'
import { fileURLToPath } from 'url'

const __dirname = fileURLToPath(new URL('.', import.meta.url))

// Stamped into every bug report's context so a report can be tied to the build it came from.
// Guarded because a deploy that builds from a tarball has no git history — and a missing version
// is not worth failing a build over.
const appVersion = (() => {
    try {
        return execSync('git rev-parse --short HEAD').toString().trim()
    } catch {
        return 'unknown'
    }
})()

export default defineConfig({
    define: {
        'import.meta.env.VITE_APP_VERSION': JSON.stringify(appVersion),
    },
    plugins: [react(), tailwindcss()],
    resolve: {
        alias: {
            '@': path.resolve(__dirname, './src'),
        },
    },
})
