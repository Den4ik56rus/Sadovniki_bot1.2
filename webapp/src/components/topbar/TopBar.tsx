/**
 * TopBar - Верхняя панель навигации
 * Стиль Samsung Calendar: месяц + стрелка, поиск, число сегодня
 */

import { format, getDate } from 'date-fns';
import { ru } from 'date-fns/locale';
import { useCalendarStore } from '@store/calendarStore';
import { useUIStore } from '@store/uiStore';
import { useTelegramHaptic } from '@hooks/useTelegramHaptic';
import styles from './TopBar.module.css';

export function TopBar() {
  const { currentDate, goToToday } = useCalendarStore();
  const { isCalendarExpanded, toggleCalendar, openSideMenu, openSearch } = useUIStore();
  const { light } = useTelegramHaptic();

  const handleMenuClick = () => {
    light();
    openSideMenu();
  };

  const handleMonthClick = () => {
    light();
    toggleCalendar();
  };

  const handleSearchClick = () => {
    light();
    openSearch();
  };

  const handleTodayClick = () => {
    light();
    goToToday();
  };

  // Форматируем только месяц на русском
  const monthName = format(currentDate, 'LLLL', { locale: ru });
  const formattedMonth = monthName.charAt(0).toUpperCase() + monthName.slice(1);

  // Сегодняшнее число
  const todayNumber = getDate(new Date());

  return (
    <header className={styles.topbar}>
      {/* Левая часть: меню + месяц */}
      <div className={styles.leftSection}>
        <button
          className={styles.menuButton}
          onClick={handleMenuClick}
          aria-label="Открыть меню"
        >
          <MenuIcon />
        </button>

        <button
          className={styles.monthPill}
          onClick={handleMonthClick}
          aria-label={isCalendarExpanded ? 'Скрыть календарь' : 'Показать календарь'}
        >
          <span className={styles.monthText}>{formattedMonth}</span>
          <span className={`${styles.chevron} ${isCalendarExpanded ? styles.chevronUp : ''}`}>
            <ChevronDownIcon />
          </span>
        </button>
      </div>

      {/* Правая часть: поиск + сегодня */}
      <div className={styles.rightSection}>
        <button
          className={styles.searchButton}
          onClick={handleSearchClick}
          aria-label="Поиск событий"
        >
          <SearchIcon />
        </button>

        <button
          className={styles.todayNumber}
          onClick={handleTodayClick}
          aria-label="Перейти к сегодня"
        >
          {todayNumber}
        </button>
      </div>
    </header>
  );
}

// Inline SVG icons
function MenuIcon() {
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <line x1="3" y1="6" x2="21" y2="6" />
      <line x1="3" y1="12" x2="21" y2="12" />
      <line x1="3" y1="18" x2="21" y2="18" />
    </svg>
  );
}

function ChevronDownIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
      <polyline points="6,9 12,15 18,9" />
    </svg>
  );
}

function SearchIcon() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <circle cx="11" cy="11" r="8" />
      <line x1="21" y1="21" x2="16.65" y2="16.65" />
    </svg>
  );
}
