import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import zh from './locales/zh.json'
import en from './locales/en.json'

// Safely get language from localStorage
const getLanguage = (): string => {
  if (typeof window === 'undefined') return 'zh'
  try {
    const lang = localStorage.getItem('language')
    return lang === 'en' || lang === 'zh' ? lang : 'zh'
  } catch {
    return 'zh'
  }
}

// 初始化 i18n
const initPromise = i18n
  .use(initReactI18next)
  .init({
    resources: {
      zh: { translation: zh },
      en: { translation: en },
    },
    lng: getLanguage(),
    fallbackLng: 'zh',
    interpolation: {
      escapeValue: false,
    },
    react: {
      useSuspense: false,
    },
    // 如果找不到翻译键，返回键本身而不是空字符串
    returnEmptyString: false,
    returnNull: false,
  })

// 导出初始化 Promise，供 main.tsx 使用
export { initPromise }
export default i18n

