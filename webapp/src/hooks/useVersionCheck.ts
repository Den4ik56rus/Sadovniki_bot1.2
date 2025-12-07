/**
 * useVersionCheck - Проверка версии приложения
 * Сравнивает текущую версию с версией на сервере
 */

import { useState, useEffect, useCallback } from 'react';

// Текущая версия из package.json (инжектится при сборке)
const CURRENT_VERSION = __APP_VERSION__;

interface VersionCheckResult {
  hasUpdate: boolean;
  currentVersion: string;
  latestVersion: string | null;
  isChecking: boolean;
  forceRefresh: () => void;
}

export function useVersionCheck(): VersionCheckResult {
  const [latestVersion, setLatestVersion] = useState<string | null>(null);
  const [isChecking, setIsChecking] = useState(true);

  const checkVersion = useCallback(async () => {
    try {
      // Добавляем timestamp чтобы обойти кэш
      const response = await fetch(`/Sadovniki_bot1.2/version.json?t=${Date.now()}`, {
        cache: 'no-store',
        headers: {
          'Cache-Control': 'no-cache',
        },
      });

      if (response.ok) {
        const data = await response.json();
        setLatestVersion(data.version);
      }
    } catch (error) {
      console.warn('Failed to check version:', error);
    } finally {
      setIsChecking(false);
    }
  }, []);

  useEffect(() => {
    checkVersion();

    // Проверяем версию каждые 5 минут
    const interval = setInterval(checkVersion, 5 * 60 * 1000);
    return () => clearInterval(interval);
  }, [checkVersion]);

  const forceRefresh = useCallback(() => {
    // Очищаем кэш и перезагружаем
    if ('caches' in window) {
      caches.keys().then((names) => {
        names.forEach((name) => caches.delete(name));
      });
    }

    // Перезагружаем с очисткой кэша
    window.location.href = window.location.href.split('?')[0] + '?v=' + Date.now();
  }, []);

  const hasUpdate = !isChecking && latestVersion !== null && latestVersion !== CURRENT_VERSION;

  return {
    hasUpdate,
    currentVersion: CURRENT_VERSION,
    latestVersion,
    isChecking,
    forceRefresh,
  };
}

// Глобальная переменная для TypeScript
declare const __APP_VERSION__: string;
