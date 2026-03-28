import { serve } from '@hono/node-server'
import { Hono } from 'hono'
import { cors } from 'hono/cors'
import { logger } from 'hono/logger'
import { readFile, writeFile, readdir } from 'node:fs/promises'
import { join, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'
import { spawn } from 'node:child_process'
import DockerModem from 'docker-modem'
import yaml from 'yaml'
import { chromium } from 'playwright'

const __dirname = dirname(fileURLToPath(import.meta.url))
const app = new Hono()
const modem = new DockerModem()

// Middleware
app.use('*', logger())
app.use('*', cors())

// Configuration
const CONFIG_DIR = join(__dirname, '../../config')
const SERVICES_FILE = join(CONFIG_DIR, 'services.yaml')
const AUTO_LOGIN_FILE = join(CONFIG_DIR, 'auto-login.yaml')

// --- Utilities ---
const loadYaml = async (path) => {
  try {
    const content = await readFile(path, 'utf8')
    return yaml.parse(content)
  } catch {
    return {}
  }
}

// --- Playwright Auto-Login ---
const performAutoLogin = async (serviceName) => {
  const config = await loadYaml(AUTO_LOGIN_FILE)
  const service = config.services?.[serviceName]
  
  if (!service) throw new Error(`Service ${serviceName} not found in auto-login.yaml`)
  
  const user = process.env[service.env_user]
  const pass = process.env[service.env_pass]
  
  if (!user || !pass) throw new Error(`Missing environment variables for ${serviceName}`)
  
  const browser = await chromium.launch({ headless: true })
  try {
    const context = await browser.newContext()
    const page = await context.newPage()
    
    console.log(`[Auto-Login] Navigating to ${service.url} for ${serviceName}`)
    await page.goto(service.url)
    
    await page.fill(service.username_selector, user)
    await page.fill(service.password_selector, pass)
    await page.click(service.submit_selector)
    
    // Wait for success indicator or a bit of time
    try {
      await page.waitForSelector(service.success_indicator, { timeout: 10000 })
    } catch (e) {
      console.warn(`[Auto-Login] Success indicator ${service.success_indicator} not found for ${serviceName}, continuing anyway.`)
    }
    
    const cookies = await context.cookies()
    return cookies
  } finally {
    await browser.close()
  }
}

// --- Service Handlers ---
const getDockerStatus = (composePath) => {
  return new Promise((resolve) => {
    const composeDir = dirname(composePath)
    const ps = spawn('docker', ['compose', '-f', composePath, 'ps', '--format', 'json'], { cwd: composeDir })
    let output = ''
    ps.stdout.on('data', (data) => output += data)
    ps.on('close', () => {
      resolve(output.toLowerCase().includes('running') ? 'running' : 'stopped')
    })
  })
}

const getSystemdStatus = (serviceName) => {
  return new Promise((resolve) => {
    const ps = spawn('systemctl', ['--user', 'is-active', serviceName])
    let output = ''
    ps.stdout.on('data', (data) => output += data)
    ps.on('close', () => {
      resolve(output.trim())
    })
  })
}

// --- Endpoints ---
app.get('/api/services', async (c) => {
  const config = await loadYaml(SERVICES_FILE)
  const services = config.services || []
  
  const statusPromises = services.map(async (s) => {
    let status = 'unknown'
    if (s.type === 'docker-compose') {
      status = await getDockerStatus(s.path)
    } else if (s.type === 'systemd') {
      status = await getSystemdStatus(s.service_name)
    }
    return { ...s, status }
  })
  
  return c.json(await Promise.all(statusPromises))
})

app.post('/api/services/:name/control', async (c) => {
  const name = c.req.param('name')
  const { action } = await c.req.json()
  const config = await loadYaml(SERVICES_FILE)
  const service = config.services?.find(s => s.name === name)
  
  if (!service) return c.json({ error: 'Not found' }, 404)
  
  let cmd, args, cwd
  if (service.type === 'docker-compose') {
    cmd = 'docker'
    args = ['compose', '-f', service.path, action]
    cwd = dirname(service.path)
  } else if (service.type === 'systemd') {
    cmd = 'systemctl'
    args = ['--user', action, service.service_name]
  }
  
  if (cmd) {
    spawn(cmd, args, { cwd, detached: true }).unref()
    return c.json({ status: 'success', action })
  }
  
  return c.json({ error: 'Invalid service type' }, 400)
})

// --- Auto-Login API ---
app.post('/api/login/:service', async (c) => {
  const serviceName = c.req.param('service')
  console.log(`[Auto-Login Request] ${serviceName}`)
  
  try {
    const cookies = await performAutoLogin(serviceName)
    const loginConfig = await loadYaml(AUTO_LOGIN_FILE)
    const service = loginConfig.services?.[serviceName]
    
    if (service) {
      // Set cookies in the browser response
      cookies.forEach(cookie => {
        c.header('Set-Cookie', `${cookie.name}=${cookie.value}; Path=/; Domain=${cookie.domain}; HttpOnly; Secure`, { append: true })
      })
      
      return c.json({ status: 'success', cookies: cookies.length })
    }
    
    return c.json({ error: 'Service configuration not found' }, 404)
  } catch (error) {
    console.error(`[Auto-Login Error] ${error.message}`)
    return c.json({ error: error.message }, 500)
  }
})

// --- Discovery ---
app.get('/api/discover', async (c) => {
  const searchPaths = [join(process.env.HOME, 'dev')]
  const discovered = []
  
  // Simple scan (recursive glob would be better with a library)
  // For now returning empty to be filled by Playbook
  return c.json(discovered)
})

const port = process.env.DASHBOARD_PORT || 8889
console.log(`Server is running on port ${port}`)

serve({
  fetch: app.fetch,
  port
})
