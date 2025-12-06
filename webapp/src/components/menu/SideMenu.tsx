/**
 * SideMenu - Боковое меню
 * Slide-in меню с навигацией и настройками
 */

import { useUIStore } from '@store/uiStore';
import { useTelegramBackButton } from '@hooks/useTelegramBackButton';
import { useTelegramHaptic } from '@hooks/useTelegramHaptic';
import { UI_TEXT } from '@constants/ui';
import styles from './SideMenu.module.css';

export function SideMenu() {
  const { isSideMenuOpen, closeSideMenu } = useUIStore();
  const { light } = useTelegramHaptic();

  // BackButton закрывает меню
  useTelegramBackButton(closeSideMenu, isSideMenuOpen);

  const handleClose = () => {
    light();
    closeSideMenu();
  };

  if (!isSideMenuOpen) return null;

  return (
    <div className={styles.overlay} onClick={handleClose}>
      <nav
        className={styles.menu}
        onClick={(e) => e.stopPropagation()}
      >
        <div className={styles.header}>
          <h2 className={styles.title}>Садовники</h2>
        </div>

        <ul className={styles.list}>
          <li>
            <button className={`${styles.item} ${styles.active}`}>
              <CalendarIcon />
              <span>{UI_TEXT.menuCalendar}</span>
            </button>
          </li>
          <li>
            <button className={styles.item} disabled>
              <SettingsIcon />
              <span>{UI_TEXT.menuSettings}</span>
            </button>
          </li>
          <li>
            <button className={styles.item} disabled>
              <InfoIcon />
              <span>{UI_TEXT.menuAbout}</span>
            </button>
          </li>
        </ul>

        <div className={styles.footer}>
          <span className={styles.version}>v1.0.0</span>
        </div>
      </nav>
    </div>
  );
}

// Inline SVG icons
function CalendarIcon() {
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
      <line x1="16" y1="2" x2="16" y2="6" />
      <line x1="8" y1="2" x2="8" y2="6" />
      <line x1="3" y1="10" x2="21" y2="10" />
    </svg>
  );
}

function SettingsIcon() {
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
    </svg>
  );
}

function InfoIcon() {
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <circle cx="12" cy="12" r="10" />
      <line x1="12" y1="16" x2="12" y2="12" />
      <line x1="12" y1="8" x2="12.01" y2="8" />
    </svg>
  );
}
