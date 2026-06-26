import React, { useState, useRef, useEffect } from 'react';
import { Send, Loader2 } from 'lucide-react';
import styles from './ChatContainer.module.css';
import MessageBubble from './MessageBubble';
import { startSession, submitAnswer } from '../api';
import type { Message, ResultData } from '../types';

export default function ChatContainer() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isComplete, setIsComplete] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);

  // 启动会话
  useEffect(() => {
    setIsLoading(true);
    startSession()
      .then((res) => {
        setSessionId(res.session_id);
        setIsComplete(res.is_complete);

        // 将智能体的消息添加到对话中
        const agentMsgs = res.agent_messages || [];
        const newMessages: Message[] = agentMsgs.map((msg, idx) => ({
          id: `start-${idx}-${Date.now()}`,
          role: 'agent' as const,
          content: msg.text || '',
          uiBlock: msg.ui_block || undefined,
          result: res.result || undefined,
        }));
        setMessages(newMessages);
      })
      .catch((err) => {
        console.error(err);
        setMessages([
          {
            id: 'error',
            role: 'agent',
            content: '连接服务器失败，请确认后端服务已启动（python web_app/server.py）。',
          },
        ]);
      })
      .finally(() => {
        setIsLoading(false);
      });
  }, []);

  // 发送文本消息
  const handleSendText = async () => {
    if (!inputValue.trim() || !sessionId || isLoading || isComplete) return;

    const text = inputValue.trim();
    setInputValue('');

    // 添加用户消息气泡
    setMessages((prev) => [
      ...prev,
      { id: `user-${Date.now()}`, role: 'user', content: text },
    ]);

    await sendToAgent({ free_text: text });
  };

  // 点击选项（单选）
  const handleOptionSelect = async (blockId: string, optionId: string, optionLabel: string) => {
    if (!sessionId || isLoading || isComplete) return;

    setMessages((prev) => [
      ...prev,
      { id: `user-${Date.now()}`, role: 'user', content: optionLabel },
    ]);

    await sendToAgent({
      selected_option_ids: [optionId],
      selected_labels: [optionLabel],
    });
  };

  // 多选确认
  const handleMultiSelect = async (blockId: string, optionIds: string[], optionLabels: string[]) => {
    if (!sessionId || isLoading || isComplete) return;

    setMessages((prev) => [
      ...prev,
      { id: `user-${Date.now()}`, role: 'user', content: optionLabels.join('、') },
    ]);

    await sendToAgent({
      selected_option_ids: optionIds,
      selected_labels: optionLabels,
    });
  };

  // 卡片上的"其他"自由输入（直接作为文本发送，不需要再弹一轮）
  const handleCardFreeText = async (text: string) => {
    if (!sessionId || isLoading || isComplete || !text.trim()) return;

    setMessages((prev) => [
      ...prev,
      { id: `user-${Date.now()}`, role: 'user', content: text },
    ]);

    await sendToAgent({ free_text: text });
  };

  // 找到最后一条带 uiBlock 的 agent 消息的 index
  const lastAgentBlockIdx = [...messages]
    .map((m, i) => (m.role === 'agent' && m.uiBlock ? i : -1))
    .filter((i) => i >= 0)
    .pop();

  return (
    <div className={styles.chatContainer}>
      <header className={styles.header}>
        <div>
          <h2 className={styles.title}>理科学习卡点定位</h2>
          <p className={styles.subtitle}>AI 对话式智能体 · Powered by DeepSeek</p>
        </div>
      </header>

      <div className={styles.messageList}>
        {messages.map((msg, idx) => (
          <MessageBubble
            key={msg.id}
            message={msg}
            onOptionSelect={handleOptionSelect}
            onMultiSelect={handleMultiSelect}
            onFreeText={handleCardFreeText}
            isLatestAgentMsg={idx === lastAgentBlockIdx}
          />
        ))}
        {isLoading && (
          <div
            style={{
              display: 'flex',
              gap: '8px',
              color: 'var(--color-text-muted)',
              fontSize: '0.9rem',
              alignItems: 'center',
              padding: '8px 0',
            }}
          >
            <Loader2 size={16} className="spin" /> 智能体正在分析你的描述...
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <div className={styles.inputArea}>
        <div className={styles.inputWrapper}>
          <input
            type="text"
            className={styles.input}
            placeholder={
              isComplete
                ? '本次定位已完成'
                : '像发微信一样描述你的困惑...'
            }
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={handleKeyPress}
            disabled={isComplete || isLoading}
          />
          <button
            className={styles.sendButton}
            onClick={handleSendText}
            disabled={!inputValue.trim() || isComplete || isLoading}
          >
            <Send size={18} />
          </button>
        </div>
      </div>

      <style
        dangerouslySetInnerHTML={{
          __html: `
        .spin { animation: spin 1s linear infinite; }
        @keyframes spin { 100% { transform: rotate(360deg); } }
      `,
        }}
      />
    </div>
  );
}
