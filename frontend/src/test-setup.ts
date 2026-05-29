import '@testing-library/jest-dom'
import { vi } from 'vitest'

// jsdom 没有 scrollIntoView 实现
Element.prototype.scrollIntoView = vi.fn() as any
