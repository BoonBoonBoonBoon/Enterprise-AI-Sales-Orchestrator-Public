'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { Bell, Search, ChevronDown, ChevronLeft } from 'lucide-react';
import { createClient } from '@/lib/supabase/client';
import { getCurrentProfile } from '@/lib/profile';

interface UserDisplay {
  email?: string | null;
  fullName?: string | null;
}

interface HeaderProps {
  title: string;
  description?: string;
  backHref?: string;
  backLabel?: string;
}

export function Header({ title, description, backHref, backLabel = 'Back' }: HeaderProps) {
  const [user, setUser] = useState<UserDisplay | null>(null);

  useEffect(() => {
    const supabase = createClient();
    getCurrentProfile(supabase).then((profile) => {
      if (!profile) {
        setUser(null);
        return;
      }
      setUser({
        email: profile.email,
        fullName: profile.fullName,
      });
    });
  }, []);

  const initials = user?.fullName
    ?.split(' ')
    .map((n) => n[0])
    .join('')
    .toUpperCase()
    .slice(0, 2) || user?.email?.[0]?.toUpperCase() || '?';

  return (
    <header className="h-16 border-b border-border bg-card flex items-center justify-between px-6">
      <div className="flex items-center gap-3">
        {backHref && (
          <Link
            href={backHref}
            className="inline-flex items-center gap-1.5 rounded-lg border border-input bg-background px-3 py-1.5 text-sm font-medium text-foreground hover:bg-secondary transition-colors"
          >
            <ChevronLeft className="h-4 w-4" />
            {backLabel}
          </Link>
        )}
        <div>
          <h1 className="text-lg font-semibold">{title}</h1>
          {description && (
            <p className="text-sm text-muted-foreground">{description}</p>
          )}
        </div>
      </div>

      <div className="flex items-center gap-4">
        {/* Search */}
        <div className="relative hidden md:block">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search..."
            className="w-64 pl-9 pr-4 py-2 rounded-lg border border-input bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          />
        </div>

        {/* Notifications */}
        <button className="relative p-2 rounded-lg hover:bg-secondary transition-colors">
          <Bell className="h-5 w-5 text-muted-foreground" />
          <span className="absolute top-1.5 right-1.5 h-2 w-2 rounded-full bg-primary" />
        </button>

        {/* User menu */}
        <button className="flex items-center gap-2 p-1.5 rounded-lg hover:bg-secondary transition-colors">
          <div className="h-8 w-8 rounded-full bg-primary/10 flex items-center justify-center text-sm font-medium text-primary">
            {initials}
          </div>
          <ChevronDown className="h-4 w-4 text-muted-foreground" />
        </button>
      </div>
    </header>
  );
}
