/**
 * UI Constants - Тексты интерфейса (русский)
 */

export const UI_TEXT = {
  // TopBar
  today: 'Сегодня',

  // DayEventsPanel
  selectDay: 'Выберите день',
  noEvents: 'Нет событий',
  addEvent: '+ Добавить событие',

  // EventForm
  formTitleCreate: 'Новое событие',
  formTitleEdit: 'Редактирование',
  fieldTitle: 'Название',
  fieldTitlePlaceholder: 'Введите название события',
  fieldDate: 'Дата',
  fieldTime: 'Время',
  fieldEndDate: 'Дата окончания',
  fieldEndTime: 'Время окончания',
  fieldAllDay: 'Весь день',
  fieldType: 'Тип',
  fieldTypePlaceholder: 'Выберите тип',
  fieldCulture: 'Культура',
  fieldCulturePlaceholder: 'Выберите культуру',
  fieldPlot: 'Участок',
  fieldPlotPlaceholder: 'Например: Участок 1',
  fieldDescription: 'Описание',
  fieldDescriptionPlaceholder: 'Дополнительная информация...',
  save: 'Сохранить',
  create: 'Создать',
  cancel: 'Отмена',

  // EventDetailsSheet
  edit: 'Редактировать',
  delete: 'Удалить',
  confirmDelete: 'Удалить событие?',
  confirmDeleteText: 'Это действие нельзя отменить',
  yes: 'Да',
  no: 'Нет',

  // SideMenu
  menuCalendar: 'Календарь',
  menuSettings: 'Настройки',
  menuAbout: 'О приложении',

  // Status
  statusPlanned: 'Запланировано',
  statusDone: 'Выполнено',
  statusSkipped: 'Пропущено',

  // Validation errors
  errorTitleRequired: 'Название обязательно',
  errorTitleTooLong: 'Максимум 100 символов',
  errorDateRequired: 'Дата обязательна',
  errorTypeRequired: 'Тип обязателен',
  errorEndDateBeforeStart: 'Дата окончания должна быть после начала',

  // General
  loading: 'Загрузка...',
  error: 'Ошибка',
  retry: 'Повторить',
};

/**
 * Дни недели (начиная с понедельника)
 */
export const WEEKDAYS_SHORT = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'];

export const WEEKDAYS_FULL = [
  'Понедельник',
  'Вторник',
  'Среда',
  'Четверг',
  'Пятница',
  'Суббота',
  'Воскресенье',
];

/**
 * Месяцы
 */
export const MONTHS_FULL = [
  'Январь',
  'Февраль',
  'Март',
  'Апрель',
  'Май',
  'Июнь',
  'Июль',
  'Август',
  'Сентябрь',
  'Октябрь',
  'Ноябрь',
  'Декабрь',
];

export const MONTHS_SHORT = [
  'Янв',
  'Фев',
  'Мар',
  'Апр',
  'Май',
  'Июн',
  'Июл',
  'Авг',
  'Сен',
  'Окт',
  'Ноя',
  'Дек',
];
