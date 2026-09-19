// 后端 API 客户端：WebSocket 流式核验 + 人工复核 + 健康检查。

function wsBase() {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws'
  return `${proto}://${location.host}`
}

function fileToBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => {
      const dataUrl = reader.result
      const b64 = String(dataUrl).split(',')[1] || ''
      resolve({ name: file.name, data: b64 })
    }
    reader.onerror = reject
    reader.readAsDataURL(file)
  })
}

export async function verifyStreaming({ text, files, onStep, onResult, onError, onDone }) {
  const images = []
  for (const f of files || []) {
    images.push(await fileToBase64(f))
  }
  const ws = new WebSocket(`${wsBase()}/ws/verify`)

  ws.onopen = () => {
    ws.send(JSON.stringify({ text, images }))
  }
  ws.onmessage = (ev) => {
    const msg = JSON.parse(ev.data)
    if (msg.type === 'step') onStep?.(msg)
    else if (msg.type === 'result') onResult?.(msg.data)
    else if (msg.type === 'error') onError?.(msg.message)
  }
  ws.onerror = () => onError?.('WebSocket 连接失败，请确认后端已启动')
  ws.onclose = () => onDone?.()

  return ws
}

export async function submitFeedback(taskId, claimId, verdict, comment) {
  const res = await fetch('/feedback', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ task_id: taskId, claim_id: claimId, user_verdict: verdict, comment }),
  })
  return res.json()
}

export async function getHealth() {
  const res = await fetch('/health')
  return res.json()
}
