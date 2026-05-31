import { create } from 'zustand'

/**
 * 看板条目接口
 */
export interface DashboardItem {
  id: string
  title: string
  columns: string[]
  data: any[][]
  type: 'line' | 'bar' | 'table'
  createdAt: number
}

/**
 * UI 状态管理接口
 */
interface UIState {
  /** 左侧面板是否展开 */
  leftOpen: boolean
  /** 右侧面板是否展开 */
  rightOpen: boolean
  /** 是否显示看板 */
  showDashboard: boolean
  /** 错误信息 */
  error: string | null

  /** 看板条目列表 */
  dashboardItems: DashboardItem[]

  /** 设置左侧面板展开状态 */
  setLeftOpen: (open: boolean) => void
  /** 设置右侧面板展开状态 */
  setRightOpen: (open: boolean) => void
  /** 设置看板显示状态 */
  setShowDashboard: (show: boolean) => void
  /** 设置错误信息 */
  setError: (error: string | null) => void

  /** 添加看板条目 */
  addDashboardItem: (item: DashboardItem) => void
  /** 根据 ID 移除看板条目 */
  removeDashboardItem: (id: string) => void
  /** 设置看板条目列表 */
  setDashboardItems: (items: DashboardItem[]) => void
}

/**
 * UI 状态管理 Zustand Store
 * 管理面板展开状态、错误信息和看板条目
 */
export const useUIStore = create<UIState>((set) => ({
  leftOpen: true,
  rightOpen: true,
  showDashboard: false,
  error: null,

  dashboardItems: [],

  setLeftOpen: (leftOpen) => set({ leftOpen }),
  setRightOpen: (rightOpen) => set({ rightOpen }),
  setShowDashboard: (showDashboard) => set({ showDashboard }),
  setError: (error) => set({ error }),

  addDashboardItem: (item) => set((state) => ({
    dashboardItems: [item, ...state.dashboardItems]
  })),
  removeDashboardItem: (id) => set((state) => ({
    dashboardItems: state.dashboardItems.filter(i => i.id !== id)
  })),
  setDashboardItems: (dashboardItems) => set({ dashboardItems }),
}))
