const activeAuthTransitions = new Set()

function registerTransition(promise) {
  let tracked
  tracked = Promise.resolve(promise)
    .catch(() => undefined)
    .finally(() => activeAuthTransitions.delete(tracked))
  activeAuthTransitions.add(tracked)
}

export function beginAuthRefresh() {
  let finish
  let finished = false
  const pending = new Promise((resolve) => {
    finish = resolve
  })
  registerTransition(pending)

  return () => {
    if (finished) return
    finished = true
    finish()
  }
}

export function trackAuthLogout(request) {
  const promise = Promise.resolve(request)
  registerTransition(promise)
  return promise
}

export function trackAuthRefresh(request) {
  const promise = Promise.resolve(request)
  registerTransition(promise)
  return promise
}

export async function waitForAuthTransitions() {
  while (activeAuthTransitions.size > 0) {
    await Promise.all([...activeAuthTransitions])
  }
}
