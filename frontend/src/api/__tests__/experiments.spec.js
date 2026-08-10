import { beforeEach, describe, expect, it, vi } from 'vitest'

const client = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  put: vi.fn(),
  patch: vi.fn(),
}))

vi.mock('../client.js', () => ({ default: client }))

import { experimentsAPI } from '../experiments.js'

describe('experimentsAPI module mutations', () => {
  beforeEach(() => {
    vi.resetAllMocks()
  })

  it('creates a module with POST', () => {
    const payload = { name: 'Independent Lab', status: 'draft' }

    experimentsAPI.createModule(payload)

    expect(client.post).toHaveBeenCalledWith('/experiments/modules', payload)
  })

  it('queries the student catalog with server-side controls', () => {
    const params = { q: 'Python', status: 'started', sort: 'recent_desc', page: 2, page_size: 10 }

    experimentsAPI.listStudentCatalog(params)

    expect(client.get).toHaveBeenCalledWith(
      '/experiments/modules/student-catalog',
      { params },
    )
  })

  it('publishes or edits an existing module with PATCH', () => {
    experimentsAPI.updateModule(12, { status: 'published' })

    expect(client.patch).toHaveBeenCalledWith(
      '/experiments/modules/12',
      { status: 'published' },
    )
    expect(client.post).not.toHaveBeenCalled()
  })
})
