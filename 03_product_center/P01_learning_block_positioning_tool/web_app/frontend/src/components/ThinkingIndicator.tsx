import styles from './ThinkingIndicator.module.css';

interface ThinkingIndicatorProps {
  text?: string;
}

export default function ThinkingIndicator({ text = "P01 正在分析逻辑断点..." }: ThinkingIndicatorProps) {
  return (
    <div className={styles.container}>
      <div className={styles.text}>{text}</div>
      <div className={styles.dots}>
        <div className={styles.dot}></div>
        <div className={styles.dot}></div>
        <div className={styles.dot}></div>
      </div>
    </div>
  );
}
