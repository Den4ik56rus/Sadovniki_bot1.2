/**
 * CalendarLayout - Основной layout календаря
 * Организует TopBar, MonthGrid/WorksList и DayEventsPanel
 */

import { TopBar } from '@components/topbar';
import { MonthGrid } from '@components/calendar';
import { DayEventsPanel } from '@components/events';
import { WorksList } from '@components/worksList';
import { useUIStore } from '@store/uiStore';
import styles from './CalendarLayout.module.css';

export function CalendarLayout() {
  const isCalendarExpanded = useUIStore((state) => state.isCalendarExpanded);

  return (
    <div className={styles.layout}>
      <TopBar />
      <main className={styles.main}>
        {isCalendarExpanded ? (
          <>
            <MonthGrid />
            <DayEventsPanel />
          </>
        ) : (
          <WorksList />
        )}
      </main>
    </div>
  );
}
