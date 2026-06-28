
import clsx from 'clsx';
import { Bot } from 'lucide-react';
import styles from './MessageBubble.module.css';
import type { Message } from '../types';
import SingleChoiceCard from './GenerativeUI/SingleChoiceCard';
import ResultCard from './GenerativeUI/ResultCard';
import OpeningPrompt from './GenerativeUI/OpeningPrompt';

interface Props {
  message: Message;
  onOptionSelect?: (blockId: string, optionId: string, optionLabel: string) => void;
  onMultiSelect?: (blockId: string, optionIds: string[], optionLabels: string[]) => void;
  onFreeText?: (text: string) => void;
  onPromptStarter?: (text: string) => void;
  isLatestAgentMsg?: boolean;
}

export default function MessageBubble({
  message,
  onOptionSelect,
  onMultiSelect,
  onFreeText,
  onPromptStarter,
  isLatestAgentMsg,
}: Props) {
  const isUser = message.role === 'user';

  const renderUIBlock = () => {
    if (!message.uiBlock) return null;

    switch (message.uiBlock.type) {
      case 'opening_prompt':
        return (
          <OpeningPrompt
            block={message.uiBlock}
            onStarter={(text) => onPromptStarter?.(text)}
            disabled={!isLatestAgentMsg}
          />
        );
      case 'single_choice':
      case 'multi_choice':
        return (
          <SingleChoiceCard
            block={message.uiBlock}
            onSelect={(optId, optLabel) => {
              if (onOptionSelect) {
                onOptionSelect(message.uiBlock!.id, optId, optLabel);
              }
            }}
            onMultiSelect={(optIds, optLabels) => {
              if (onMultiSelect) {
                onMultiSelect(message.uiBlock!.id, optIds, optLabels);
              }
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
        <div className={clsx(styles.avatar, styles.agentAvatar, message.result && styles.resultAvatar)}>
          <Bot size={18} />
        </div>
      )}

      <div
        className={clsx(
          styles.messageStack,
          isUser && styles.userStack,
          message.result && styles.resultStack,
        )}
      >
        {message.content && (
          <div className={clsx(styles.bubble, isUser ? styles.userBubble : styles.agentBubble)}>
            {message.content}
          </div>
        )}

        {!isUser && renderUIBlock()}
        {!isUser && renderResult()}
      </div>
    </div>
  );
}
