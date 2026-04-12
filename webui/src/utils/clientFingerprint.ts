type FingerprintPayload = {
  fingerprint: string
  userAgent: string
  browser: {
    name: string
    version: string
  }
  engine: string
  os: string
  platform: string
  language: string
  languages: string[]
  timezone: string
  screen: {
    width: number
    height: number
    colorDepth: number
    pixelRatio: number
  }
  viewport: {
    width: number
    height: number
  }
  hardware: {
    cores: number | null
    memoryGb: number | null
    touchPoints: number
  }
  features: {
    cookieEnabled: boolean
    doNotTrack: string | null
    webdriver: boolean
  }
}

const hashString = (value: string) => {
  let hash = 2166136261
  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index)
    hash = Math.imul(hash, 16777619)
  }
  return (hash >>> 0).toString(16).padStart(8, '0')
}

const parseBrowser = (ua: string) => {
  const rules: Array<[string, RegExp]> = [
    ['Edge', /Edg\/([\d.]+)/],
    ['Chrome', /Chrome\/([\d.]+)/],
    ['Firefox', /Firefox\/([\d.]+)/],
    ['Safari', /Version\/([\d.]+).*Safari/],
  ]
  for (const [name, pattern] of rules) {
    const match = ua.match(pattern)
    if (match) return { name, version: match[1] || '' }
  }
  return { name: 'Unknown', version: '' }
}

const parseEngine = (ua: string) => {
  if (/AppleWebKit/i.test(ua)) return 'WebKit/Blink'
  if (/Gecko\//i.test(ua)) return 'Gecko'
  if (/Trident|MSIE/i.test(ua)) return 'Trident'
  return 'Unknown'
}

const parseOs = (ua: string) => {
  if (/Windows NT/i.test(ua)) return 'Windows'
  if (/Mac OS X/i.test(ua)) return 'macOS'
  if (/Android/i.test(ua)) return 'Android'
  if (/iPhone|iPad|iPod/i.test(ua)) return 'iOS'
  if (/Linux/i.test(ua)) return 'Linux'
  return 'Unknown'
}

export async function collectClientFingerprint(): Promise<FingerprintPayload> {
  const nav = window.navigator as Navigator & {
    deviceMemory?: number
    webdriver?: boolean
  }
  const userAgent = nav.userAgent || ''
  const browser = parseBrowser(userAgent)
  const payload: Omit<FingerprintPayload, 'fingerprint'> = {
    userAgent,
    browser,
    engine: parseEngine(userAgent),
    os: parseOs(userAgent),
    platform: nav.platform || '',
    language: nav.language || '',
    languages: Array.from(nav.languages || []),
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || '',
    screen: {
      width: window.screen?.width || 0,
      height: window.screen?.height || 0,
      colorDepth: window.screen?.colorDepth || 0,
      pixelRatio: window.devicePixelRatio || 1,
    },
    viewport: {
      width: window.innerWidth || 0,
      height: window.innerHeight || 0,
    },
    hardware: {
      cores: nav.hardwareConcurrency || null,
      memoryGb: nav.deviceMemory || null,
      touchPoints: nav.maxTouchPoints || 0,
    },
    features: {
      cookieEnabled: Boolean(nav.cookieEnabled),
      doNotTrack: nav.doNotTrack || null,
      webdriver: Boolean(nav.webdriver),
    },
  }

  return {
    fingerprint: hashString(JSON.stringify(payload)),
    ...payload,
  }
}
