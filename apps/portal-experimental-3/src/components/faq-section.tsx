'use client';

import { useState } from 'react';
import { ChevronDown } from 'lucide-react';

interface FaqItem {
  question: string;
  answer: string;
}

const faqs: FaqItem[] = [
  {
    question: "How long does it take to get started?",
    answer: "Most teams are up and running within a day. We'll connect your inbox, configure your approval settings, and you're ready to go. No complex integrations required.",
  },
  {
    question: "Will AI responses sound robotic?",
    answer: "Not at all. Our AI learns from your existing email threads and adapts to your company's voice. Every draft sounds like it came from your team—because you approve it before it sends.",
  },
  {
    question: "Do I lose control over what gets sent?",
    answer: "Never. You set the rules for what requires approval. Critical accounts, new leads, or specific topics can all require human review. You're always in the driver's seat.",
  },
  {
    question: "Is my data secure?",
    answer: "Absolutely. We use enterprise-grade encryption, SOC 2 compliant infrastructure, and your data is never used to train external models. Your emails stay yours.",
  },
  {
    question: "What if the AI makes a mistake?",
    answer: "Every response is a draft first. You review, edit if needed, and approve. Think of it as a very smart assistant that prepares your replies—you always have final say.",
  },
];

export default function FaqSection() {
  const [openIndex, setOpenIndex] = useState<number | null>(0);

  return (
    <div className="space-y-3">
      {faqs.map((faq, index) => {
        const isOpen = openIndex === index;
        return (
          <div
            key={index}
            className="card-soft overflow-hidden transition-all"
          >
            <button
              onClick={() => setOpenIndex(isOpen ? null : index)}
              className="w-full flex items-center justify-between p-5 text-left hover:bg-muted/30 transition-colors"
            >
              <span className="font-medium text-foreground pr-4">{faq.question}</span>
              <ChevronDown
                className={`h-5 w-5 text-muted-foreground transition-transform flex-shrink-0 ${isOpen ? 'rotate-180' : ''}`}
              />
            </button>
            <div
              className={`overflow-hidden transition-all duration-300 ${isOpen ? 'max-h-48 opacity-100' : 'max-h-0 opacity-0'}`}
            >
              <div className="px-5 pb-5 text-muted-foreground leading-relaxed">
                {faq.answer}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
