import React, { useEffect, useRef, useState } from 'react';
import { Loader2, Send } from 'lucide-react';
import styles from './ChatContainer.module.css';
import MessageBubble from './MessageBubble';
import { startSession, submitAnswer } from '../api';
import type { APIAnswerRequest, APIAnswerResponse, APIStartResponse, Message, UIBlock } from '../types';

function createMessageId(prefix: string) {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return `${prefix}-${crypto.randomUUID()}`;
  }
  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function getLatestUIBlock(messages: Message[]): UIBlock | null {
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    const message = messages[index];
    if (message.role === 'agent' && message.uiBlock) return message.uiBlock;
  }
  return null;
}

function mapAgentMessages(res: APIStartResponse | APIAnswerResponse, prefix: string): Message[] {
  const agentMessages = res.agent_messages || [];
  if (!agentMessages.length && res.result) {
    return [
      {
        id: createMessageId(`${prefix}-result`),
        role: 'agent',
        content: '我先把这次卡点整理成一个可执行的判断。',
        result: res.result,
      },
    ];
  }

  return agentMessages.map((msg, index) => ({
    id: createMessageId(`${prefix}-${index}`),
    role: 'agent' as const,
    content: msg.text || '',
    uiBlock: msg.ui_block || undefined,
    result: index === agentMessages.length - 1 ? res.result || undefined : undefined,
  }));
}

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

  useEffect(() => {
    setIsLoading(true);
    startSession()
      .then((res) => {
        setSessionId(res.session_id);
        setIsComplete(res.is_complete);
        setMessages(mapAgentMessages(res, 'start'));
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

  const sendToAgent = async (payload: Omit<APIAnswerRequest, 'session_id'>) => {
    if (!sessionId || isLoading || isComplete) return;

    setIsLoading(true);
    try {
      const res = await submitAnswer({
        session_id: sessionId,
        ...payload,
      });
      setSessionId(res.session_id);
      setIsComplete(res.is_complete);
      setMessages((prev) => [...prev, ...mapAgentMessages(res, 'agent')]);
    } catch (err) {
      console.error(err);
      setMessages((prev) => [
        ...prev,
        {
          id: createMessageId('error'),
          role: 'agent',
          content: '这轮分析没有成功。你可以换一种说法再发一次，或者稍后重试。',
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSendText = async () => {
    const text = inputValue.trim();
    if (!text || !sessionId || isLoading || isComplete) return;

    setInputValue('');
    setMessages((prev) => [
      ...prev,
      { id: createMessageId('user'), role: 'user', content: text },
    ]);

    const activeBlock = getLatestUIBlock(messages);
    await sendToAgent({ ui_block_id: activeBlock?.id, free_text: text });
  };

  const handleOptionSelect = async (blockId: string, optionId: string, optionLabel: string) => {
    if (!sessionId || isLoading || isComplete) return;

    setMessages((prev) => [
      ...prev,
      { id: createMessageId('user'), role: 'user', content: optionLabel },
    ]);

    await sendToAgent({
      ui_block_id: blockId,
      selected_option_ids: [optionId],
      selected_labels: [optionLabel],
    });
  };

  const handleMultiSelect = async (blockId: string, optionIds: string[], optionLabels: string[]) => {
    if (!sessionId || isLoading || isComplete) return;

    setMessages((prev) => [
      ...prev,
      {
        id: createMessageId('user'),
        role: 'user',
        content: optionLabels.length ? optionLabels.join('、') : '先跳过',
      },
    ]);

    await sendToAgent({
      ui_block_id: blockId,
      selected_option_ids: optionIds,
      selected_labels: optionLabels,
    });
  };

  const handleCardFreeText = async (text: string) => {
    if (!sessionId || isLoading || isComplete || !text.trim()) return;

    setMessages((prev) => [
      ...prev,
      { id: createMessageId('user'), role: 'user', content: text.trim() },
    ]);

    const activeBlock = getLatestUIBlock(messages);
    await sendToAgent({ ui_block_id: activeBlock?.id, free_text: text.trim() });
  };

  const handleKeyPress = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      void handleSendText();
    }
  };

  const lastAgentBlockIdx = [...messages]
    .map((message, index) => (message.role === 'agent' && message.uiBlock ? index : -1))
    .filter((index) => index >= 0)
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
        {messages.map((msg, index) => (
          <MessageBubble
            key={msg.id}
            message={msg}
            onOptionSelect={handleOptionSelect}
            onMultiSelect={handleMultiSelect}
            onFreeText={handleCardFreeText}
            isLatestAgentMsg={index === lastAgentBlockIdx}
          />
        ))}
        {isLoading && (
          <div className={styles.loadingLine}>
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
            placeholder={isComplete ? '本次定位已完成' : '像发微信一样描述你的困惑...'}
            value={inputValue}
            onChange={(event) => setInputValue(event.target.value)}
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
