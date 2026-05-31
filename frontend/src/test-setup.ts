import '@testing-library/jest-dom'
import { vi } from 'vitest'
import './i18n'

// jsdom 没有 scrollIntoView 实现
Element.prototype.scrollIntoView = vi.fn() as any
