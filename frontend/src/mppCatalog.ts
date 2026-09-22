import type { FormOptions } from './options'

/** Справочник пригоден для выбора работ — иначе форму не разблокируем. */
export function catalogHasTasks(options?: FormOptions | null): options is FormOptions {
  return Array.isArray(options?.tasks) && options.tasks.length > 0
}
