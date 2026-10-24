'use client';

import React, { useState, useRef, useEffect } from 'react';
import {
  MessageSquareCode,
  Send,
  Bot,
  User,
  ShieldCheck,
  RotateCcw,
  Boxes,
  Truck,
  Calculator,
  Copy,
  Check,
  ExternalLink,
} from 'lucide-react';
import { api } from '@/lib/api';
import { PageHeader } from '@/components/common/PageHeader';

interface ChatMessage {
  id: string;
  sender: 'user' | 'agent';
  text: string;
  timestamp: string;
}

export const AgentChatView: React.FC = () => {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'init-1',
      sender: 'agent',
      text:
        'Hello! I am StockWise Coordinator, your autonomous inventory and procurement agent.\n\n' +
        'You can ask me to analyze stock, compare suppliers, or plan restocks:\n' +
        '• "Check my inventory"\n' +
        '• "Compare suppliers for urgent shortages"\n' +
        '• "Create a restocking plan with budget ₹25,000"\n' +
        '• "Approve order PO-XXXX"\n' +
        '• "Simulate placing order PO-XXXX"',
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    },
  ]);
  const [inputText, setInputText] = useState<string>('');
  const [isSending, setIsSending] = useState<boolean>(false);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSend = async (textToSend?: string) => {
    const text = (textToSend || inputText).trim();
    if (!text || isSending) return;

    const userMsg: ChatMessage = {
      id: `user-${Date.now()}`,
      sender: 'user',
      text,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInputText('');
    setIsSending(true);

    try {
      const res = await api.sendChatCommand(text);
      const agentMsg: ChatMessage = {
        id: `agent-${Date.now()}`,
        sender: 'agent',
        text: res.reply,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };
      setMessages((prev) => [...prev, agentMsg]);
    } catch (err: any) {
      const errorMsg: ChatMessage = {
        id: `err-${Date.now()}`,
        sender: 'agent',
        text: `Error contacting procurement engine: ${err.message}`,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setIsSending(false);
    }
  };

  const copyToClipboard = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const quickPrompts = [
    { label: 'Check Inventory Deficit', query: 'Check my inventory' },
    { label: 'Compare Supplier Quotes', query: 'Compare suppliers for urgent shortages' },
    { label: 'Plan Restock (₹25k)', query: 'Create a restocking plan with budget ₹25,000' },
  ];

  return (
    <div className="p-6 md:p-8 space-y-6 max-w-5xl mx-auto flex flex-col h-[calc(100vh-3.5rem)]">
      {/* Header */}
      <PageHeader
        title="Autonomous Agent Workspace"
        description="Direct conversational interface to the Fetch.ai uAgents Coordinator. Deterministic fallback parser operates even when external LLMs are unreachable."
        badge="Fetch.ai uAgent"
      />

      {/* Main Chat Frame */}
      <div className="flex-1 bg-white border border-slate-200/90 rounded-xl shadow-xs flex flex-col min-h-0 overflow-hidden">
        {/* Messages Scroll Area */}
        <div className="flex-1 overflow-y-auto p-6 space-y-5">
          {messages.map((msg) => {
            const isUser = msg.sender === 'user';
            // Extract any PO IDs in response for easy copying
            const poMatches = msg.text.match(/PO-[A-Z0-9]+/g);

            return (
              <div
                key={msg.id}
                className={`flex gap-3.5 ${isUser ? 'justify-end' : 'justify-start'}`}
              >
                {!isUser && (
                  <div className="w-8 h-8 rounded-lg bg-blue-600 text-white flex items-center justify-center shrink-0 shadow-xs">
                    <Bot className="w-4 h-4" />
                  </div>
                )}

                <div
                  className={`max-w-2xl rounded-xl p-4 text-xs leading-relaxed space-y-2 ${
                    isUser
                      ? 'bg-blue-600 text-white shadow-xs'
                      : 'bg-slate-50 border border-slate-200/80 text-slate-800'
                  }`}
                >
                  <div className="whitespace-pre-wrap font-sans">{msg.text}</div>

                  {/* Copyable PO badges if mentioned */}
                  {poMatches && !isUser && (
                    <div className="pt-2 border-t border-slate-200/60 flex flex-wrap items-center gap-2">
                      <span className="text-[10px] text-slate-400">Referenced Orders:</span>
                      {poMatches.map((po) => (
                        <button
                          key={po}
                          onClick={() => copyToClipboard(po, `${msg.id}-${po}`)}
                          className="inline-flex items-center gap-1 font-mono font-bold text-[11px] px-2 py-0.5 rounded bg-white border border-slate-200 text-blue-700 hover:bg-blue-50 transition-colors"
                        >
                          {copiedId === `${msg.id}-${po}` ? (
                            <Check className="w-3 h-3 text-emerald-600" />
                          ) : (
                            <Copy className="w-3 h-3 text-slate-400" />
                          )}
                          <span>{po}</span>
                        </button>
                      ))}
                    </div>
                  )}

                  <div
                    className={`text-[10px] text-right font-mono ${
                      isUser ? 'text-blue-100' : 'text-slate-400'
                    }`}
                  >
                    {msg.timestamp}
                  </div>
                </div>

                {isUser && (
                  <div className="w-8 h-8 rounded-lg bg-slate-800 text-white flex items-center justify-center shrink-0 text-xs font-bold shadow-xs">
                    <User className="w-4 h-4" />
                  </div>
                )}
              </div>
            );
          })}

          {isSending && (
            <div className="flex gap-3.5 justify-start">
              <div className="w-8 h-8 rounded-lg bg-blue-600 text-white flex items-center justify-center shrink-0">
                <Bot className="w-4 h-4" />
              </div>
              <div className="bg-slate-50 border border-slate-200/80 rounded-xl p-4 text-xs text-slate-500 flex items-center gap-2">
                <span className="w-3 h-3 border-2 border-slate-400 border-t-blue-600 rounded-full animate-spin" />
                <span>StockWise Agent is analyzing inventory and solving procurement...</span>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Quick Suggestion Pills */}
        <div className="px-5 py-2.5 bg-slate-50/80 border-t border-slate-100 flex items-center gap-2 overflow-x-auto">
          <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider shrink-0">
            Suggested:
          </span>
          {quickPrompts.map((p, idx) => (
            <button
              key={idx}
              onClick={() => handleSend(p.query)}
              disabled={isSending}
              className="px-2.5 py-1 rounded-full bg-white border border-slate-200 text-[11px] font-medium text-slate-700 hover:border-blue-300 hover:text-blue-700 hover:bg-blue-50/50 whitespace-nowrap transition-colors shadow-2xs"
            >
              {p.label}
            </button>
          ))}
        </div>

        {/* Input Bar */}
        <div className="p-4 bg-white border-t border-slate-200/80">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleSend();
            }}
            className="flex items-center gap-2.5"
          >
            <input
              type="text"
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              placeholder="Ask agent: 'Check my inventory', 'Compare suppliers', 'Create plan with budget ₹20,000'..."
              disabled={isSending}
              className="flex-1 bg-slate-50 border border-slate-200 rounded-lg px-3.5 py-2 text-xs text-slate-800 placeholder:text-slate-400 focus:outline-none focus:border-blue-500 focus:bg-white transition-all"
            />
            <button
              type="submit"
              disabled={isSending || !inputText.trim()}
              className="px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold shadow-xs transition-colors flex items-center gap-1.5 disabled:opacity-50"
            >
              <Send className="w-3.5 h-3.5" />
              <span>Send</span>
            </button>
          </form>
        </div>
      </div>
    </div>
  );
};
