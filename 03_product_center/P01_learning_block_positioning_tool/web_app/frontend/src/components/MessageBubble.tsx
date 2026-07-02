import { useState, useEffect } from 'react';
import clsx from 'clsx';
import { Bot } from 'lucide-react';
import styles from './MessageBubble.module.css';
import type { Message } from '../types';
import SingleChoiceCard from './GenerativeUI/SingleChoiceCard';
import SubjectPicker from './GenerativeUI/SubjectPicker';
import ResultCard from './GenerativeUI/ResultCard';

interface Props {
  message: Message;
  onOptionSelect?: (blockId: string, optionId: string, optionLabel: string) => void;
  onMultiSelect?: (blockId: string, optionIds: string[], optionLabels: string[]) => void;
  onFreeText?: (text: string) => void;
  isLatestAgentMsg?: boolean;
}

export default function MessageBubble({ message, onOptionSelect, onMultiSelect, onFreeText, isLatestAgentMsg }: Props) {
  const isUser = message.role === 'user';

  const [displayedContent, setDisplayedContent] = useState('');
  const [isTyping, setIsTyping] = useState(false);

  useEffect(() => {
    if (!isUser && isLatestAgentMsg && message.content) {
      setIsTyping(true);
      setDisplayedContent('');
      let i = 0;
      const text = message.content;
      const interval = setInterval(() => {
        setDisplayedContent(text.slice(0, i + 1));
        i++;
        if (i >= text.length) {
          clearInterval(interval);
          setIsTyping(false);
        }
      }, 30);
      return () => clearInterval(interval);
    } else {
      setDisplayedContent(message.content || '');
      setIsTyping(false);
    }
  }, [message.content, isUser, isLatestAgentMsg]);

  const renderUIBlock = () => {
    if (!message.uiBlock) return null;

    switch (message.uiBlock.type) {
      case 'subject_picker':
        return (
          <SubjectPicker
            block={message.uiBlock}
            onSelect={(optId, optLabel) => {
              if (onOptionSelect) onOptionSelect(message.uiBlock!.id, optId, optLabel);
            }}
            disabled={!isLatestAgentMsg}
          />
        );

      case 'single_choice':
      case 'multi_choice':
        return (
          <SingleChoiceCard
            block={message.uiBlock}
            onSelect={(optId, optLabel) => {
              if (onOptionSelect) onOptionSelect(message.uiBlock!.id, optId, optLabel);
            }}
            onMultiSelect={(optIds, optLabels) => {
              if (onMultiSelect) onMultiSelect(message.uiBlock!.id, optIds, optLabels);
            }}
            onFreeText={onFreeText}
            disabled={!isLatestAgentMsg}
          />
        );

      default:
        return null;
    }
  };

  const renderResult = () => {
    if (!message.result) return null;
    return <ResultCard data={message.result} />;
  };

  return (
    <div className={clsx(styles.bubbleContainer, isUser ? styles.userContainer : styles.agentContainer)}>
      {!isUser && (
        <div className={clsx(styles.avatar, styles.agentAvatar)}>
          <Bot size={18} />
        </div>
      )}

      <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', maxWidth: '80%' }}>
        {message.content && (
          <div className={clsx(styles.bubble, isUser ? styles.userBubble : styles.agentBubble)}>
            {displayedContent}
          </div>
        )}

        {!isUser && !isTyping && renderUIBlock()}
        {!isUser && !isTyping && renderResult()}
      </div>
    </div>
  );
}
