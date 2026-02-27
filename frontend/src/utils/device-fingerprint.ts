/**
 * 采集浏览器特征并生成设备指纹哈希。
 * 优先使用 crypto.subtle（HTTPS），降级到 djb2（HTTP 兼容）。
 */

function djb2Hash(str: string): string {
  let hash = 5381
  for (let i = 0; i < str.length; i++) {
    hash = ((hash << 5) + hash) ^ str.charCodeAt(i)
    hash = hash >>> 0  // 转为无符号 32 位
  }
  return hash.toString(16).padStart(8, '0')
}

export async function getDeviceFingerprint(): Promise<string> {
  const features = [
    navigator.userAgent,
    navigator.language,
    `${screen.width}x${screen.height}`,
    Intl.DateTimeFormat().resolvedOptions().timeZone,
    navigator.platform,
  ].join('|')

  // 优先使用 crypto.subtle（HTTPS 环境）
  if (typeof crypto !== 'undefined' && crypto.subtle) {
    try {
      const data = new TextEncoder().encode(features)
      const hashBuffer = await crypto.subtle.digest('SHA-256', data)
      const hashArray = Array.from(new Uint8Array(hashBuffer))
      return hashArray.map(b => b.toString(16).padStart(2, '0')).join('')
    } catch {
      // 降级
    }
  }

  // HTTP 降级：djb2 哈希（不需要 HTTPS）
  return djb2Hash(features)
}
