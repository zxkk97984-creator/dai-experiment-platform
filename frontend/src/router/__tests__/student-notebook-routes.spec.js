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
})
