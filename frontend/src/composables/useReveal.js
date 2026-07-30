import { ref, onMounted, onUnmounted } from 'vue'

/**
 * One-shot viewport reveal composable.
 * Returns `isVisible` that becomes true once the element enters the viewport
 * and never resets. Falls back to always-visible when IntersectionObserver is
 * unavailable.
 *
 * @param {{ threshold?: number, rootMargin?: string }} options
 * @returns {{ isVisible: import('vue').Ref<boolean>, elRef: import('vue').Ref<HTMLElement | null> }}
 */
export function useReveal(options = {}) {
  const { threshold = 0.12, rootMargin = '0px 0px -40px 0px' } = options

  const isVisible = ref(false)
  const elRef = ref(null)

  let observer = null

  onMounted(() => {
    if (typeof IntersectionObserver === 'undefined') {
      // Static fallback — show everything immediately
      isVisible.value = true
      return
    }

    observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            isVisible.value = true
            observer.unobserve(entry.target)
          }
        }
      },
      { threshold, rootMargin },
    )

    if (elRef.value) {
      observer.observe(elRef.value)
    }
  })

  onUnmounted(() => {
    if (observer) {
      observer.disconnect()
    }
  })

  return { isVisible, elRef }
}
