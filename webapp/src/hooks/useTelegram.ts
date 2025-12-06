/**
 * useTelegram - Инициализация Telegram WebApp
 */

import { useEffect } from 'react';
import { useUIStore } from '@/store';

/**
 * Основной хук инициализации Telegram WebApp
 */
export function useTelegram() {
  const setTheme = useUIStore((state) => state.setTheme);

  useEffect(() => {
    const tg = window.Telegram?.WebApp;
    if (!tg) {
      console.log('[Telegram] WebApp not available, running in browser mode');
      return;
    }

    // Сообщаем Telegram, что приложение готово
    tg.ready();

    // Расширяем на весь экран
    tg.expand();

    // Устанавливаем начальную тему
    setTheme(tg.colorScheme || 'light');

    // Скрываем MainButton по умолчанию
    tg.MainButton.hide();

    console.log('[Telegram] WebApp initialized', {
      version: tg.version,
      platform: tg.platform,
      colorScheme: tg.colorScheme,
    });
  }, [setTheme]);
}

/**
 * Получить объект Telegram WebApp
 */
export function getTelegram() {
  return window.Telegram?.WebApp;
}

/**
 * Проверка, запущено ли в Telegram
 */
export function isTelegramWebApp(): boolean {
  return !!window.Telegram?.WebApp;
}
