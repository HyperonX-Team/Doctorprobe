// ChatBubble — user/assistant style bubble used on the report page.

import type { ReactNode } from 'react';

interface ChatBubbleProps {
  /** "user" renders right-aligned brand-tinted bubble; "assistant" left. */
  role: 'user' | 'assistant';
  children: ReactNode;
}

export default function ChatBubble({ role, children }: ChatBubbleProps) {
  const isUser = role === 'user';
  return (
    <div
      data-testid={`chat-bubble-${role}`}
      className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}
    >
      <div
        className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${
          isUser
            ? 'rounded-br-sm bg-brand-600 text-white'
            : 'rounded-bl-sm border border-slate-200 bg-white text-slate-800 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100'
        }`}
      >
        {children}
      </div>
    </div>
  );
}
