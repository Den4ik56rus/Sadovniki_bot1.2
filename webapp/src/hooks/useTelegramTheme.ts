/**
 * useTelegramTheme - Синхронизация темы с Telegram
 */

import { useEffect } from 'react';
import { useUIStore } from '@/store';
import type { Theme } from '@/types';

/**
 * Хук для синхронизации темы с Telegram WebApp
 */
export function useTelegramTheme() {
  const theme = useUIStore((state) => state.theme);
  const setTheme = useUIStore((state) => state.setTheme);

  useEffect(() => {
    const tg = window.Telegram?.WebApp;
    if (!tg) return;

    // Обработчик смены темы в Telegram
    const handleThemeChanged = () => {
      const newTheme = tg.colorScheme as Theme;
      setTheme(newTheme);
    };

    // Подписываемся на событие смены темы
    tg.onEvent('themeChanged', handleThemeChanged);

    return () => {
      tg.offEvent('themeChanged', handleThemeChanged);
    };
  }, [setTheme]);

  // Применяем CSS-переменные из Telegram
  useEffect(() => {
    const tg = window.Telegram?.WebApp;
    const root = document.documentElement;

    // Устанавливаем атрибут темы
    root.setAttribute('data-theme', theme);

    // Если есть Telegram, используем его цвета
    if (tg?.themeParams) {
      const { themeParams } = tg;

      if (themeParams.bg_color) {
        root.style.setProperty('--tg-bg', themeParams.bg_color);
      }
      if (themeParams.text_color) {
        root.style.setProperty('--tg-text', themeParams.text_color);
      }
      if (themeParams.hint_color) {
        root.style.setProperty('--tg-hint', themeParams.hint_color);
      }
      if (themeParams.link_color) {
        root.style.setProperty('--tg-link', themeParams.link_color);
      }
      if (themeParams.button_color) {
        root.style.setProperty('--tg-button', themeParams.button_color);
      }
      if (themeParams.button_text_color) {
        root.style.setProperty('--tg-button-text', themeParams.button_text_color);
      }
      if (themeParams.secondary_bg_color) {
        root.style.setProperty('--tg-secondary-bg', themeParams.secondary_bg_color);
      }
    }
  }, [theme]);

  return theme;
}
