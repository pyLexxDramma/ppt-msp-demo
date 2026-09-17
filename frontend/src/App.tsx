import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { clearMppUpload, fetchPrefill, mppDownloadHref, postRecalc, uploadMpp } from './api'
import { CustomSelect } from './components/CustomSelect'
import { FieldLabel } from './components/FieldLabel'
import { MppFieldsDisclosure } from './components/MppFieldsDisclosure'
import { MppUploadCard } from './components/MppUploadCard'
import { ScheduleTable } from './components/ScheduleTable'
import { computeAggregates, fmt, periodLabel, signedFmt } from './formLogic'
import { FIELD_HELP, type FormOptions } from './options'
import { isStreamlitComponent, subscribeArgs, syncHeight } from './streamlitBridge'
import { MONTHS_RU, WEEKS_COUNT, defaultForm, type FormState, type RecalcResult } from './types'
import { formIsValid, validateForm } from './validation'

type ToastKind = 'info' | 'warn' | 'ok'

type ToastState = {
  message: string
  kind: ToastKind
}

export default function App() {
  const [form, setForm] = useState<FormState>(defaultForm)
  const [options, setOptions] = useState<FormOptions | null>(null)
  const [months, setMonths] = useState<string[]>([...MONTHS_RU])
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState<RecalcResult | null>(null)
  const [theme, setTheme] = useState<'light' | 'dark'>('light')
  const [toast, setToast] = useState<ToastState | null>(null)
  const [touched, setTouched] = useState(false)
  const [mppUploadId, setMppUploadId] = useState<string | null>(null)
  const [mppFilename, setMppFilename] = useState<string | null>(null)
  const toastTimer = useRef<number | null>(null)

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
  }, [theme])

  const showToast = useCallback((message: string, kind: ToastKind = 'info') => {
    if (toastTimer.current != null) {
      window.clearTimeout(toastTimer.current)
    }
    setToast({ message, kind })
    toastTimer.current = window.setTimeout(() => {
      setToast(null)
      toastTimer.current = null
    }, 5000)
  }, [])

  useEffect(() => {
    return () => {
      if (toastTimer.current != null) window.clearTimeout(toastTimer.current)
    }
  }, [])

  useEffect(() => {
    if (!isStreamlitComponent()) return
    return subscribeArgs((args) => {
      const upload = (args.prefill as { mpp_upload?: { ready?: boolean; filename?: string | null } } | undefined)
        ?.mpp_upload
      if (!upload?.ready) return
      setMppFilename(upload.filename ?? 'source.mpp')
      setMppUploadId((prev) => prev || 'session')
    })
  }, [])

  useEffect(() => {
    if (!isStreamlitComponent()) return
    syncHeight()
    const t = window.setTimeout(syncHeight, 50)
    return () => window.clearTimeout(t)
  }, [loading, result, form, toast, mppFilename, mppUploadId])

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const data = await fetchPrefill()
        if (cancelled) return
        setForm(defaultForm())
        if (data.months?.length) setMonths(data.months)
        if (data.options) setOptions(data.options)
        if (data.mpp_upload?.ready) {
          setMppFilename(data.mpp_upload.filename ?? 'source.mpp')
          setMppUploadId('session')
        }
      } catch (e) {
        if (!cancelled) {
          showToast(
            e instanceof Error ? e.message : 'Не удалось загрузить справочники',
            'warn',
          )
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [showToast])

  const sourceReady = Boolean(mppUploadId)
  const formLocked = !sourceReady

  const agg = useMemo(() => computeAggregates(form), [form])
  const errors = useMemo(
    () => (formLocked ? {} : validateForm(form, options)),
    [form, options, formLocked],
  )
  const valid = formIsValid(errors)


  const patch = <K extends keyof FormState>(key: K, value: FormState[K]) => {
    setForm((prev) => ({ ...prev, [key]: value }))
  }

  const patchWeek = (index: number, field: 'plan' | 'fact', raw: string) => {
    setForm((prev) => {
      const weeks = prev.weeks.map((w, i) => {
        if (i !== index) return w
        if (raw === '') {
          return { ...w, [field]: null }
        }
        return { ...w, [field]: Number(raw) }
      })
      while (weeks.length < WEEKS_COUNT) weeks.push({ plan: null, fact: null })
      return { ...prev, weeks: weeks.slice(0, WEEKS_COUNT) }
    })
  }

  const onSelectProject = (projectId: string) => {
    const p = options?.projects.find((x) => x.id === projectId)
    if (!p) return
    setForm((prev) => ({ ...prev, project: p.name, project_id: p.id }))
  }

  const onSelectTask = (taskId: string) => {
    const t = options?.tasks.find((x) => x.id === taskId)
    if (!t) return
    const p = options?.projects.find((x) => x.id === t.project_id)
    setForm((prev) => ({
      ...prev,
      task_id: t.id,
      task_name: t.name,
      unit: t.unit || prev.unit,
      vor: t.vor > 0 ? t.vor : prev.vor,
      prev_cumulative: Number.isFinite(t.vor_fact) ? t.vor_fact : 0,
      project_id: t.project_id || prev.project_id,
      project: p?.name || prev.project,
    }))
  }

  const onRecalc = async () => {
    setTouched(true)
    if (formLocked) {
      showToast('Сначала загрузите исходный .mpp', 'warn')
      return
    }
    if (!valid) {
      showToast('Исправьте подсвеченные поля перед пересчётом.', 'warn')
      return
    }
    setBusy(true)
    try {
      const data = await postRecalc(form, { mppUploadId })
      setResult(data)
      if (data.downloads.mpp) {
        showToast('Пересчёт завершён. Можно скачать .mpp', 'ok')
      }
    } catch (e) {
      showToast(e instanceof Error ? e.message : 'Ошибка пересчёта', 'warn')
    } finally {
      setBusy(false)
    }
  }

  if (loading) {
    return <div className="loading">Загрузка формы…</div>
  }

  const statusBadge =
    result?.status === 'over' ? (
      <span className="badge over">Превышение ВОР</span>
    ) : result?.status === 'done' ? (
      <span className="badge done">Завершено</span>
    ) : (
      <span className="badge progress">В работе</span>
    )

  const m1 = result?.schedule?.mode1 ?? result?.mode1 ?? {}
  const showErr = (key: string) => (touched ? errors[key] : undefined)

  const projectOpts = (options?.projects ?? []).map((p) => ({
    value: p.id,
    label: `${p.name}`,
  }))
  const projectIdOpts = (options?.projects ?? []).map((p) => ({
    value: p.id,
    label: p.id,
  }))
  const taskOpts = (options?.tasks ?? []).map((t) => ({
    value: t.id,
    label: t.name,
  }))
  const taskIdOpts = (options?.tasks ?? []).map((t) => ({
    value: t.id,
    label: t.id,
  }))
  const unitOpts = (options?.units ?? []).map((u) => ({ value: u, label: u }))
  const monthOpts = months.map((m, i) => ({ value: String(i), label: m }))
  const yearOpts = (options?.years ?? [2024, 2025, 2026, 2027, 2028]).map((y) => ({
    value: String(y),
    label: String(y),
  }))
  const modeOpts = (options?.modes ?? [{ id: 'last', label: 'По факту последней недели (Mode1)' }]).map(
    (m) => ({ value: m.id, label: m.label }),
  )

  const beforeStart = result?.update?.before?.['Начало'] || '—'
  const beforeFinish = result?.update?.before?.['Окончание'] || '—'
  const afterStart = result?.schedule.start ?? result?.update?.after?.['Начало'] ?? '—'
  const afterFinish = result?.schedule.finish ?? result?.update?.after?.['Окончание'] ?? '—'
  const remDays =
    result?.schedule.remaining_days_ceil ??
    (m1 as { remaining_days_ceil?: number }).remaining_days_ceil ??
    null
  const factPeriod = (m1 as { fact_period?: number }).fact_period
  const lastWeek = (m1 as { last_week?: number }).last_week
  const mppHref = result ? mppDownloadHref(result) : null

  return (
    <>
      <header className="topbar">
        <div className="container">
          <div className="brand">
            <span className="brand-mark">Λ</span>
            <span className="brand-word">CONALL</span>
          </div>
          <div className="topbar-right">
            <span className="pill">AI.CONALL.RU · ВВОД ДАННЫХ</span>
            <button
              type="button"
              className="theme-toggle"
              onClick={() => setTheme((t) => (t === 'dark' ? 'light' : 'dark'))}
            >
              <span className="dot" />
              <span>{theme === 'dark' ? 'Тёмная тема' : 'Светлая тема'}</span>
            </button>
          </div>
        </div>
      </header>

      <div className="hero">
        <div className="container">
          <h1 className="hero-title">Данные по объему стройплощадок</h1>
          <p className="hero-sub">
            Загрузите исходный .mpp → заполните план/факт сами → пересчитайте → скачайте обновлённый график
          </p>
          <div className="hero-underline" />
        </div>
        </div>

      <main className="main">
        <div className="container">
          <MppFieldsDisclosure />
          <MppUploadCard
            filename={mppFilename}
            busy={busy}
            uploadFn={uploadMpp}
            onUploaded={({ uploadId, filename, options, warning }) => {
              setMppUploadId(uploadId)
              setMppFilename(filename)
              if (options) setOptions(options)
              setForm(defaultForm())
              setTouched(false)
              setResult(null)
              if (warning) showToast(warning, 'warn')
              else showToast(`Файл загружен: ${filename}. Выберите задачу из .mpp.`, 'ok')
            }}
            onCleared={() => {
              void clearMppUpload()
              setMppUploadId(null)
              setMppFilename(null)
              setForm(defaultForm())
              setTouched(false)
              setResult(null)
            }}
            onError={(message) => showToast(message, 'warn')}
          />
          <div className={`card form-block${formLocked ? ' is-locked' : ''}`}>
            {formLocked ? (
              <div className="form-lock-banner" role="status">
                Сначала загрузите исходный .mpp — затем заполните поля вручную (без автоподстановки).
              </div>
            ) : null}
            <fieldset className="form-fieldset" disabled={formLocked}>
            <div className="form-section settings-card">
              <div className="form-step-head">
                <p className="card-title">2. Параметры и объёмы</p>
              </div>
              <div className="settings-fields">
                <FieldLabel
                  className="wide"
                  label="Объект / ЖК"
                  help={FIELD_HELP.project}
                  error={showErr('project')}
                >
                  <CustomSelect
                    value={form.project_id}
                    options={projectOpts}
                    invalid={Boolean(showErr('project'))}
                    onChange={onSelectProject}
                    aria-label="Объект / ЖК"
                  />
                </FieldLabel>
                <FieldLabel
                  className="wide"
                  label="ID проекта"
                  help={FIELD_HELP.project_id}
                  error={showErr('project_id')}
                >
                  <CustomSelect
                    value={form.project_id}
                    options={projectIdOpts}
                    disabled
                    invalid={Boolean(showErr('project_id'))}
                    onChange={() => undefined}
                    aria-label="ID проекта"
                  />
                </FieldLabel>
                <FieldLabel label="Месяц отчёта" help={FIELD_HELP.period_month} error={showErr('period_month')}>
                  <CustomSelect
                    value={form.period_month < 0 ? '' : String(form.period_month)}
                    options={monthOpts}
                    placeholder="Выберите месяц"
                    invalid={Boolean(showErr('period_month'))}
                    onChange={(v) => patch('period_month', Number(v))}
                    aria-label="Месяц отчёта"
                  />
                </FieldLabel>
                <FieldLabel label="Год" help={FIELD_HELP.period_year} error={showErr('period_year')}>
                  <CustomSelect
                    value={form.period_year ? String(form.period_year) : ''}
                    options={yearOpts}
                    placeholder="Выберите год"
                    invalid={Boolean(showErr('period_year'))}
                    onChange={(v) => patch('period_year', Number(v))}
                    aria-label="Год"
                  />
                </FieldLabel>
                <FieldLabel
                  className="wide"
                  label="Режим расчёта прогноза"
                  help={FIELD_HELP.mode}
                >
                  <CustomSelect
                    value={form.mode || 'last'}
                    options={modeOpts}
                    disabled
                    onChange={() => undefined}
                    aria-label="Режим расчёта"
                  />
                  <p className="field-caption">остальные режимы — следующий этап</p>
                </FieldLabel>
              </div>
              <p className="settings-caption">
                Данные по выбранному периоду вносятся вручную, один раз в неделю
              </p>
            </div>

            <div className="form-section">
              <div className="card-head-row">
                <div>
                  <p className="card-title">Задача</p>
                  <p className="card-sub">из графика MPP / БД — ID подставляются автоматически</p>
                </div>
              </div>
              <div className="form-grid">
                <FieldLabel label="Наименование работ" help={FIELD_HELP.task_name} error={showErr('task_name')}>
                  <CustomSelect
                    value={form.task_id}
                    options={taskOpts}
                    invalid={Boolean(showErr('task_name'))}
                    onChange={onSelectTask}
                    aria-label="Наименование работ"
                  />
                </FieldLabel>
                <FieldLabel label="Ид задачи (MSP)" help={FIELD_HELP.task_id} error={showErr('task_id')}>
                  <CustomSelect
                    value={form.task_id}
                    options={taskIdOpts}
                    disabled
                    invalid={Boolean(showErr('task_id'))}
                    onChange={() => undefined}
                    aria-label="Ид задачи"
                  />
                </FieldLabel>
                <FieldLabel label="ВОР" help={FIELD_HELP.vor} error={showErr('vor')}>
                  <input
                    id="tVor"
                    type="number"
                    readOnly
                    disabled
                    className={`readonly-input${showErr('vor') ? ' invalid' : ''}`}
                    value={form.vor}
                    aria-label="ВОР из графика"
                  />
                </FieldLabel>
                <FieldLabel label="Ед. измерения" help={FIELD_HELP.unit} error={showErr('unit')}>
                  <CustomSelect
                    value={form.unit}
                    options={unitOpts}
                    invalid={Boolean(showErr('unit'))}
                    onChange={(v) => patch('unit', v)}
                    aria-label="Ед. измерения"
                  />
                </FieldLabel>
              </div>
            </div>

            <div className="form-section">
              <div className="card-head-row">
                <div>
                  <p className="card-title">Ввод по неделям</p>
                  <p className="card-sub">
                    План и факт по неделям — отклонение и накопительно считаются автоматически
                  </p>
                </div>
                <span className="period-pill">{periodLabel(form, months)}</span>
              </div>

              <div className="zone zone-blue">
                <div className="zone-head">
                  <span>План</span>
                  <span className="zone-badge">{fmt(agg.plan_total)}</span>
                </div>
                <div className="zone-grid">
                  {Array.from({ length: WEEKS_COUNT }, (_, i) => (
                    <FieldLabel
                      key={`plan-${i}`}
                      className="zone-field"
                      label={`${i + 1} нед.`}
                      help={FIELD_HELP.week_plan}
                      error={showErr(`week_plan_${i}`)}
                    >
                      <input
                        type="number"
                        className={showErr(`week_plan_${i}`) ? 'invalid' : undefined}
                        value={form.weeks[i]?.plan ?? ''}
                        onChange={(e) => patchWeek(i, 'plan', e.target.value)}
                      />
                    </FieldLabel>
                  ))}
                </div>
              </div>

              <div className="zone zone-green">
                <div className="zone-head">
                  <span>Факт</span>
                  <span className="zone-badge">{fmt(agg.fact_total)}</span>
                </div>
                <div className="zone-grid">
                  {Array.from({ length: WEEKS_COUNT }, (_, i) => (
                    <FieldLabel
                      key={`fact-${i}`}
                      className="zone-field"
                      label={`${i + 1} нед.`}
                      help={FIELD_HELP.week_fact}
                      error={showErr(`week_fact_${i}`)}
                    >
                      <input
                        type="number"
                        className={`${showErr(`week_fact_${i}`) ? 'invalid' : ''}${
                          form.weeks[i]?.fact === null || form.weeks[i]?.fact === undefined
                            ? ' fact-empty'
                            : ''
                        }`.trim()}
                        value={form.weeks[i]?.fact ?? ''}
                        onChange={(e) => patchWeek(i, 'fact', e.target.value)}
                        placeholder="—"
                      />
                    </FieldLabel>
                  ))}
                </div>
                {showErr('weeks_fact') ? (
                  <p className="field-error zone-error">{showErr('weeks_fact')}</p>
                ) : null}
              </div>

              <div className="zone zone-amber">
                <div className="zone-head">
                  <span>Отклонение и накопительно</span>
                  <span className={`zone-badge ${agg.month_cum >= 0 ? 'pos' : 'neg'}`}>
                    {`${agg.month_cum > 0 ? '+' : ''}${fmt(agg.month_cum)}`}
                  </span>
                </div>
                <div className="dashed-box">
                  <div className="dashed-label">Отклонение (факт − план)</div>
                  <div className="zone-grid">
                    {agg.rows.map((row, i) => {
                      const s = signedFmt(row.dev)
                      return (
                        <div className="zone-field" key={`dev-${i}`}>
                          <label>{i + 1} нед.</label>
                          <div className={`computed-val ${s.cls}`}>{s.text}</div>
                        </div>
                      )
                    })}
                  </div>
                </div>
                <div className="dashed-box">
                  <div className="dashed-label">Накопительно</div>
                  <div className="zone-grid">
                    {agg.rows.map((row, i) => {
                      const s = signedFmt(row.cum)
                      return (
                        <div className="zone-field strong" key={`cum-${i}`}>
                          <label>{i + 1} нед.</label>
                          <div className={`computed-val ${s.cls}`}>{s.text}</div>
                        </div>
                      )
                    })}
                  </div>
                </div>
                <p className="zone-note">
                  Отклонение считается как <b>Факт − План</b>. Недели без факта в накопительный расчёт не
                  попадают.
                </p>
              </div>
            </div>

            <div className="form-section">
              <div className="card-head-row">
                <div>
                  <p className="card-title">Факт накопленный с начала</p>
                </div>
              </div>
              <div className="stat-row">
                <div className="stat">
                  <FieldLabel
                    htmlFor="sPrevCum"
                    label="Накоплено до периода"
                    help={FIELD_HELP.prev_cumulative}
                    error={showErr('prev_cumulative')}
                  >
                    <div className="stat-value">
                      <input
                        id="sPrevCum"
                        type="number"
                        readOnly
                        disabled
                        className={`readonly-input${showErr('prev_cumulative') ? ' invalid' : ''}`}
                        value={form.prev_cumulative}
                        aria-label="Накоплено до периода из эталона"
                      />
                    </div>
                  </FieldLabel>
                </div>
                <div className="stat auto">
                  <label>Факт накопленный с начала</label>
                  <div className="stat-value">
                    <div className="val">
                      {fmt(agg.done)} {form.unit}
                    </div>
                  </div>
                </div>
                <div className="stat auto">
                  <label>Остаток до ВОР</label>
                  <div className="stat-value">
                    <div className={`val ${agg.remaining >= 0 ? 'pos' : 'neg'}`}>
                      {fmt(agg.remaining)} {form.unit}
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <div className="form-section form-actions">
              <div className="action-bar">
                <button
                  type="button"
                  className={`btn btn-primary${busy ? ' is-busy' : ''}`}
                  disabled={busy || formLocked}
                  onClick={onRecalc}
                >
                  {busy ? (
                    <>
                      <span className="btn-spinner" aria-hidden />
                      Пересчёт…
                    </>
                  ) : (
                    'Сохранить и пересчитать'
                  )}
                </button>
              </div>
            </div>
            </fieldset>
          </div>

          {result ? (
            <div className={`card result-panel${busy ? ' is-busy' : ''}`}>
              {busy ? <div className="result-busy" aria-hidden /> : null}
              <div className="result-head">
                <div>
                  <div className="result-head-title">Результат пересчёта (Mode1)</div>
                  <div className="result-head-sub">
                    {form.task_name || result.update?.name || 'Задача'} · {periodLabel(form, months)}
                  </div>
                </div>
                {statusBadge}
              </div>

              <div className="result-highlight">
                <div className="result-hl-item">
                  <span className="result-hl-label">Начало → Окончание</span>
                  <span className="result-hl-value">
                    {afterStart} → {afterFinish}
                  </span>
                </div>
                <div className="result-hl-item">
                  <span className="result-hl-label">Осталось дней</span>
                  <span className="result-hl-value">{remDays ?? '—'}</span>
                </div>
                <div className="result-hl-item">
                  <span className="result-hl-label">Факт периода</span>
                  <span className="result-hl-value">
                    нед. {lastWeek ?? '—'} · {fmt(factPeriod, 1)}
                  </span>
                </div>
              </div>

              <div className="result-body">
                <div className="result-line">
                  <span className="k">Факт накопленный / ВОР</span>
                  <span className="v">
                    {fmt(result.aggregates.done)} / {fmt(result.aggregates.vor)} {form.unit}
                  </span>
                </div>
                <div className="result-line">
                  <span className="k">Остаток</span>
                  <span className="v">
                    {fmt(result.aggregates.remaining)} {form.unit}
                  </span>
                </div>
                <div className="result-line">
                  <span className="k">Прогноз недель</span>
                  <span className="v">
                    {(m1 as { forecast_weeks?: number }).forecast_weeks != null
                      ? `≈ ${fmt((m1 as { forecast_weeks?: number }).forecast_weeks, 1)}`
                      : '—'}
                  </span>
                </div>
                <div className="result-line">
                  <span className="k">today (конец месяца отчёта)</span>
                  <span className="v">{result.today}</span>
                </div>
              </div>

              <div className="result-change">
                Обновлена задача Id {result.update?.task_id ?? form.task_id}
                {' · '}
                Начало {beforeStart} → {afterStart}
                {' · '}
                Окончание {beforeFinish} → {afterFinish}
              </div>

              {(result.schedule_before?.length || result.schedule_after?.length) ? (
                <div className="result-schedule-tables">
                  <ScheduleTable
                    title="До изменений"
                    rows={result.schedule_before ?? []}
                    cols={result.schedule_cols}
                  />
                  <ScheduleTable
                    title="После изменений"
                    rows={result.schedule_after ?? []}
                    cols={result.schedule_cols}
                    highlightChanged
                  />
                </div>
              ) : null}

              <div className="result-footer">
                {mppHref ? (
                  <a className="btn btn-primary" href={mppHref} download="msp_updated.mpp">
                    Скачать .mpp
                  </a>
                ) : (
                  <p className="result-mpp-note">
                    {result.mpp_error ||
                      'Расчёт готов. Файл .mpp недоступен на этой машине расчёта (нужны MS Project и pywin32).'}
                  </p>
                )}
              </div>
            </div>
          ) : null}

        </div>
      </main>

      <div
        className={`toast${toast ? ' show' : ''}${toast ? ` toast-${toast.kind}` : ''}`}
        role="status"
        aria-live="polite"
      >
        {toast?.message}
      </div>
    </>
  )
}
