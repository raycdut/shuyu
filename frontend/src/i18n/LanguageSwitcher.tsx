import { useTranslation } from 'react-i18next'

export default function LanguageSwitcher() {
  const { i18n } = useTranslation()
  const currentLang = i18n.language

  const toggleLanguage = () => {
    const newLang = currentLang.startsWith('en') ? 'zh-CN' : 'en-US'
    i18n.changeLanguage(newLang)
    localStorage.setItem('app-language', newLang)
  }

  return (
    <button
      onClick={toggleLanguage}
      className="text-xs px-2 py-1 rounded-sm border border-tea text-ink-lighter hover:text-ink hover:border-ink/20 transition-colors font-kai"
      title={currentLang.startsWith('en') ? '切换中文' : 'Switch to English'}
      aria-label={currentLang.startsWith('en') ? '切换中文' : 'Switch to English'}
    >
      {currentLang.startsWith('en') ? '中' : 'EN'}
    </button>
  )
}
