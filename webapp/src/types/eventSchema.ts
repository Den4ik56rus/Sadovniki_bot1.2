/**
 * Event Form Schema - Zod валидация для формы события
 */

import { z } from 'zod';

// Помощник для optional string полей - пустая строка превращается в undefined
const optionalString = z.string().optional().transform(val => val === '' ? undefined : val);

// Время в формате HH:mm или пустое
const optionalTime = z.string()
  .optional()
  .transform(val => val === '' ? undefined : val)
  .refine(val => !val || /^\d{2}:\d{2}$/.test(val), 'Формат: HH:mm');

// Дата в формате YYYY-MM-DD или пустая
const optionalDate = z.string()
  .optional()
  .transform(val => val === '' ? undefined : val)
  .refine(val => !val || /^\d{4}-\d{2}-\d{2}$/.test(val), 'Формат: YYYY-MM-DD');

export const eventFormSchema = z.object({
  title: z.string()
    .min(1, 'Заголовок обязателен')
    .max(100, 'Максимум 100 символов'),
  startDate: z.string().regex(/^\d{4}-\d{2}-\d{2}$/, 'Формат: YYYY-MM-DD'),
  startTime: optionalTime,
  endDate: optionalDate,
  endTime: optionalTime,
  allDay: z.boolean(),
  type: z.enum(['nutrition', 'soil', 'protection', 'harvest', 'planting', 'other']),
  cultureCode: optionalString,
  plotId: optionalString,
  description: z.string().max(500).optional().transform(val => val === '' ? undefined : val),
}).refine(
  (data) => {
    if (data.endDate && data.startDate > data.endDate) return false;
    return true;
  },
  { message: 'Дата окончания должна быть после начала', path: ['endDate'] }
).refine(
  (data) => {
    // Если не весь день, требуем время начала
    if (!data.allDay && !data.startTime) return false;
    return true;
  },
  { message: 'Укажите время начала', path: ['startTime'] }
);

// Output type after transforms
export type EventFormValues = z.output<typeof eventFormSchema>;

// Input type for defaultValues (before transforms)
export type EventFormInput = z.input<typeof eventFormSchema>;
