/**
 * useEventsSync - Хук для автоматической синхронизации событий
 *
 * Загружает события с сервера при открытии WebApp в Telegram
 */

import { useEffect } from 'react';
import { useEventsStore } from '@store/eventsStore';
import { api } from '@services/api';

export function useEventsSync() {
  const fetchEvents = useEventsStore((state) => state.fetchEvents);
  const isSynced = useEventsStore((state) => state.isSynced);
  const isLoading = useEventsStore((state) => state.isLoading);

  useEffect(() => {
    // Синхронизируем только если:
    // 1. Мы в Telegram WebApp
    // 2. API настроен
    // 3. Ещё не синхронизировались
    // 4. Не в процессе загрузки
    if (
      api.isTelegramWebApp() &&
      api.isApiConfigured() &&
      !isSynced &&
      !isLoading
    ) {
      fetchEvents();
    }
  }, [fetchEvents, isSynced, isLoading]);

  return { isSynced, isLoading };
}
