import { Atom, Calculator, FlaskConical } from 'lucide-react';
import type { UIBlock } from '../../types';
import styles from './SubjectPicker.module.css';

interface Props {
  block: UIBlock;
  onSelect: (optionId: string, optionLabel: string) => void;
  disabled?: boolean;
}

const subjectIcons = {
  subject_math: Calculator,
  subject_physics: Atom,
  subject_chemistry: FlaskConical,
};

export default function SubjectPicker({ block, onSelect, disabled = false }: Props) {
  return (
    <section className={styles.picker} aria-label={block.title || '选择科目'}>
      <div className={styles.heading}>
        {block.title && <h3>{block.title}</h3>}
        {block.body && <p>{block.body}</p>}
      </div>
      <div className={styles.subjects}>
        {(block.options || []).map((option) => {
          const Icon = subjectIcons[option.id as keyof typeof subjectIcons] || Calculator;
          return (
            <button
              key={option.id}
              type="button"
              onClick={() => onSelect(option.id, option.label)}
              disabled={disabled}
            >
              <span className={styles.icon}><Icon size={20} /></span>
              <strong>{option.label}</strong>
              {option.hint && <small>{option.hint}</small>}
            </button>
          );
        })}
      </div>
    </section>
  );
}
