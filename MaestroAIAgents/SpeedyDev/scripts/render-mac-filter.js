import fs from 'fs'

/**
 * Renders nftables policy for given MAC addresses
 * @param {string[]} macAddresses 
 * @returns {string} nftables ruleset
 */
function renderMacFilter(macAddresses) {
  const header = `table inet filter {
  chain input {
    type filter hook input priority 0; policy drop;`

  const rules = macAddresses.map(mac => `    ether saddr ${mac} accept;`).join('\n')

  const footer = `    iif "lo" accept;
  }
}`

  return `${header}\n${rules}\n${footer}`
}

// Example usage: Generate default policy
const defaultMacs = ['00:11:22:33:44:55', 'AA:BB:CC:DD:EE:FF']
const policy = renderMacFilter(defaultMacs)

console.log('--- Generated nftables Policy ---')
console.log(policy)

// Optional: Write to file if path provided
const outputPath = process.argv[2]
if (outputPath) {
  fs.writeFileSync(outputPath, policy)
  console.log(`\nPolicy written to ${outputPath}`)
}

export { renderMacFilter }
