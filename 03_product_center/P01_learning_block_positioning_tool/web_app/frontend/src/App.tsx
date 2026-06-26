import React from 'react';
import { Bot, History, Settings, MessageSquare } from 'lucide-react';
import clsx from 'clsx';
import styles from './App.module.css';
import ChatContainer from './components/ChatContainer';

function App() {
  return (
    <div className={clsx(styles.appContainer, 'glass-panel')}>
      {/* Sidebar */}
      <aside className={styles.sidebar}>
        <div className={styles.logo}>
          <div className={styles.iconWrapper}>
            <Bot size={24} />
          </div>
          理科学习卡点定位
        </div>

        <nav className={styles.nav}>
          <div className={clsx(styles.navItem, styles.active)}>
            <MessageSquare size={18} />
            <span>新对话</span>
          </div>
          <div className={styles.navItem}>
            <History size={18} />
            <span>历史记录</span>
          </div>
          <div className={styles.navItem}>
            <Settings size={18} />
            <span>设置</span>
          </div>
        </nav>
      </aside>

      {/* Main Chat Area */}
      <main className={styles.mainContent}>
        <ChatContainer />
      </main>
    </div>
  );
}

export default App;
