import { useCallback, useEffect, useState } from 'react';
import { Bot, History, MessageSquare, RefreshCw, Settings } from 'lucide-react';
import clsx from 'clsx';
import styles from './App.module.css';
import ChatContainer from './components/ChatContainer';
import { getProviderStatus, listSessions } from './api';
import type { ProviderStatus, StoredSessionSummary } from './types';

type ViewMode = 'chat' | 'history' | 'settings';

function formatTime(value: string) {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function App() {
  const [viewMode, setViewMode] = useState<ViewMode>('chat');
  const [chatKey, setChatKey] = useState(0);
  const [activeHistorySessionId, setActiveHistorySessionId] = useState<string | null>(null);
  const [sessions, setSessions] = useState<StoredSessionSummary[]>([]);
  const [sessionsLoading, setSessionsLoading] = useState(false);
  const [status, setStatus] = useState<ProviderStatus | null>(null);
  const [statusLoading, setStatusLoading] = useState(false);

  const refreshSessions = useCallback(async () => {
    setSessionsLoading(true);
    try {
      setSessions(await listSessions());
    } finally {
      setSessionsLoading(false);
    }
  }, []);

  const refreshStatus = useCallback(async () => {
    setStatusLoading(true);
    try {
      setStatus(await getProviderStatus());
    } finally {
      setStatusLoading(false);
    }
  }, []);

  useEffect(() => {
    void refreshSessions();
  }, [refreshSessions]);

  const handleNewChat = () => {
    setActiveHistorySessionId(null);
    setViewMode('chat');
    setChatKey((value) => value + 1);
  };

  const handleOpenHistory = () => {
    setViewMode('history');
    setActiveHistorySessionId(null);
    void refreshSessions();
  };

  const handleOpenSettings = () => {
    setViewMode('settings');
    setActiveHistorySessionId(null);
    void refreshStatus();
  };

  const handleSessionStarted = useCallback(() => {
    void refreshSessions();
  }, [refreshSessions]);

  const openStoredSession = (sessionId: string) => {
    setActiveHistorySessionId(sessionId);
    setViewMode('chat');
  };

  const renderMain = () => {
    if (viewMode === 'history') {
      return (
        <section className={styles.panelPage}>
          <div className={styles.panelHeader}>
            <div>
              <h2>历史记录</h2>
              <p>发送第一句话后，对话会自动保存到这里，点击即可回看。</p>
            </div>
            <button className={styles.panelButton} type="button" onClick={refreshSessions}>
              <RefreshCw size={16} />
              刷新
            </button>
          </div>

          {sessionsLoading ? (
            <p className={styles.emptyText}>正在读取历史会话...</p>
          ) : sessions.length ? (
            <div className={styles.sessionList}>
              {sessions.map((session) => (
                <button
                  key={session.session_id}
                  className={styles.sessionItem}
                  type="button"
                  onClick={() => openStoredSession(session.session_id)}
                >
                  <div>
                    <strong>{session.title}</strong>
                    <p>{session.preview}</p>
                  </div>
                  <span>{formatTime(session.updated_at)}</span>
                  <em>{session.is_complete ? '已完成' : `${session.turn_count} 轮`}</em>
                </button>
              ))}
            </div>
          ) : (
            <p className={styles.emptyText}>还没有历史会话。发出第一句话后，这里会自动出现。</p>
          )}
        </section>
      );
    }

    if (viewMode === 'settings') {
      return (
        <section className={styles.panelPage}>
          <div className={styles.panelHeader}>
            <div>
              <h2>设置</h2>
              <p>这里先放运行状态，后面再接模型切换、提示词版本和日志策略。</p>
            </div>
            <button className={styles.panelButton} type="button" onClick={refreshStatus}>
              <RefreshCw size={16} />
              刷新
            </button>
          </div>

          {statusLoading ? (
            <p className={styles.emptyText}>正在读取设置...</p>
          ) : status ? (
            <div className={styles.settingsGrid}>
              <article>
                <span>运行模式</span>
                <strong>{status.mode}</strong>
              </article>
              <article>
                <span>默认文本模型</span>
                <strong>{status.default_text_provider}</strong>
              </article>
              <article>
                <span>DeepSeek</span>
                <strong>{status.deepseek_ready ? '已配置' : '未配置'}</strong>
                <p>{status.deepseek_model || '未设置模型'}</p>
              </article>
              <article>
                <span>豆包</span>
                <strong>{status.doubao_ready ? '已配置' : '未配置'}</strong>
                <p>{status.doubao_text_model || '未设置文本模型'}</p>
              </article>
            </div>
          ) : (
            <p className={styles.emptyText}>还没有读取到设置状态。</p>
          )}
        </section>
      );
    }

    return (
      <ChatContainer
        key={activeHistorySessionId || chatKey}
        sessionToLoad={activeHistorySessionId}
        onSessionStarted={handleSessionStarted}
      />
    );
  };

  return (
    <div className={clsx(styles.appContainer, 'glass-panel')}>
      <aside className={styles.sidebar}>
        <div className={styles.logo}>
          <div className={styles.iconWrapper}>
            <Bot size={24} />
          </div>
          理科学习卡点定位
        </div>

        <nav className={styles.nav}>
          <button
            type="button"
            className={clsx(styles.navItem, viewMode === 'chat' && !activeHistorySessionId && styles.active)}
            onClick={handleNewChat}
          >
            <MessageSquare size={18} />
            <span>新对话</span>
          </button>
          <button
            type="button"
            className={clsx(styles.navItem, (viewMode === 'history' || activeHistorySessionId) && styles.active)}
            onClick={handleOpenHistory}
          >
            <History size={18} />
            <span>历史记录</span>
          </button>
          <button
            type="button"
            className={clsx(styles.navItem, viewMode === 'settings' && styles.active)}
            onClick={handleOpenSettings}
          >
            <Settings size={18} />
            <span>设置</span>
          </button>
        </nav>
      </aside>

      <main className={styles.mainContent}>{renderMain()}</main>

      <nav className={styles.mobileNav} aria-label="主要功能">
        <button
          type="button"
          className={clsx(styles.mobileNavItem, viewMode === 'chat' && !activeHistorySessionId && styles.active)}
          onClick={handleNewChat}
        >
          <MessageSquare size={18} />
          <span>新对话</span>
        </button>
        <button
          type="button"
          className={clsx(styles.mobileNavItem, (viewMode === 'history' || activeHistorySessionId) && styles.active)}
          onClick={handleOpenHistory}
        >
          <History size={18} />
          <span>历史</span>
        </button>
        <button
          type="button"
          className={clsx(styles.mobileNavItem, viewMode === 'settings' && styles.active)}
          onClick={handleOpenSettings}
        >
          <Settings size={18} />
          <span>设置</span>
        </button>
      </nav>
    </div>
  );
}

export default App;
