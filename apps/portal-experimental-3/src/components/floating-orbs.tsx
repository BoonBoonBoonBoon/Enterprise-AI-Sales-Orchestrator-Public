'use client';

import { useEffect, useState } from 'react';

interface Orb {
  id: number;
  x: number;
  y: number;
  size: number;
  color: string;
  delay: number;
}

const orbColors = [
  'hsl(221 83% 53% / 0.15)', // Blue
  'hsl(262 83% 58% / 0.12)', // Purple
  'hsl(31 97% 56% / 0.10)',  // Warm orange
  'hsl(158 64% 52% / 0.10)', // Teal
];

export default function FloatingOrbs() {
  const [orbs, setOrbs] = useState<Orb[]>([]);

  useEffect(() => {
    // Generate orbs on client only
    const generated: Orb[] = Array.from({ length: 5 }, (_, i) => ({
      id: i,
      x: 15 + Math.random() * 70,
      y: 10 + Math.random() * 70,
      size: 200 + Math.random() * 300,
      color: orbColors[i % orbColors.length],
      delay: i * 2,
    }));
    setOrbs(generated);
  }, []);

  return (
    <div className="absolute inset-0 overflow-hidden pointer-events-none">
      {orbs.map((orb) => (
        <div
          key={orb.id}
          className="absolute blob animate-blob"
          style={{
            left: `${orb.x}%`,
            top: `${orb.y}%`,
            width: orb.size,
            height: orb.size,
            background: orb.color,
            animationDelay: `${orb.delay}s`,
            transform: 'translate(-50%, -50%)',
          }}
        />
      ))}
    </div>
  );
}
