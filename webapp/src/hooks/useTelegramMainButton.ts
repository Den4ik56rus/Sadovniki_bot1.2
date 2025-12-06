/**
 * useTelegramMainButton - Управление главной кнопкой Telegram
 */

import { useEffect, useRef } from 'react';

interface MainButtonOptions {
  text: string;
  onClick: () => void;
  enabled?: boolean;
  visible?: boolean;
  showProgress?: boolean;
}

/**
 * Хук для управления Telegram MainButton
 */
export function useTelegramMainButton(options: MainButtonOptions | null) {
  // Храним callback в ref чтобы избежать проблем с подпиской
  const callbackRef = useRef<(() => void) | null>(null);
  // Стабильная функция обработчика
  const handlerRef = useRef<(() => void) | null>(null);

  // Создаём стабильный обработчик один раз
  if (!handlerRef.current) {
    handlerRef.current = () => {
      callbackRef.current?.();
    };
  }

  // Обновляем ref при изменении onClick
  useEffect(() => {
    callbackRef.current = options?.onClick ?? null;
  }, [options?.onClick]);

  useEffect(() => {
    const tg = window.Telegram?.WebApp;
    if (!tg) return;

    const handler = handlerRef.current!;

    if (!options) {
      tg.MainButton.offClick(handler);
      tg.MainButton.hide();
      return;
    }

    const { text, enabled = true, visible = true, showProgress = false } = options;

    // Устанавливаем текст
    tg.MainButton.setText(text);

    // Включаем/выключаем
    if (enabled) {
      tg.MainButton.enable();
    } else {
      tg.MainButton.disable();
    }

    // Показываем/скрываем прогресс
    if (showProgress) {
      tg.MainButton.showProgress(false);
    } else {
      tg.MainButton.hideProgress();
    }

    // Показываем/скрываем кнопку
    if (visible) {
      // Сначала отписываемся, потом подписываемся (избегаем дублей)
      tg.MainButton.offClick(handler);
      tg.MainButton.onClick(handler);
      tg.MainButton.show();
    } else {
      tg.MainButton.offClick(handler);
      tg.MainButton.hide();
    }

    return () => {
      tg.MainButton.offClick(handler);
    };
  }, [options?.text, options?.enabled, options?.visible, options?.showProgress]);
}

/**
 * Показать MainButton
 */
export function showMainButton(text: string) {
  const tg = window.Telegram?.WebApp;
  if (!tg) return;

  tg.MainButton.setText(text);
  tg.MainButton.show();
}

/**
 * Скрыть MainButton
 */
export function hideMainButton() {
  window.Telegram?.WebApp?.MainButton.hide();
}
