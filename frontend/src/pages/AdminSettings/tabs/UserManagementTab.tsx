import { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { api } from '../../../api'
import type { UserInfo } from '../../../types'

function formatRelativeTime(dateStr: string): string {
  const date = new Date(dateStr)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMin = Math.floor(diffMs / 60000)

  if (diffMin < 1) return '刚刚'
  if (diffMin < 60) return `${diffMin} 分钟前`
  const diffHour = Math.floor(diffMin / 60)
  if (diffHour < 24) return `${diffHour} 小时前`
  const diffDay = Math.floor(diffHour / 24)
  if (diffDay < 7) return `${diffDay} 天前`
  return date.toLocaleDateString('zh-CN', {
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit',
  })
}

export function UserManagementTab() {
  const { t } = useTranslation()
  const [users, setUsers] = useState<UserInfo[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.getUsers().then(setUsers).finally(() => setLoading(false))
  }, [])

  const handleRoleChange = async (u: UserInfo, role: string) => {
    await api.updateUser(u.id, { role })
    setUsers(users.map(user => user.id === u.id ? { ...user, role: role as 'admin' | 'user' } : user))
  }

  const handleToggleActive = async (u: UserInfo) => {
    await api.updateUser(u.id, { is_active: !u.is_active })
    setUsers(users.map(user => user.id === u.id ? { ...user, is_active: !user.is_active } : user))
  }

  const handleDelete = async (u: UserInfo) => {
    if (!confirm(t('userManagement.confirmDeleteUser', { username: u.username }))) return
    await api.deleteUser(u.id)
    setUsers(users.filter(user => user.id !== u.id))
  }

  if (loading) return <div className="py-12 text-center text-ink-lighter font-kai">{t('common.loading')}</div>

  return (
    <div className="w-full animate-in fade-in slide-in-from-bottom-2 duration-300">
      <div className="flex items-center justify-between mb-8 border-b border-tea pb-4">
        <div>
          <h3 className="text-xl font-song font-bold text-ink">{t('userManagement.title')}</h3>
          <p className="text-xs text-ink-lighter font-kai mt-1">{t('userManagement.subtitle')}</p>
        </div>
      </div>

      <div className="bg-white rounded-sm ink-border shadow-sm overflow-hidden w-full">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-smoke/50 text-left text-xs text-ink-lighter font-kai uppercase tracking-wider">
              <th className="px-6 py-4 font-bold">{t('userManagement.colUserInfo')}</th>
              <th className="px-6 py-4 font-bold">{t('userManagement.colRole')}</th>
              <th className="px-6 py-4 font-bold">{t('userManagement.colStatus')}</th>
              <th className="px-6 py-4 font-bold">{t('userManagement.colLastLogin')}</th>
              <th className="px-6 py-4 font-bold">{t('userManagement.colRegistered')}</th>
              <th className="px-6 py-4 font-bold text-right">{t('userManagement.colActions')}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-tea/20">
            {users.map(u => (
              <tr key={u.id} className="hover:bg-smoke/30 transition-colors">
                <td className="px-6 py-4">
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-full bg-celadon/10 flex items-center justify-center text-celadon-dark font-bold text-xs">
                      {u.username[0].toUpperCase()}
                    </div>
                    <span className="font-medium text-ink">{u.username}</span>
                  </div>
                </td>
                <td className="px-6 py-4">
                  <select
                    value={u.role}
                    onChange={e => handleRoleChange(u, e.target.value)}
                    className="bg-paper-light border border-tea/50 rounded px-2 py-1 text-xs focus:border-celadon outline-none transition-colors"
                  >
                    <option value="user">{t('userManagement.roleUser')}</option>
                    <option value="admin">{t('userManagement.roleAdmin')}</option>
                  </select>
                </td>
                <td className="px-6 py-4">
                  <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold ${
                    u.is_active ? 'bg-celadon/10 text-celadon-dark' : 'bg-cinnabar/10 text-cinnabar'
                  }`}>
                    {u.is_active ? t('userManagement.statusActive') : t('userManagement.statusDisabled')}
                  </span>
                </td>
                <td className="px-6 py-4 text-xs font-kai">
                  {u.last_login_at ? (
                    formatRelativeTime(u.last_login_at)
                  ) : (
                    <span className="text-ink-lighter italic">{t('userManagement.neverLoggedIn')}</span>
                  )}
                </td>
                <td className="px-6 py-4 text-xs text-ink-lighter font-kai">
                  {u.created_at ? new Date(u.created_at).toLocaleDateString() : '-'}
                </td>
                <td className="px-6 py-4 text-right">
                  <div className="flex justify-end gap-3">
                    <button onClick={() => handleToggleActive(u)} className="text-xs text-celadon-dark hover:underline font-kai">
                      {u.is_active ? t('common.disable') : t('common.enable')}
                    </button>
                    <button onClick={() => handleDelete(u)} className="text-xs text-cinnabar hover:underline font-kai">
                      {t('common.delete')}
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
