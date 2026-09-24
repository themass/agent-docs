import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import { ChatApp } from '../../chat/ChatApp'
import { I18nProvider } from '../../i18n'
import { bootstrapDocumentLang } from '../../i18n/locales'
import { guardDocumentLang } from '../../lib/ime-safe-surface'
import '../../styles/global.css'

guardDocumentLang()
bootstrapDocumentLang()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <I18nProvider>
      <ChatApp variant="wide" />
    </I18nProvider>
  </StrictMode>
)
