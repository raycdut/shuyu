import { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { api } from '../../../api'
import type { UserInfo } from '../../../types'
import { PageHeader, LoadingState } from '../../../components/AdminSettings/Common'
import { DataTable } from '../../../components/DataTable'
import type { Column } from '../../../components/DataTable'

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

  const columns: Column<UserInfo>[] = [
    {
      key: 'username',
      header: t('userManagement.colUserInfo'),
      render: (_, u) => (
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-full bg-celadon/10 flex items-center justify-center text-celadon-dark font-bold text-xs">
            {u.username[0].toUpperCase()}
          </div>
          <span className="font-medium text-ink">{u.username}</span>
        </div>
      ),
    },
    {
      key: 'role',
      header: t('userManagement.colRole'),
      render: (_, u) => (
        <select
          value={u.role}
          onChange={e => handleRoleChange(u, e.target.value)}
          className="bg-paper-light border border-tea/50 rounded px-2 py-1 text-xs focus:border-celadon outline-none transition-colors"
        >
          <option value="user">{t('userManagement.roleUser')}</option>
          <option value="admin">{t('userManagement.roleAdmin')}</option>
        </select>
      ),
    },
    {
      key: 'is_active',
      header: t('userManagement.colStatus'),
      render: (v) => (
        <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold ${
          v ? 'bg-celadon/10 text-celadon-dark' : 'bg-cinnabar/10 text-cinnabar'
        }`}>
          {v ? t('userManagement.statusActive') : t('userManagement.statusDisabled')}
        </span>
      ),
    },
    {
      key: 'last_login_at',
      header: t('userManagement.colLastLogin'),
      className: 'text-xs font-kai',
      render: (v) => v ? formatRelativeTime(v) : <span className="text-ink-lighter italic">{t('userManagement.neverLoggedIn')}</span>,
    },
    {
      key: 'created_at',
      header: t('userManagement.colRegistered'),
      className: 'text-xs text-ink-lighter font-kai',
      render: (v) => v ? new Date(v).toLocaleDateString() : '-',
    },
    {
      key: 'id',
      header: t('userManagement.colActions'),
      className: 'text-right',
      render: (_, u) => (
        <div className="flex justify-end gap-3">
          <button onClick={() => handleToggleActive(u)} className="text-xs text-celadon-dark hover:underline font-kai">
            {u.is_active ? t('common.disable') : t('common.enable')}
          </button>
          <button onClick={() => handleDelete(u)} className="text-xs text-cinnabar hover:underline font-kai">
            {t('common.delete')}
          </button>
        </div>
      ),
    },
  ]

  if (loading) return <LoadingState />

  return (
    <div className="w-full animate-in fade-in slide-in-from-bottom-2 duration-300">
      <PageHeader title={t('userManagement.title')} subtitle={t('userManagement.subtitle')} />
      <DataTable columns={columns} data={users} rowKey={u => u.id} />
    </div>
  )
}
