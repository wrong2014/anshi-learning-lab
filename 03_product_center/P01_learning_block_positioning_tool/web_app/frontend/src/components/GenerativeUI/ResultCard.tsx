import {
  AlertCircle,
  CheckCircle2,
  Search,
  Target,
  TimerReset,
  XCircle,
} from 'lucide-react';
import styles from './ResultCard.module.css';
import type { ResultData } from '../../types';

interface Props {
  data: ResultData;
}

const subjectLabels: Record<string, string> = {
  math: '数学',
  physics: '物理',
  chemistry: '化学',
  unknown: '理科',
};

const confidenceLabels: Record<string, string> = {
  low: '线索较少',
  medium: '方向较清楚',
  high: '多条线索一致',
};

export default function ResultCard({ data }: Props) {
  const subjectLabel = data.subject_label || subjectLabels[data.subject || ''] || data.subject || '理科';
  const primaryLabel = data.primary_category_label || data.primary_factor || '还需要更多信息';
  const uncertainties = data.uncertainties || data.missing_information || [];
  const confidenceLabel = confidenceLabels[data.confidence || ''] || data.confidence;

  return (
    <article className={styles.card}>
      <header className={styles.header}>
        <div className={styles.headerIcon}>
          <Target size={19} />
        </div>
        <div className={styles.headerCopy}>
          <span className={styles.eyebrow}>本次初步定位</span>
          <h3 className={styles.headerTitle}>
            {subjectLabel}{data.grade_label ? ` · ${data.grade_label}` : ''}
          </h3>
        </div>
        {confidenceLabel && <span className={styles.confidence}>{confidenceLabel}</span>}
      </header>

      <div className={styles.content}>
        {data.public_summary && <p className={styles.summary}>{data.public_summary}</p>}

        <section className={styles.primarySection}>
          <span className={styles.sectionTitle}>当前优先排查</span>
          <strong className={styles.primaryTitle}>{primaryLabel}</strong>
          {data.primary_desc && <p className={styles.primaryDescription}>{data.primary_desc}</p>}
        </section>

        {data.amplifier_label && (
          <section className={styles.amplifierSection}>
            <AlertCircle size={18} />
            <div>
              <span className={styles.inlineLabel}>同时留意</span>
              <p>{data.amplifier_label}</p>
            </div>
          </section>
        )}

        {data.evidence && data.evidence.length > 0 && (
          <section className={styles.section}>
            <span className={styles.sectionTitle}>为什么先看这个方向</span>
            <ul className={styles.list}>
              {data.evidence.slice(0, 4).map((evidence, index) => (
                <li key={`${evidence}-${index}`}>{evidence}</li>
              ))}
            </ul>
          </section>
        )}

        {data.verification_action && (
          <section className={styles.verificationSection}>
            <div className={styles.verificationHeading}>
              <TimerReset size={19} />
              <div>
                <span className={styles.sectionTitle}>今晚 5 分钟验证</span>
                <h4>{data.verification_action.title}</h4>
              </div>
            </div>
            {data.verification_action.steps && <p>{data.verification_action.steps}</p>}
            {data.verification_action.observe && (
              <p className={styles.observe}><strong>只观察：</strong>{data.verification_action.observe}</p>
            )}
          </section>
        )}

        {uncertainties.length > 0 && (
          <section className={styles.section}>
            <span className={styles.sectionTitle}>现在还不能确定</span>
            <ul className={styles.listMuted}>
              {uncertainties.slice(0, 3).map((item, index) => (
                <li key={`${item}-${index}`}>{item}</li>
              ))}
            </ul>
          </section>
        )}

        {(data.next_7_days_stop || data.next_7_days_start) && (
          <section className={styles.section}>
            <span className={styles.sectionTitle}>接下来先这样做</span>
            <div className={styles.actionRows}>
              {data.next_7_days_stop && (
                <div className={styles.actionItem}>
                  <XCircle size={18} className={styles.actionStop} />
                  <p><strong>先停一下：</strong>{data.next_7_days_stop}</p>
                </div>
              )}
              {data.next_7_days_start && (
                <div className={styles.actionItem}>
                  <CheckCircle2 size={18} className={styles.actionStart} />
                  <p><strong>开始观察：</strong>{data.next_7_days_start}</p>
                </div>
              )}
            </div>
          </section>
        )}

        {data.diagnostic_upgrade && (
          <section className={styles.upgradeSection}>
            <Search size={19} />
            <div>
              <span className={styles.inlineLabel}>要进一步确认</span>
              <p>{data.diagnostic_upgrade}</p>
            </div>
          </section>
        )}
      </div>
    </article>
  );
}
