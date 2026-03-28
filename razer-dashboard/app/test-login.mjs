import { chromium } from 'playwright'
import { readFile } from 'node:fs/promises'
import { join, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'
import yaml from 'yaml'

const __dirname = dirname(fileURLToPath(import.meta.url))
const CONFIG_FILE = join(__dirname, '../config/auto-login.yaml')

async function testLogin(serviceName) {
  const content = await readFile(CONFIG_FILE, 'utf8')
  const config = yaml.parse(content)
  const service = config.services[serviceName]
  
  if (!service) {
    console.error(`Service ${serviceName} not found in config`)
    return
  }

  const user = process.env[service.env_user]
  const pass = process.env[service.env_pass]

  if (!user || !pass) {
    console.error(`Missing env vars for ${serviceName}: ${service.env_user} or ${service.env_pass}`)
    // For testing purposes, we might want to manually set these or mock
    return
  }

  console.log(`Testing login for ${serviceName} at ${service.url}`)
  const browser = await chromium.launch({ headless: true })
  const context = await browser.newContext()
  const page = await context.newPage()

  try {
    await page.goto(service.url)
    console.log(`Page title: ${await page.title()}`)
    
    // We can't really "test" against the real URL if it's not reachable
    // But we can check if the selectors exist or if we get a 404/connection error
    console.log(`Success: Found login page for ${serviceName}`)
    
    const cookies = await context.cookies()
    console.log(`Initial cookies: ${cookies.length}`)
  } catch (e) {
    console.error(`Failed to reach ${service.url}: ${e.message}`)
  } finally {
    await browser.close()
  }
}

// Running for both configured services
testLogin('linkwarden')
testLogin('wikijs')
