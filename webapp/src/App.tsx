/**
 * App - Root component
 * Инициализирует Telegram WebApp и рендерит основной layout
 */

import { useEffect } from 'react';
import { useTelegram } from '@hooks/useTelegram';
import { useTelegramTheme } from '@hooks/useTelegramTheme';
import { useUIStore } from '@store/uiStore';
import { CalendarLayout } from '@components/layout';
import { SideMenu } from '@components/menu';
import { EventDetailsSheet } from '@components/sheets';
import { EventForm } from '@components/forms';
import styles from './App.module.css';

function App() {
  // Инициализация Telegram WebApp
  useTelegram();

  // Синхронизация темы с Telegram
  useTelegramTheme();

  // UI state
  const theme = useUIStore((state) => state.theme);

  // Применяем тему к document
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
  }, [theme]);

  return (
    <div className={styles.app} data-theme={theme}>
      <CalendarLayout />
      <SideMenu />
      <EventDetailsSheet />
      <EventForm />
    </div>
  );
}

export default App;
