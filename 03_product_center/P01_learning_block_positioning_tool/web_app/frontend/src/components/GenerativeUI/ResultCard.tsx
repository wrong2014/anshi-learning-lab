import React from 'react';
import { Target, XCircle, CheckCircle2, AlertTriangle, ClipboardCheck, HelpCircle } from 'lucide-react';
import styles from './ResultCard.module.css';
import type { ResultData } from '../../types';

interface Props {
  data: ResultData;
}

export default function ResultCard({ data }: Props) {
  const subjectLabel = data.subject_label || data.subject || '';
  const categoryLabel = data.primary_category_label || data.primary_factor || '';

  return (
    <div className={styles.card}>
      <div className={styles.header}>
        <Target size={20} />
        <span className={styles.headerTitle}>
          学习卡点定位报告
          {subjectLabel && ` · ${subjectLabel}`}
          {data.grade_label && ` · ${data.grade_label}`}
        </span>
      </div>

      <div className={styles.content}>
        {/* 总结 */}
        {data.public_summary && (
          <div className={styles.section} style={{ marginBottom: '12px' }}>
            <div style={{ fontSize: '0.95rem', lineHeight: 1.7, color: 'var(--color-text-main)' }}>
              {data.public_summary}
            </div>
          </div>
        )}

        {/* 主因 */}
        <div className={styles.section}>
          <span className={styles.sectionTitle}>当前优先排查方向</span>
          <div className={styles.primaryFactor}>
            <div>{categoryLabel}</div>
            {data.primary_desc && (
              <div style={{ fontSize: '0.9rem', color: 'var(--color-text-main)', marginTop: '4px', fontWeight: 400 }}>
                {data.primary_desc}
              </div>
            )}
          </div>
        </div>

        {/* 放大器 */}
        {data.amplifier_label && (
          <div className={styles.section}>
            <span className={styles.sectionTitle}>
              <AlertTriangle size={14} style={{ marginRight: '4px', verticalAlign: 'middle' }} />
              放大因素
            </span>
            <div style={{ fontSize: '0.9rem', color: 'var(--color-text-main)', lineHeight: 1.6 }}>
              同时，{data.amplifier_label}，这会让主要卡点的影响反复出现。
            </div>
          </div>
        )}

        {/* 证据 */}
        {data.evidence && data.evidence.length > 0 && (
          <div className={styles.section}>
            <span className={styles.sectionTitle}>判断依据</span>
            <ul style={{ margin: 0, paddingLeft: '20px', color: 'var(--color-text-main)', fontSize: '0.9rem' }}>
              {data.evidence.map((ev, i) => (
                <li key={i} style={{ marginBottom: '4px' }}>{ev}</li>
              ))}
            </ul>
          </div>
        )}

        {/* 不确定性 */}
        {data.uncertainties && data.uncertainties.length > 0 && (
          <div className={styles.section}>
            <span className={styles.sectionTitle}>
              <HelpCircle size={14} style={{ marginRight: '4px', verticalAlign: 'middle' }} />
              还不能确定
            </span>
            <ul style={{ margin: 0, paddingLeft: '20px', color: 'var(--color-text-muted)', fontSize: '0.85rem' }}>
              {data.uncertainties.map((u, i) => (
                <li key={i} style={{ marginBottom: '4px' }}>{u}</li>
              ))}
            </ul>
          </div>
        )}

        {/* 今晚 5 分钟验证 */}
        {data.verification_action && (
          <div className={styles.section}>
            <span className={styles.sectionTitle}>
              <ClipboardCheck size={14} style={{ marginRight: '4px', verticalAlign: 'middle' }} />
              今晚 5 分钟验证
            </span>
            <div className={styles.verificationBox}>
              <div className={styles.verificationTitle}>{data.verification_action.title}</div>
              <div className={styles.verificationSteps}>{data.verification_action.steps}</div>
              <div className={styles.verificationObserve}>
                <strong>重点观察：</strong>{data.verification_action.observe}
              </div>
            </div>
          </div>
        )}

        {/* 7 天行动 */}
        <div className={styles.section}>
          <span className={styles.sectionTitle}>父母未来 7 天行动建议</span>
          <div className={styles.actionBox}>
            {data.next_7_days_stop && (
              <div className={styles.actionItem}>
                <XCircle size={18} className={styles.actionStop} />
                <div style={{ fontSize: '0.9rem' }}>
                  <strong>先停做：</strong>{data.next_7_days_stop}
                </div>
              </div>
            )}
            {data.next_7_days_start && (
              <div className={styles.actionItem}>
                <CheckCircle2 size={18} className={styles.actionStart} />
                <div style={{ fontSize: '0.9rem' }}>
                  <strong>开始做：</strong>{data.next_7_days_start}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* 常见误区 */}
        {data.parent_common_mistake && (
          <div className={styles.section}>
            <span className={styles.sectionTitle}>
              <AlertTriangle size={14} style={{ marginRight: '4px', verticalAlign: 'middle' }} />
              家长常见误区
            </span>
            <div style={{ fontSize: '0.9rem', color: 'var(--color-text-main)', lineHeight: 1.6 }}>
              {data.parent_common_mistake}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
