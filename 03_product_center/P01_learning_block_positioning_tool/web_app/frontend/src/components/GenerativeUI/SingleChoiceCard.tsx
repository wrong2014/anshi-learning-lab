import React, { useState } from 'react';
import { Check, Send } from 'lucide-react';
import styles from './SingleChoiceCard.module.css';
import type { UIBlock } from '../../types';

interface Props {
  block: UIBlock;
  onSelect: (optionId: string, optionLabel: string) => void;
  onMultiSelect?: (optionIds: string[], optionLabels: string[]) => void;
  onFreeText?: (text: string) => void;
  disabled?: boolean;
}

export default function SingleChoiceCard({ block, onSelect, onMultiSelect, onFreeText, disabled }: Props) {
  const isMulti = block.type === 'multi_choice';
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [otherText, setOtherText] = useState('');
  const [submitted, setSubmitted] = useState(false);

  const effectiveDisabled = disabled || submitted;

  const handleSingleClick = (opt: { id: string; label: string }) => {
    if (effectiveDisabled) return;
    setSubmitted(true);
    onSelect(opt.id, opt.label);
  };

  const handleMultiToggle = (optId: string) => {
    if (effectiveDisabled) return;
    setSelectedIds(prev => {
      const next = new Set(prev);
      if (next.has(optId)) next.delete(optId);
      else next.add(optId);
      return next;
    });
  };

  const handleMultiConfirm = () => {
    if (effectiveDisabled || selectedIds.size === 0) return;
    setSubmitted(true);
    const ids = Array.from(selectedIds);
    const labels = ids.map(id => block.options?.find(o => o.id === id)?.label || id);
    if (onMultiSelect) {
      onMultiSelect(ids, labels);
    } else {
      // fallback: 用逗号连接
      onSelect(ids.join(','), labels.join('、'));
    }
  };

  const handleOtherSubmit = () => {
    if (effectiveDisabled || !otherText.trim()) return;
    setSubmitted(true);
    if (onFreeText) {
      onFreeText(otherText.trim());
    } else {
      onSelect('_other', otherText.trim());
    }
  };

  const handleOtherKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleOtherSubmit();
    }
  };

  return (
    <div className={styles.card} style={{ opacity: effectiveDisabled ? 0.7 : 1, pointerEvents: effectiveDisabled ? 'none' : 'auto' }}>
      {block.title && <div className={styles.cardTitle}>{block.title}</div>}

      {block.options?.map((opt) => (
        isMulti ? (
          <button
            key={opt.id}
            className={`${styles.option} ${selectedIds.has(opt.id) ? styles.optionSelected : ''}`}
            onClick={() => handleMultiToggle(opt.id)}
          >
            <span className={`${styles.checkbox} ${selectedIds.has(opt.id) ? styles.checkboxChecked : ''}`}>
              {selectedIds.has(opt.id) && <Check size={12} color="white" />}
            </span>
            {opt.label}
          </button>
        ) : (
          <button
            key={opt.id}
            className={styles.option}
            onClick={() => handleSingleClick(opt)}
          >
            {opt.label}
          </button>
        )
      ))}

      {/* 多选确认按钮 */}
      {isMulti && (
        <button
          className={styles.confirmBtn}
          onClick={handleMultiConfirm}
          disabled={selectedIds.size === 0}
        >
          确认选择 ({selectedIds.size})
        </button>
      )}

      {/* "其他"自由输入 */}
      <div className={styles.otherInput}>
        <input
          type="text"
          className={styles.otherTextField}
          placeholder="都不像？用你自己的话说..."
          value={otherText}
          onChange={(e) => setOtherText(e.target.value)}
          onKeyDown={handleOtherKeyDown}
          disabled={effectiveDisabled}
        />
        <button
          className={styles.otherSendBtn}
          onClick={handleOtherSubmit}
          disabled={!otherText.trim() || effectiveDisabled}
        >
          <Send size={14} />
        </button>
      </div>
    </div>
  );
}
