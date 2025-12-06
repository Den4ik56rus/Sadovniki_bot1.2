/**
 * useTelegramBackButton - Управление кнопкой "Назад" в Telegram
 */

import { useEffect, useCallback } from 'react';

/**
 * Хук для управления Telegram BackButton
 * @param onBack - Callback при нажатии на кнопку "Назад"
 * @param enabled - Показывать ли кнопку
 */
export function useTelegramBackButton(
  onBack: () => void,
  enabled: boolean
) {
  // Мемоизируем callback
  const handleBack = useCallback(() => {
    onBack();
  }, [onBack]);

  useEffect(() => {
    const tg = window.Telegram?.WebApp;
    if (!tg) return;

    if (enabled) {
      tg.BackButton.show();
      tg.BackButton.onClick(handleBack);
    } else {
      tg.BackButton.hide();
    }

    return () => {
      tg.BackButton.offClick(handleBack);
    };
  }, [handleBack, enabled]);
}

/**
 * Показать кнопку "Назад"
 */
export function showBackButton() {
  window.Telegram?.WebApp?.BackButton.show();
}

/**
 * Скрыть кнопку "Назад"
 */
export function hideBackButton() {
  window.Telegram?.WebApp?.BackButton.hide();
}
