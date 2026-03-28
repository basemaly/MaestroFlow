import { Hono } from 'hono'
import { serve } from '@hono/node-server'
import { serveStatic } from '@hono/node-server/serve-static'
import { exec } from 'child_process'
import { promisify } from 'util'
import fs from 'fs'
import path from 'path'

const execPromise = promisify(exec)
const app = new Hono()

// Serve frontend files
app.use('/static/*', serveStatic({ root: './' }))
app.get('/', (c) => c.redirect('/static/frontend/index.html'))

// FS Discovery API
app.get('/config-files', async (c) => {
  try {
    const configDir = path.resolve('./config')
    const files = fs.readdirSync(configDir).map(file => {
        const filePath = path.join(configDir, file)
        const stats = fs.statSync(filePath)
        return {
            name: file,
            size: stats.size,
            mtime: stats.mtime,
            isDirectory: stats.isDirectory()
        }
    })
    
    return c.json({
      path: configDir,
      files
    })
  } catch (error) {
    return c.json({ error: error.message }, 500)
  }
})

// Basic status API
app.get('/status', async (c) => {
  try {
    const { stdout: dockerStatus } = await execPromise('docker ps --format "{{.Names}}: {{.Status}}"').catch(() => ({ stdout: "No docker daemon running" }))
    const { stdout: systemdStatus } = await execPromise('systemctl is-active razer-service || echo "inactive"').catch(() => ({ stdout: "inactive" }))
    
    return c.json({
      docker: dockerStatus.trim().split('\n').filter(Boolean),
      systemd: systemdStatus.trim(),
      timestamp: new Date().toISOString()
    })
  } catch (error) {
    return c.json({ error: error.message }, 500)
  }
})

// app.get('/', (c) => c.text('Razer Dashboard API')) // Commented out to prefer the redirect

const port = 3000
console.log(`Server is running on port ${port}`)

serve({
  fetch: app.fetch,
  port
})
