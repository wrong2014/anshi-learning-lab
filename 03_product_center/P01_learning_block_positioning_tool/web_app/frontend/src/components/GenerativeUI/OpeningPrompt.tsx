import { FileText, HeartHandshake, Repeat2 } from 'lucide-react';
import type { UIBlock } from '../../types';
import styles from './OpeningPrompt.module.css';

interface Props {
  block: UIBlock;
  onStarter: (text: string) => void;
  disabled?: boolean;
}

const starterIcons = {
  opening_paper: FileText,
  opening_repeated_error: Repeat2,
  opening_help_conflict: HeartHandshake,
};

export default function OpeningPrompt({ block, onStarter, disabled = false }: Props) {
  return (
    <section className={styles.prompt} aria-label={block.title || '开始描述'}>
      <div className={styles.copy}>
        {block.title && <h3>{block.title}</h3>}
        {block.body && <p>{block.body}</p>}
      </div>

      <div className={styles.starters}>
        {(block.starters || []).map((starter) => {
          const Icon = starterIcons[starter.id as keyof typeof starterIcons] || FileText;
          return (
            <button
              key={starter.id}
              type="button"
              className={styles.starter}
              onClick={() => onStarter(starter.text)}
              disabled={disabled}
            >
              <Icon size={17} />
              <span>{starter.label}</span>
            </button>
          );
        })}
      </div>

      <p className={styles.reassurance}>你不需要一次说清楚，后面的线索我来帮你接。</p>
    </section>
  );
}
