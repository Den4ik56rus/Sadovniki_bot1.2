/**
 * CalendarLayout - Основной layout календаря
 * Организует TopBar, MonthGrid и DayEventsPanel
 */

import { TopBar } from '@components/topbar';
import { MonthGrid } from '@components/calendar';
import { DayEventsPanel } from '@components/events';
import styles from './CalendarLayout.module.css';

export function CalendarLayout() {
  return (
    <div className={styles.layout}>
      <TopBar />
      <main className={styles.main}>
        <MonthGrid />
        <DayEventsPanel />
      </main>
    </div>
  );
}
