import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './index.css'
import { useAppStore } from '@/store/useAppStore'
import { setLang } from '@/lib/i18n'

// Sync <html> class with persisted theme/language so styling reacts instantly.
function ThemeSync() {
  const theme = useAppStore((s) => s.settings.theme)
  const language = useAppStore((s) => s.settings.language)
  React.useEffect(() => {
    const root = document.documentElement
    root.classList.toggle('dark', theme === 'dark')
    root.classList.toggle('light', theme === 'light')
    root.setAttribute('lang', language)
    setLang(language)
  }, [theme, language])
  return null
}

const boot = document.getElementById('boot')
if (boot) boot.remove()

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ThemeSync />
    <App />
  </React.StrictMode>,
)
