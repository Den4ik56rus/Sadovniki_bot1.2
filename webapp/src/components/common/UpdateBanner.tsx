/**
 * UpdateBanner - Баннер обновления приложения
 */

import { useVersionCheck } from '@hooks/useVersionCheck';
import styles from './UpdateBanner.module.css';

export function UpdateBanner() {
  const { hasUpdate, latestVersion, forceRefresh } = useVersionCheck();

  if (!hasUpdate) return null;

  return (
    <div className={styles.banner}>
      <div className={styles.content}>
        <span className={styles.text}>
          Доступна новая версия ({latestVersion})
        </span>
        <button className={styles.button} onClick={forceRefresh}>
          Обновить
        </button>
      </div>
    </div>
  );
}
