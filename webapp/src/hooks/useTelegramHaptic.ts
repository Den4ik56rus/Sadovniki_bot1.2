/**
 * useTelegramHaptic - Тактильная обратная связь
 */

type ImpactStyle = 'light' | 'medium' | 'heavy' | 'rigid' | 'soft';
type NotificationType = 'error' | 'success' | 'warning';

/**
 * Вибрация при взаимодействии
 */
export function hapticImpact(style: ImpactStyle = 'light') {
  window.Telegram?.WebApp?.HapticFeedback?.impactOccurred(style);
}

/**
 * Вибрация для уведомлений
 */
export function hapticNotification(type: NotificationType) {
  window.Telegram?.WebApp?.HapticFeedback?.notificationOccurred(type);
}

/**
 * Вибрация при изменении выбора
 */
export function hapticSelection() {
  window.Telegram?.WebApp?.HapticFeedback?.selectionChanged();
}

/**
 * Хук для удобного использования haptic feedback
 */
export function useTelegramHaptic() {
  return {
    // Лёгкая вибрация (выбор дня, нажатие кнопки)
    light: () => hapticImpact('light'),

    // Средняя вибрация (открытие/закрытие модала)
    medium: () => hapticImpact('medium'),

    // Сильная вибрация (удаление)
    heavy: () => hapticImpact('heavy'),

    // Успешное действие
    success: () => hapticNotification('success'),

    // Ошибка
    error: () => hapticNotification('error'),

    // Предупреждение
    warning: () => hapticNotification('warning'),

    // Изменение выбора
    selection: () => hapticSelection(),
  };
}
