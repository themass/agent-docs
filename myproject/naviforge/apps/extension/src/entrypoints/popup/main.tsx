import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import { I18nProvider } from '../../i18n'
import { PopupApp } from './PopupApp'
import '../../styles/global.css'

document.documentElement.classList.add('nf-popup-html')
document.body.classList.add('nf-popup-body')

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <I18nProvider>
      <PopupApp />
    </I18nProvider>
  </StrictMode>
)
