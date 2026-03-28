import { readFile, writeFile } from 'node:fs/promises'
import { join, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'
import yaml from 'yaml'

const __dirname = dirname(fileURLToPath(import.meta.url))
const CONFIG_DIR = join(__dirname, '../config')
const DEVICES_FILE = join(CONFIG_DIR, 'allowed_devices.yaml')
const FILTER_FILE = join(CONFIG_DIR, 'mac-filter.sh')

const renderFilter = async () => {
  try {
    const devicesContent = await readFile(DEVICES_FILE, 'utf8')
    const config = yaml.parse(devicesContent)
    const devices = config.devices || []
    
    let rules = '#!/bin/bash\n# Auto-generated nftables rules\n\n'
    rules += 'nft add table inet dashboard_filter\n'
    rules += 'nft add chain inet dashboard_filter input { type filter hook input priority 0; policy drop; }\n'
    rules += 'nft add rule inet dashboard_filter input iif lo accept\n'
    
    devices.forEach(d => {
      rules += `nft add rule inet dashboard_filter input ether saddr ${d.mac} accept\n`
    })
    
    rules += 'nft add rule inet dashboard_filter input tcp dport 8888 drop\n'
    
    await writeFile(FILTER_FILE, rules)
    console.log('Successfully rendered MAC filters to ' + FILTER_FILE)
  } catch (e) {
    console.error('Failed to render filters:', e.message)
  }
}

renderFilter()
