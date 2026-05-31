/**
 * 状态管理入口文件
 * 
 * 架构说明:
 * 为了提高组件性能并减少不必要的重渲染，全局状态已拆分为多个专门的 Store。
 * 建议按需订阅特定的 Store，而不是使用原来的单体 useStore。
 */

export { useSessionStore } from './sessionStore'
export { useConfigStore } from './configStore'
export { useUIStore } from './uiStore'
export { useAuthStore } from './authStore'

/**
 * @deprecated 请使用专门的 useSessionStore, useConfigStore, useUIStore 或 useAuthStore。
 * 为了向后兼容，暂时保留 useStore 接口，但内部已不再维护。
 */
export const useStore = () => {
  throw new Error('useStore 已弃用，请使用专门的 Store (useSessionStore, useConfigStore, useUIStore, useAuthStore)')
}
