import React from 'react'

/**
 * 设置项容器，包含标签和子组件
 */
export function SettingSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="mb-6 w-full">
      <label className="block text-xs text-ink-lighter mb-2 font-kai tracking-wide">{title}</label>
      <div className="w-full">
        {children}
      </div>
    </div>
  )
}

/**
 * 开关行组件，用于布尔设置
 */
export function ToggleRow({ label, checked, onChange }: { label: string; checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <div 
      className="flex items-center justify-between p-3 rounded-sm hover:bg-smoke/50 transition-colors cursor-pointer border border-transparent hover:border-tea/30"
      onClick={() => onChange(!checked)}
    >
      <span className="text-sm text-ink font-kai">{label}</span>
      <button
        className={`w-10 h-5 flex items-center rounded-full p-1 transition-colors duration-200 ${
          checked ? 'bg-celadon' : 'bg-tea/30'
        }`}
      >
        <div className={`bg-white w-3 h-3 rounded-full shadow-sm transition-transform duration-200 ${checked ? 'translate-x-5' : 'translate-x-0'}`} />
      </button>
    </div>
  )
}
