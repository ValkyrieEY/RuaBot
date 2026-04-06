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

//  i18n
const initPromise = i18n
  .use(initReactI18next)
  .init({
    resources: {
      zh: { translation: zh },
      en: { translation: en },
    },
    lng: getLanguage(),
    // 中文缺键、空串（returnEmptyString: false 视为缺失）时回退到英文，否则会显示 login.xxx 原始键名
    fallbackLng: {
      zh: ['en'],
      en: ['en'],
      default: ['en'],
    },
    interpolation: {
      escapeValue: false,
    },
    react: {
      useSuspense: false,
    },
    // 
    returnEmptyString: false,
    returnNull: false,
  })

//  Promise main.tsx 
export { initPromise }
export default i18n

