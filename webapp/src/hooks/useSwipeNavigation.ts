/**
 * useSwipeNavigation - Хук для свайп-навигации между месяцами
 */

import { useRef, useCallback } from 'react';

interface SwipeOptions {
  onSwipeLeft: () => void;
  onSwipeRight: () => void;
  threshold?: number;  // Минимальное расстояние свайпа (px)
  enabled?: boolean;
}

interface SwipeHandlers {
  onTouchStart: (e: React.TouchEvent) => void;
  onTouchMove: (e: React.TouchEvent) => void;
  onTouchEnd: (e: React.TouchEvent) => void;
}

export function useSwipeNavigation({
  onSwipeLeft,
  onSwipeRight,
  threshold = 50,
  enabled = true,
}: SwipeOptions): SwipeHandlers {
  const touchStartX = useRef<number | null>(null);
  const touchStartY = useRef<number | null>(null);
  const touchEndX = useRef<number | null>(null);
  const isSwiping = useRef(false);

  const onTouchStart = useCallback((e: React.TouchEvent) => {
    if (!enabled) return;

    touchStartX.current = e.touches[0].clientX;
    touchStartY.current = e.touches[0].clientY;
    touchEndX.current = null;
    isSwiping.current = false;
  }, [enabled]);

  const onTouchMove = useCallback((e: React.TouchEvent) => {
    if (!enabled || touchStartX.current === null || touchStartY.current === null) return;

    const currentX = e.touches[0].clientX;
    const currentY = e.touches[0].clientY;

    const diffX = Math.abs(currentX - touchStartX.current);
    const diffY = Math.abs(currentY - touchStartY.current);

    // Определяем, что это горизонтальный свайп
    if (diffX > diffY && diffX > 10) {
      isSwiping.current = true;
    }

    touchEndX.current = currentX;
  }, [enabled]);

  const onTouchEnd = useCallback(() => {
    if (!enabled || touchStartX.current === null || touchEndX.current === null) {
      touchStartX.current = null;
      touchStartY.current = null;
      touchEndX.current = null;
      isSwiping.current = false;
      return;
    }

    if (!isSwiping.current) {
      touchStartX.current = null;
      touchStartY.current = null;
      touchEndX.current = null;
      isSwiping.current = false;
      return;
    }

    const diff = touchStartX.current - touchEndX.current;

    if (Math.abs(diff) > threshold) {
      if (diff > 0) {
        // Свайп влево → следующий месяц
        onSwipeLeft();
      } else {
        // Свайп вправо → предыдущий месяц
        onSwipeRight();
      }
    }

    touchStartX.current = null;
    touchStartY.current = null;
    touchEndX.current = null;
    isSwiping.current = false;
  }, [enabled, threshold, onSwipeLeft, onSwipeRight]);

  return {
    onTouchStart,
    onTouchMove,
    onTouchEnd,
  };
}
