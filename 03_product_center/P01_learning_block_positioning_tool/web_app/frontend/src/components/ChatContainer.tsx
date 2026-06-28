import React, { useEffect, useRef, useState } from 'react';
import { Loader2, Send } from 'lucide-react';
import styles from './ChatContainer.module.css';
import MessageBubble from './MessageBubble';
import { getSession, startSession, submitAnswer } from '../api';
import type {
  APIAnswerRequest,
  APIAnswerResponse,
  APIStartResponse,
  Message,
  StoredMessage,
  UIBlock,
} from '../types';

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

function mapStoredMessages(storedMessages: StoredMessage[]): Message[] {
  return storedMessages.map((message, index) => ({
    id: createMessageId(`history-${index}`),
    role: message.role,
    content: message.content,
    uiBlock: message.uiBlock || undefined,
    result: message.result || undefined,
  }));
}

interface Props {
  sessionToLoad?: string | null;
  onSessionStarted?: (sessionId: string) => void;
}

export default function ChatContainer({ sessionToLoad = null, onSessionStarted }: Props) {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isComplete, setIsComplete] = useState(false);
  const [isReadOnlyHistory, setIsReadOnlyHistory] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);

  useEffect(() => {
    setIsLoading(true);
    setMessages([]);
    setInputValue('');

    if (sessionToLoad) {
      setIsReadOnlyHistory(true);
      getSession(sessionToLoad)
        .then((res) => {
          setSessionId(res.session_id);
          setIsComplete(true);
          setMessages(mapStoredMessages(res.messages || []));
        })
        .catch((err) => {
          console.error(err);
          setMessages([
            {
              id: createMessageId('history-error'),
              role: 'agent',
              content: '这条历史会话没有加载成功。可以回到历史记录再试一次。',
            },
          ]);
        })
        .finally(() => {
          setIsLoading(false);
        });
      return;
    }

    setIsReadOnlyHistory(false);
    setIsComplete(false);
    startSession()
      .then((res) => {
        setSessionId(res.session_id);
        onSessionStarted?.(res.session_id);
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
  }, [onSessionStarted, sessionToLoad]);

  const sendToAgent = async (payload: Omit<APIAnswerRequest, 'session_id'>) => {
    if (!sessionId || isLoading || isComplete || isReadOnlyHistory) return;

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
    if (!text || !sessionId || isLoading || isComplete || isReadOnlyHistory) return;

    setInputValue('');
    setMessages((prev) => [
      ...prev,
      { id: createMessageId('user'), role: 'user', content: text },
    ]);

    const activeBlock = getLatestUIBlock(messages);
    await sendToAgent({ ui_block_id: activeBlock?.id, free_text: text });
  };

  const handleOptionSelect = async (blockId: string, optionId: string, optionLabel: string) => {
    if (!sessionId || isLoading || isComplete || isReadOnlyHistory) return;

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
    if (!sessionId || isLoading || isComplete || isReadOnlyHistory) return;

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
    if (!sessionId || isLoading || isComplete || isReadOnlyHistory || !text.trim()) return;

    setMessages((prev) => [
      ...prev,
      { id: createMessageId('user'), role: 'user', content: text.trim() },
    ]);

    const activeBlock = getLatestUIBlock(messages);
    await sendToAgent({ ui_block_id: activeBlock?.id, free_text: text.trim() });
  };

  const handlePromptStarter = (text: string) => {
    if (isLoading || isComplete || isReadOnlyHistory) return;
    setInputValue(text);
    requestAnimationFrame(() => {
      inputRef.current?.focus();
    });
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

  const placeholder = isReadOnlyHistory
    ? '历史会话只读'
    : isComplete
      ? '本次定位已完成'
      : '像发微信一样描述你的困惑...';

  return (
    <div className={styles.chatContainer}>
      <header className={styles.header}>
        <div>
          <h2 className={styles.title}>理科学习卡点定位</h2>
          <p className={styles.subtitle}>
            {isReadOnlyHistory ? '历史会话 · 只读查看' : 'AI 对话式智能体 · Powered by DeepSeek'}
          </p>
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
            onPromptStarter={handlePromptStarter}
            isLatestAgentMsg={!isReadOnlyHistory && index === lastAgentBlockIdx}
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
            ref={inputRef}
            type="text"
            className={styles.input}
            placeholder={placeholder}
            value={inputValue}
            onChange={(event) => setInputValue(event.target.value)}
            onKeyDown={handleKeyPress}
            disabled={isComplete || isLoading || isReadOnlyHistory}
          />
          <button
            className={styles.sendButton}
            onClick={handleSendText}
            disabled={!inputValue.trim() || isComplete || isLoading || isReadOnlyHistory}
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
