import { useState, useRef, useEffect } from 'react';
import type { KeyboardEvent } from 'react';
import { Send } from 'lucide-react';
import styles from './ChatContainer.module.css';
import MessageBubble from './MessageBubble';
import ThinkingIndicator from './ThinkingIndicator';
import { startSession, submitAnswer } from '../api';
import type { Message } from '../types';

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
  const handleOptionSelect = async (_blockId: string, optionId: string, optionLabel: string) => {
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
  const handleMultiSelect = async (_blockId: string, optionIds: string[], optionLabels: string[]) => {
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

  // 统一的发送逻辑
  const sendToAgent = async (params: {
    free_text?: string;
    selected_option_ids?: string[];
    selected_labels?: string[];
  }) => {
    if (!sessionId) return;

    setIsLoading(true);
    try {
      const res = await submitAnswer({
        session_id: sessionId,
        ...params,
      });

      const rawMsgs = res.agent_messages || [];
      const agentMessages: Message[] = rawMsgs.map((msg, idx) => ({
        id: `agent-${Date.now()}-${idx}`,
        role: 'agent' as const,
        content: msg.text || '',
        uiBlock: msg.ui_block || undefined,
      }));

      if (res.result && agentMessages.length > 0) {
        agentMessages[agentMessages.length - 1].result = res.result;
      }

      setMessages((prev) => [...prev, ...agentMessages]);
      setIsComplete(res.is_complete);
    } catch (err) {
      console.error(err);
      setMessages((prev) => [
        ...prev,
        {
          id: `error-${Date.now()}`,
          role: 'agent',
          content: '网络异常，请稍后重试。',
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyPress = (e: KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendText();
    }
  };

  // 找到最后一条带 uiBlock 的 agent 消息的 index
  const lastAgentBlockIdx = [...messages]
    .map((m, i) => (m.role === 'agent' && m.uiBlock ? i : -1))
    .filter((i) => i >= 0)
    .pop();

  const userTurns = messages.filter((m) => m.role === 'user').length;
  let activeStep = 0;
  if (isComplete) {
    activeStep = 3;
  } else if (userTurns >= 2) {
    activeStep = 2;
  } else if (userTurns === 1) {
    activeStep = 1;
  } else {
    activeStep = 0;
  }

  return (
    <div className={styles.chatContainer}>
      <header className={styles.header}>
        <div className={styles.headerTop}>
          <div>
            <h2 className={styles.title}>理科学习卡点定位</h2>
            <p className={styles.subtitle}>AI 对话式智能体 · Powered by DeepSeek</p>
          </div>
        </div>
        <div className={styles.progressContainer}>
          {[0, 1, 2, 3].map((stepIndex) => (
            <div
              key={stepIndex}
              className={`${styles.progressStep} ${
                stepIndex < activeStep
                  ? styles.progressStepCompleted
                  : stepIndex === activeStep
                  ? styles.progressStepActive
                  : ''
              }`}
            />
          ))}
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
        {isLoading && <ThinkingIndicator />}
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

      {/* 移除原本内联的 spin 样式，因为已经换成了 ThinkingIndicator */}
    </div>
  );
}
