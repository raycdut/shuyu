import React from 'react'
import { useTranslation } from 'react-i18next'

interface AuthLayoutProps {
  subtitle: string
  children: React.ReactNode
  footer: React.ReactNode
}

export default function AuthLayout({ subtitle, children, footer }: AuthLayoutProps) {
  const { t } = useTranslation()
  return (
    <div className="min-h-screen flex items-center justify-center bg-paper-light">
      <div className="w-full max-w-sm mx-4">
        <div className="text-center mb-10">
          <h1 className="text-2xl font-song font-semibold text-ink tracking-wider mb-2">
            {t('app.name')}
          </h1>
          <p className="text-sm text-ink-lighter font-kai">{subtitle}</p>
        </div>

        {children}

        <p className="mt-6 text-center text-sm text-ink-lighter font-kai">
          {footer}
        </p>
      </div>
    </div>
  )
}
