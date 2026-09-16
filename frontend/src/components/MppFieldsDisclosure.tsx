import { MPP_FIELDS_UNCHANGED, MPP_FIELDS_UPDATED, FORMULAS } from '../calcHelp'

/** Скрытый блок под заголовком: что меняем в .mpp и свод формул. */
export function MppFieldsDisclosure() {
  return (
    <details className="disclosure">
      <summary>Что меняется в файле MS Project (.mpp) и как считаются показатели</summary>
      <div className="disclosure-body">
        <p>
          После «Сохранить и пересчитать» обновляется <b>одна задача</b> (Ид из формы) в sample/актуальном
          графике. Ниже — полный перечень полей и формулы.
        </p>

        <h3>Обновляем в .mpp («жёлтые» поля)</h3>
        <div className="disclosure-table-wrap">
          <table className="disclosure-table">
            <thead>
              <tr>
                <th>Поле (форма / CSV)</th>
                <th>Поле Project</th>
                <th>Откуда значение</th>
              </tr>
            </thead>
            <tbody>
              {MPP_FIELDS_UPDATED.map((row) => (
                <tr key={row.label}>
                  <td>{row.label}</td>
                  <td>
                    <code>{row.projectField}</code>
                  </td>
                  <td>{row.note}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <h3>Не изменяем</h3>
        <div className="disclosure-table-wrap">
          <table className="disclosure-table">
            <thead>
              <tr>
                <th>Поле</th>
                <th>Project</th>
                <th>Комментарий</th>
              </tr>
            </thead>
            <tbody>
              {MPP_FIELDS_UNCHANGED.map((row) => (
                <tr key={row.label}>
                  <td>{row.label}</td>
                  <td>
                    <code>{row.projectField}</code>
                  </td>
                  <td>{row.note}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <h3>Формулы расчётов</h3>
        <ul className="formula-list">
          {FORMULAS.map((f) => (
            <li key={f.id}>
              <b>{f.title}</b> — <code>{f.formula}</code>
              <br />
              <span className="formula-detail">{f.detail}</span>
            </li>
          ))}
        </ul>
      </div>
    </details>
  )
}
