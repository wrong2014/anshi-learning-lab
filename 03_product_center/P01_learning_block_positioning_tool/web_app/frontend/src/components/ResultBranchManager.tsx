import { Check, Copy, Loader2 } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { getResultBranches, getResultPreview } from '../api';
import type { ResultBranchCatalog, ResultData } from '../types';
import ResultCard from './GenerativeUI/ResultCard';
import styles from './ResultBranchManager.module.css';

const FEEDBACK_STORAGE_KEY = 'p01-result-branch-feedback-v1';

function readFeedback(): Record<string, string> {
  try {
    return JSON.parse(localStorage.getItem(FEEDBACK_STORAGE_KEY) || '{}');
  } catch {
    return {};
  }
}

export default function ResultBranchManager() {
  const [catalog, setCatalog] = useState<ResultBranchCatalog | null>(null);
  const [subject, setSubject] = useState('math');
  const [category, setCategory] = useState('C_modeling_and_transfer');
  const [amplifier, setAmplifier] = useState('');
  const [gradeLabel, setGradeLabel] = useState('初二');
  const [preview, setPreview] = useState<ResultData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [feedbackByBranch, setFeedbackByBranch] = useState<Record<string, string>>(readFeedback);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    getResultBranches()
      .then((data) => {
        setCatalog(data);
        setSubject(data.subjects[0]?.id || 'math');
        setCategory(data.categories[2]?.id || data.categories[0]?.id || 'C_modeling_and_transfer');
      })
      .catch(() => setError('结果分支目录暂时没有加载成功。'));
  }, []);

  useEffect(() => {
    if (!catalog) return;
    let cancelled = false;
    setLoading(true);
    setError('');
    getResultPreview({
      subject,
      category,
      amplifier: amplifier || undefined,
      grade_label: gradeLabel,
    })
      .then((data) => {
        if (!cancelled) setPreview(data);
      })
      .catch(() => {
        if (!cancelled) setError('这个结果分支暂时无法预览。');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [amplifier, catalog, category, gradeLabel, subject]);

  const activeBranch = useMemo(
    () => catalog?.branches.find((branch) => branch.subject === subject && branch.category === category),
    [catalog, category, subject],
  );
  const branchId = preview?.branch_id || activeBranch?.id || '';
  const feedback = feedbackByBranch[branchId] || '';

  const handleFeedbackChange = (value: string) => {
    if (!branchId) return;
    const next = { ...feedbackByBranch, [branchId]: value };
    setFeedbackByBranch(next);
    localStorage.setItem(FEEDBACK_STORAGE_KEY, JSON.stringify(next));
    setCopied(false);
  };

  const copyFeedback = async () => {
    if (!branchId) return;
    const categoryLabel = catalog?.categories.find((item) => item.id === category)?.label || '';
    const subjectLabel = catalog?.subjects.find((item) => item.id === subject)?.label || '';
    await navigator.clipboard.writeText(
      `结果分支：${branchId}\n学科：${subjectLabel}\n卡点：${categoryLabel}\n放大因素：${amplifier || '无'}\n反馈：${feedback || '暂无'}`,
    );
    setCopied(true);
  };

  if (!catalog && !error) {
    return <p className={styles.loading}><Loader2 size={16} className={styles.spin} /> 正在读取结果分支...</p>;
  }

  if (!catalog) {
    return <p className={styles.error}>{error}</p>;
  }

  return (
    <div className={styles.manager}>
      <aside className={styles.controls}>
        <div className={styles.catalogMeta}>
          <span>目录版本</span>
          <strong>{catalog.version}</strong>
          <em>{catalog.branches.length} 个结果分支</em>
        </div>

        <fieldset className={styles.fieldset}>
          <legend>学科</legend>
          <div className={styles.segmented}>
            {catalog.subjects.map((item) => (
              <button
                key={item.id}
                type="button"
                className={subject === item.id ? styles.activeSegment : ''}
                onClick={() => setSubject(item.id)}
              >
                {item.label}
              </button>
            ))}
          </div>
        </fieldset>

        <fieldset className={styles.fieldset}>
          <legend>卡点分支</legend>
          <div className={styles.categoryList}>
            {catalog.categories.map((item) => (
              <button
                key={item.id}
                type="button"
                className={category === item.id ? styles.activeCategory : ''}
                onClick={() => setCategory(item.id)}
              >
                <strong>{item.label}</strong>
                <span>{item.description}</span>
              </button>
            ))}
          </div>
        </fieldset>

        <label className={styles.selectField}>
          <span>放大因素</span>
          <select value={amplifier} onChange={(event) => setAmplifier(event.target.value)}>
            <option value="">不叠加</option>
            {catalog.amplifiers.map((item) => (
              <option key={item.id} value={item.id}>{item.label}</option>
            ))}
          </select>
        </label>

        <label className={styles.selectField}>
          <span>年级显示</span>
          <select value={gradeLabel} onChange={(event) => setGradeLabel(event.target.value)}>
            <option value="五年级">五年级</option>
            <option value="初一">初一</option>
            <option value="初二">初二</option>
            <option value="初三">初三</option>
            <option value="高一">高一</option>
          </select>
        </label>
      </aside>

      <section className={styles.previewPane}>
        <div className={styles.previewHeader}>
          <div>
            <span>分支编号</span>
            <code>{branchId}</code>
          </div>
          {activeBranch && <p>验证动作：{activeBranch.verification_title}</p>}
        </div>

        {loading ? (
          <p className={styles.loading}><Loader2 size={16} className={styles.spin} /> 正在生成预览...</p>
        ) : error ? (
          <p className={styles.error}>{error}</p>
        ) : preview ? (
          <ResultCard data={preview} />
        ) : null}

        <div className={styles.feedback}>
          <label htmlFor="result-branch-feedback">反馈备注</label>
          <textarea
            id="result-branch-feedback"
            value={feedback}
            onChange={(event) => handleFeedbackChange(event.target.value)}
            placeholder="例如：这句太像老师；这里应该先安慰妈妈；验证动作还不够具体。"
          />
          <button type="button" onClick={copyFeedback} disabled={!branchId}>
            {copied ? <Check size={16} /> : <Copy size={16} />}
            {copied ? '已复制' : '复制反馈'}
          </button>
        </div>
      </section>
    </div>
  );
}
