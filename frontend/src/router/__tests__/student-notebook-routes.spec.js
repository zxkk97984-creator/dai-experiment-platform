import { describe, expect, it } from 'vitest'
import router from '../index.js'

describe('student notebook routes', () => {
  it.each([
    'StudentNotebook',
    'StudentExperimentDetail',
  ])('keeps %s restricted to students', (name) => {
    const route = router.getRoutes().find(candidate => candidate.name === name)

    expect(route).toBeDefined()
    expect(route.meta.role).toBe('student')
  })

  it('provides a dedicated developer template route', () => {
    const route = router.getRoutes().find(
      candidate => candidate.name === 'DeveloperTemplates',
    )

    expect(route).toBeDefined()
    expect(route.path).toBe('/developer/templates')
    expect(route.meta.role).toBe('developer')
  })
})
