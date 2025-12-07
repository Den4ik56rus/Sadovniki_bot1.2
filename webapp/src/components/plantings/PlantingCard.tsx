/**
 * PlantingCard - Карточка посадки
 */

import { usePlantingsStore } from '@store/plantingsStore';
import { useTelegramHaptic } from '@hooks/useTelegramHaptic';
import { getCultureIconComponent, getPlantingLabel } from '@constants/plantingCultures';
import type { UserPlanting } from '@/types';
import styles from './PlantingCard.module.css';

interface PlantingCardProps {
  planting: UserPlanting;
  onEdit: () => void;
}

export function PlantingCard({ planting, onEdit }: PlantingCardProps) {
  const { deletePlanting } = usePlantingsStore();
  const { light, success, error: hapticError } = useTelegramHaptic();

  const handleDelete = async () => {
    light();
    if (!confirm('Удалить эту культуру?')) return;

    try {
      await deletePlanting(planting.id);
      success();
    } catch {
      hapticError();
    }
  };

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return null;
    const date = new Date(dateStr);
    return date.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' });
  };

  const fruitingStart = formatDate(planting.fruitingStart);
  const fruitingEnd = formatDate(planting.fruitingEnd);
  const hasFruitingDates = fruitingStart || fruitingEnd;

  const CultureIcon = getCultureIconComponent(planting.cultureType);

  return (
    <div className={styles.card}>
      <div className={styles.icon}>
        <CultureIcon width={24} height={24} />
      </div>

      <div className={styles.info}>
        <span className={styles.name}>
          {getPlantingLabel(planting)}
        </span>
        {hasFruitingDates && (
          <span className={styles.dates}>
            Плодоношение: {fruitingStart || '?'} — {fruitingEnd || '?'}
          </span>
        )}
      </div>

      <div className={styles.actions}>
        <button
          className={styles.actionButton}
          onClick={onEdit}
          aria-label="Редактировать"
        >
          <EditIcon />
        </button>
        <button
          className={`${styles.actionButton} ${styles.deleteButton}`}
          onClick={handleDelete}
          aria-label="Удалить"
        >
          <TrashIcon />
        </button>
      </div>
    </div>
  );
}

// Icons
function EditIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
      <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
    </svg>
  );
}

function TrashIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <polyline points="3 6 5 6 21 6" />
      <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
    </svg>
  );
}
