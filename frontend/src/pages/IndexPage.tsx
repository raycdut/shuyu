import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useAuthStore } from '../store/authStore'
import { useConfigStore } from '../store/configStore'
import { useSessionStore } from '../store/sessionStore'

export default function IndexPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()

  const user = useAuthStore(s => s.user)
  const databases = useConfigStore(s => s.databases)
  const llmConnected = useConfigStore(s => s.llmConnected)
  const llmConfig = useConfigStore(s => s.llmConfig)
  const sessions = useSessionStore(s => s.sessions)

  const featureCards = [
    {
      key: 'chat',
      icon: (
        <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-celadon">
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
        </svg>
      ),
      title: t('index.chatTitle'),
      desc: t('index.chatDesc'),
      action: () => navigate('/chat'),
      btnLabel: t('index.startChat'),
    },
  ]

  if (user?.role === 'admin') {
    featureCards.push({
      key: 'admin',
      icon: (
        <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-celadon">
          <circle cx="12" cy="12" r="3" />
          <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
        </svg>
      ),
      title: t('index.adminTitle'),
      desc: t('index.adminDesc'),
      action: () => navigate('/admin'),
      btnLabel: t('index.goToAdmin'),
    })
  }

  const dbCount = databases.length
  const sessionCount = sessions.length

  return (
    <div className="flex-1 flex flex-col overflow-y-auto bg-paper/30">
      <div className="flex-1 flex flex-col items-center justify-center px-6 py-12 max-w-4xl mx-auto w-full">
        <div className="text-center mb-12">
          <h1 className="text-4xl font-song font-semibold text-ink tracking-wider mb-3">
            {t('app.name')}
          </h1>
          <p className="text-base text-ink-lighter font-kai">
            {t('index.tagline')}
          </p>
          <div className="mt-4 max-w-md mx-auto">
            <p className="text-sm text-ink-light/70 font-kai leading-relaxed">
              {t('index.description')}
            </p>
          </div>
        </div>

        <div className="flex flex-wrap justify-center gap-5 w-full mb-12">
          {featureCards.map(card => (
            <div
              key={card.key}
              className="bg-white rounded-sm ink-border p-6 flex flex-col items-center text-center
                paper-shadow hover:shadow-md transition-all duration-200
                group cursor-pointer w-full sm:w-72"
              onClick={card.action}
            >
              <div className="mb-4 p-3 rounded-full bg-celadon/5 group-hover:bg-celadon/10 transition-colors">
                {card.icon}
              </div>
              <h3 className="text-base font-song font-medium text-ink mb-2">
                {card.title}
              </h3>
              <p className="text-xs text-ink-lighter font-kai leading-relaxed mb-5 flex-1">
                {card.desc}
              </p>
              <button
                onClick={(e) => { e.stopPropagation(); card.action() }}
                className="btn-celadon text-xs"
              >
                {card.btnLabel}
              </button>
            </div>
          ))}
        </div>

        <div className="w-full">
          <div className="ink-divider mb-8" />
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
            <div className="text-center">
              <div className="text-2xl font-song font-semibold text-celadon">
                {dbCount}
              </div>
              <div className="text-xs text-ink-lighter font-kai mt-1">
                {t('index.statDatabases')}
              </div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-song font-semibold text-celadon">
                {llmConnected === null
                  ? t('statusBar.checking')
                  : llmConnected
                    ? t('statusBar.connected')
                    : t('statusBar.disconnected')
                }
              </div>
              <div className="text-xs text-ink-lighter font-kai mt-1">
                {t('index.statLlm')}
                {llmConfig.model && <span className="text-ink-light"> · {llmConfig.model}</span>}
              </div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-song font-semibold text-celadon">
                {sessionCount}
              </div>
              <div className="text-xs text-ink-lighter font-kai mt-1">
                {t('index.statSessions')}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
