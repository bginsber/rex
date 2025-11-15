import styles from './SettingsView.module.css'

export function SettingsView() {
  return (
    <section className={styles.settingsView}>
      <div>
        <h2>Settings</h2>
        <p className={styles.subtitle}>
          Configure RexLit Review UI preferences. Additional settings will ship soon.
        </p>
      </div>
      <div className={styles.placeholder}>
        <p>Settings controls are not available in this build.</p>
        <p>Use CLI flags or environment variables to adjust behavior.</p>
      </div>
    </section>
  )
}
