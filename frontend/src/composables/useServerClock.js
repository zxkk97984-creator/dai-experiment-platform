import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

/**
 * A monotonic clock anchored to a timestamp returned by the API. Local wall
 * clock changes never affect exam eligibility or countdowns.
 */
export function useServerClock(onResync) {
  const serverAnchor = ref(0)
  const monotonicAnchor = ref(0)
  const tick = ref(0)
  let ticker = null
  let calibrator = null
  let syncing = false

  const nowMs = computed(() => {
    tick.value
    if (!serverAnchor.value) return 0
    return serverAnchor.value + (performance.now() - monotonicAnchor.value)
  })

  function calibrate(serverNow) {
    const parsed = new Date(serverNow).getTime()
    if (!Number.isFinite(parsed)) return
    serverAnchor.value = parsed
    monotonicAnchor.value = performance.now()
    tick.value += 1
  }

  async function resync() {
    if (!onResync || syncing) return
    syncing = true
    try {
      const serverNow = await onResync()
      if (serverNow) calibrate(serverNow)
    } catch {
      // Keep advancing from the last trusted server anchor while offline. The
      // next focus/online/30-second calibration will repair any network drift.
    } finally {
      syncing = false
    }
  }

  function onFocus() { resync() }
  function onOnline() { resync() }

  onMounted(() => {
    ticker = window.setInterval(() => { tick.value += 1 }, 250)
    calibrator = window.setInterval(resync, 30_000)
    window.addEventListener('focus', onFocus)
    window.addEventListener('online', onOnline)
  })

  onBeforeUnmount(() => {
    window.clearInterval(ticker)
    window.clearInterval(calibrator)
    window.removeEventListener('focus', onFocus)
    window.removeEventListener('online', onOnline)
  })

  return { nowMs, calibrate, resync }
}
