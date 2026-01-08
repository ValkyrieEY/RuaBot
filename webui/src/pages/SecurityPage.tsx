import { useTranslation } from 'react-i18next'
import { Users, Key, UserCheck } from 'lucide-react'

export default function SecurityPage() {
  const { t } = useTranslation()

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-gray-900">{t('security.title')}</h1>
        <p className="text-gray-600 mt-1">{t('security.description')}</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="card hover:shadow-md transition-shadow cursor-pointer">
          <div className="flex items-center gap-3 mb-4">
            <Users className="w-6 h-6 text-primary-600" />
            <h2 className="text-lg font-semibold text-gray-900">{t('security.users')}</h2>
          </div>
          <p className="text-gray-600 text-sm">{t('security.usersDesc')}</p>
        </div>

        <div className="card hover:shadow-md transition-shadow cursor-pointer">
          <div className="flex items-center gap-3 mb-4">
            <Key className="w-6 h-6 text-primary-600" />
            <h2 className="text-lg font-semibold text-gray-900">{t('security.permissions')}</h2>
          </div>
          <p className="text-gray-600 text-sm">{t('security.permissionsDesc')}</p>
        </div>

        <div className="card hover:shadow-md transition-shadow cursor-pointer">
          <div className="flex items-center gap-3 mb-4">
            <UserCheck className="w-6 h-6 text-primary-600" />
            <h2 className="text-lg font-semibold text-gray-900">{t('security.roles')}</h2>
          </div>
          <p className="text-gray-600 text-sm">{t('security.rolesDesc')}</p>
        </div>
      </div>

      <div className="card">
        <p className="text-gray-600">{t('security.developing')}</p>
      </div>
    </div>
  )
}

