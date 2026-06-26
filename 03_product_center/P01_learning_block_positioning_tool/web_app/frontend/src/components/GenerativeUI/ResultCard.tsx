import React from 'react';
import { Target, XCircle, CheckCircle2 } from 'lucide-react';
import styles from './ResultCard.module.css';
import type { ResultData } from '../../types';

interface Props {
  data: ResultData;
}

export default function ResultCard({ data }: Props) {
  return (
    <div className={styles.card}>
      <div className={styles.header}>
        <Target size={20} />
        <span className={styles.headerTitle}>学习卡点定位报告 ({data.subject})</span>
      </div>
      
      <div className={styles.content}>
        {data.public_summary && (
          <div className={styles.section} style={{marginBottom: '12px'}}>
            <div style={{fontSize: '0.95rem', lineHeight: 1.6, color: 'var(--color-text-main)'}}>
              {data.public_summary}
            </div>
          </div>
        )}

        <div className={styles.section}>
          <span className={styles.sectionTitle}>当前最可能主因</span>
          <div className={styles.primaryFactor}>
            <div>{data.primary_factor}</div>
            {data.primary_desc && (
              <div style={{fontSize: '0.9rem', color: 'var(--color-text-main)', marginTop: '4px', fontWeight: 400}}>
                {data.primary_desc}
              </div>
            )}
          </div>
        </div>

        {data.secondary_factors && data.secondary_factors.length > 0 && (
          <div className={styles.section}>
            <span className={styles.sectionTitle}>次因及关联表现</span>
            <div className={styles.tagList}>
              {data.secondary_factors.map((factor, i) => (
                <span key={i} className={styles.tag}>{factor}</span>
              ))}
            </div>
          </div>
        )}

        {data.evidence && data.evidence.length > 0 && (
          <div className={styles.section}>
            <span className={styles.sectionTitle}>关键证据</span>
            <ul style={{margin: 0, paddingLeft: '20px', color: 'var(--color-text-main)', fontSize: '0.9rem'}}>
              {data.evidence.map((ev, i) => (
                <li key={i} style={{marginBottom: '4px'}}>{ev}</li>
              ))}
            </ul>
          </div>
        )}

        <div className={styles.section}>
          <span className={styles.sectionTitle}>父母未来 7 天行动建议</span>
          <div className={styles.actionBox}>
            {data.next_7_days_stop && (
              <div className={styles.actionItem}>
                <XCircle size={18} className={styles.actionStop} />
                <div style={{fontSize: '0.9rem'}}>
                  <strong>先停做：</strong>{data.next_7_days_stop}
                </div>
              </div>
            )}
            {data.next_7_days_start && (
              <div className={styles.actionItem}>
                <CheckCircle2 size={18} className={styles.actionStart} />
                <div style={{fontSize: '0.9rem'}}>
                  <strong>开始做：</strong>{data.next_7_days_start}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
