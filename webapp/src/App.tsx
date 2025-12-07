/**
 * App - Root component
 * Инициализирует Telegram WebApp и рендерит основной layout
 */

import { useEffect } from 'react';
import { useTelegram } from '@hooks/useTelegram';
import { useTelegramTheme } from '@hooks/useTelegramTheme';
import { useEventsSync } from '@hooks/useEventsSync';
import { useUIStore } from '@store/uiStore';
import { usePlantingsStore } from '@store/plantingsStore';
import { CalendarLayout } from '@components/layout';
import { SideMenu } from '@components/menu';
import { EventDetailsSheet } from '@components/sheets';
import { EventForm } from '@components/forms';
import { PlantingsPage, PlantingForm } from '@components/plantings';
import styles from './App.module.css';

function App() {
  // Инициализация Telegram WebApp
  useTelegram();

  // Синхронизация темы с Telegram
  useTelegramTheme();

  // Синхронизация событий с сервером (только в Telegram WebApp)
  useEventsSync();

  // Загрузка посадок пользователя при старте
  const fetchPlantings = usePlantingsStore((state) => state.fetchPlantings);
  useEffect(() => {
    fetchPlantings();
  }, [fetchPlantings]);

  // UI state
  const theme = useUIStore((state) => state.theme);
  const isPlantingsPageOpen = useUIStore((state) => state.isPlantingsPageOpen);
  const isPlantingFormOpen = useUIStore((state) => state.isPlantingFormOpen);

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
      {isPlantingsPageOpen && <PlantingsPage />}
      {isPlantingFormOpen && <PlantingForm />}
    </div>
  );
}

export default App;
