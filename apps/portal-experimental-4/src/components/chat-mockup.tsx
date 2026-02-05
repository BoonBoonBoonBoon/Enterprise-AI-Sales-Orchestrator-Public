"use client";

import { useState, useEffect } from "react";
import { Bot, User, Sparkles } from "lucide-react";

interface Message {
  id: number;
  role: "ai" | "user" | "system";
  content: string;
  typing?: boolean;
}

const conversationFlow: Omit<Message, "id">[] = [
  {
    role: "system",
    content: "Luna is analyzing incoming lead from website form...",
  },
  {
    role: "ai",
    content:
      "I've received a new inquiry from Sarah Chen at TechVentures. She's interested in our Enterprise plan and asked about API integrations. I'll draft a personalized response.",
  },
  {
    role: "ai",
    content:
      "✉️ Draft ready:\n\nHi Sarah,\n\nThanks for reaching out! I'd love to walk you through our API capabilities. We support REST, GraphQL, and webhooks.\n\nWould Thursday at 2pm work for a quick call?\n\nBest,\nThe AgentFlow Team",
  },
  {
    role: "user",
    content: "Perfect, send it. Also follow up if no response in 3 days.",
  },
  {
    role: "ai",
    content:
      "Done! Email sent to sarah@techventures.io ✓\n\nI've scheduled a follow-up for Thursday if she doesn't respond. I'll personalize it based on her company's recent Series B announcement.",
  },
];

export function ChatMockup() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [currentIndex, setCurrentIndex] = useState(0);

  useEffect(() => {
    if (currentIndex < conversationFlow.length) {
      const timer = setTimeout(
        () => {
          setMessages((prev) => [
            ...prev,
            { ...conversationFlow[currentIndex], id: currentIndex },
          ]);
          setCurrentIndex((prev) => prev + 1);
        },
        currentIndex === 0 ? 1000 : 2000
      );
      return () => clearTimeout(timer);
    }
  }, [currentIndex]);

  return (
    <div className="glass rounded-2xl p-1 glow-soft">
      {/* Window Header */}
      <div className="flex items-center gap-3 px-4 py-3 border-b border-border/50">
        <div className="flex gap-1.5">
          <div className="w-3 h-3 rounded-full bg-red-500/60" />
          <div className="w-3 h-3 rounded-full bg-yellow-500/60" />
          <div className="w-3 h-3 rounded-full bg-green-500/60" />
        </div>
        <div className="flex-1 flex items-center justify-center gap-2 text-sm text-muted-foreground">
          <div className="w-6 h-6 rounded-full gradient-cta flex items-center justify-center">
            <Sparkles className="w-3 h-3 text-gray-900" />
          </div>
          <span>Luna — Email Agent</span>
          <div className="status-online ml-1" />
        </div>
      </div>

      {/* Chat Area */}
      <div className="p-4 space-y-4 min-h-[360px] max-h-[400px] overflow-y-auto">
        {messages.map((message) => (
          <div
            key={message.id}
            className={`flex gap-3 animate-fade-up ${
              message.role === "user" ? "flex-row-reverse" : ""
            }`}
          >
            {message.role !== "system" && (
              <div
                className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${
                  message.role === "ai"
                    ? "bg-primary/20 text-primary"
                    : "bg-white/10 text-white"
                }`}
              >
                {message.role === "ai" ? (
                  <Bot className="w-4 h-4" />
                ) : (
                  <User className="w-4 h-4" />
                )}
              </div>
            )}
            <div
              className={`chat-bubble max-w-[80%] ${
                message.role === "system"
                  ? "bg-transparent text-muted-foreground text-sm italic text-center w-full"
                  : message.role === "ai"
                  ? "chat-bubble-ai"
                  : "chat-bubble-user"
              }`}
            >
              <p className="text-sm whitespace-pre-line leading-relaxed">
                {message.content}
              </p>
            </div>
          </div>
        ))}

        {currentIndex < conversationFlow.length && (
          <div className="flex gap-3">
            <div className="w-8 h-8 rounded-full bg-primary/20 flex items-center justify-center flex-shrink-0">
              <Bot className="w-4 h-4 text-primary" />
            </div>
            <div className="chat-bubble chat-bubble-ai">
              <div className="flex gap-1">
                <span className="w-2 h-2 bg-primary/60 rounded-full animate-pulse" />
                <span className="w-2 h-2 bg-primary/60 rounded-full animate-pulse delay-100" />
                <span className="w-2 h-2 bg-primary/60 rounded-full animate-pulse delay-200" />
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Input Area */}
      <div className="px-4 pb-4">
        <div className="flex items-center gap-3 bg-white/5 rounded-full px-4 py-3 border border-border/50">
          <input
            type="text"
            placeholder="Ask Luna anything..."
            className="flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground"
            disabled
          />
          <button className="w-8 h-8 rounded-full gradient-cta flex items-center justify-center hover:opacity-80 transition-opacity">
            <Sparkles className="w-4 h-4 text-gray-900" />
          </button>
        </div>
      </div>
    </div>
  );
}
