'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { cn } from '@/lib/utils';
import {
  LayoutDashboard,
  Inbox,
  Users,
  BarChart3,
  Settings,
  Sparkles,
  HelpCircle,
  LogOut,
} from 'lucide-react';
import { createClient } from '@/lib/supabase/client';
import { useRouter } from 'next/navigation';

const navigation = [
  { name: 'Overview', href: '/dashboard', icon: LayoutDashboard },
  { name: 'Inbox', href: '/dashboard/inbox', icon: Inbox, badge: 3 },
  { name: 'Prospects', href: '/dashboard/leads', icon: Users },
  { name: 'Analytics', href: '/dashboard/analytics', icon: BarChart3 },
  { name: 'Settings', href: '/dashboard/settings', icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();

  const handleSignOut = async () => {
    const supabase = createClient();
    await supabase.auth.signOut();
    router.push('/login');
    router.refresh();
  };

  return (
    <aside className="w-64 border-r border-border bg-card flex flex-col h-screen">
      {/* Logo */}
      <div className="h-16 flex items-center gap-3 px-6 border-b border-border">
        <div className="h-9 w-9 rounded-lg bg-gradient-to-br from-emerald-500 to-teal-600 flex items-center justify-center">
          <Sparkles className="h-5 w-5 text-white" />
        </div>
        <div>
          <span className="font-bold text-lg">Monty</span>
          <span className="text-xs text-muted-foreground ml-1.5">Portal</span>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 py-4 space-y-1">
        {navigation.map((item) => {
          const isActive = pathname === item.href || 
            (item.href !== '/dashboard' && pathname.startsWith(item.href));

          return (
            <Link
              key={item.name}
              href={item.href}
              className={cn(
                'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors',
                isActive
                  ? 'bg-primary/10 text-primary'
                  : 'text-muted-foreground hover:bg-secondary hover:text-foreground'
              )}
            >
              <item.icon className="h-4 w-4" />
              <span className="flex-1">{item.name}</span>
              {item.badge && (
                <span className="px-1.5 py-0.5 text-xs rounded-full bg-primary text-primary-foreground">
                  {item.badge}
                </span>
              )}
            </Link>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="p-3 border-t border-border space-y-1">
        <Link
          href="/help"
          className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium text-muted-foreground hover:bg-secondary hover:text-foreground transition-colors"
        >
          <HelpCircle className="h-4 w-4" />
          Help & Support
        </Link>
        <button
          onClick={handleSignOut}
          className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium text-muted-foreground hover:bg-secondary hover:text-foreground transition-colors"
        >
          <LogOut className="h-4 w-4" />
          Sign out
        </button>
      </div>
    </aside>
  );
}
