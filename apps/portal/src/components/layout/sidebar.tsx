'use client';

import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import {
  LayoutDashboard,
  Inbox,
  FileEdit,
  Users,
  Mail,
  Settings,
  LogOut,
  Zap,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { useEffect, useMemo, useState } from 'react';
import { supabase } from '@/lib/supabase';

const navigation = [
  { name: 'Dashboard', href: '/dashboard', icon: LayoutDashboard },
  { name: 'Drafts', href: '/dashboard/drafts', icon: FileEdit, badge: 3 },
  { name: 'Inbox', href: '/dashboard/inbox', icon: Inbox },
  { name: 'Leads', href: '/dashboard/leads', icon: Users },
  { name: 'Mailboxes', href: '/dashboard/mailboxes', icon: Mail },
  { name: 'Settings', href: '/dashboard/settings', icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const [collapsed, setCollapsed] = useState(false);
  const [isSigningOut, setIsSigningOut] = useState(false);
  const [profileName, setProfileName] = useState('');
  const [profileEmail, setProfileEmail] = useState('');

  const initials = useMemo(() => {
    const base = profileName || profileEmail || 'User';
    return base
      .split(' ')
      .filter(Boolean)
      .slice(0, 2)
      .map((part) => part[0]?.toUpperCase())
      .join('') || 'U';
  }, [profileName, profileEmail]);

  useEffect(() => {
    let isMounted = true;

    const hydrateUser = async () => {
      const { data, error } = await supabase.auth.getUser();
      if (!isMounted || error || !data.user) {
        return;
      }
      const meta = data.user.user_metadata || {};
      const name = meta.name || meta.full_name || meta.display_name || '';
      setProfileName(name || data.user.email || '');
      setProfileEmail(data.user.email || '');
    };

    hydrateUser();

    const { data: authListener } = supabase.auth.onAuthStateChange((_event, session) => {
      if (!isMounted) {
        return;
      }
      const user = session?.user;
      const meta = user?.user_metadata || {};
      const name = meta.name || meta.full_name || meta.display_name || '';
      setProfileName(name || user?.email || '');
      setProfileEmail(user?.email || '');
    });

    return () => {
      isMounted = false;
      authListener?.subscription?.unsubscribe();
    };
  }, []);

  const handleSignOut = async () => {
    if (!window.confirm('Do you want to sign out?')) {
      return;
    }

    setIsSigningOut(true);
    try {
      await supabase.auth.signOut();
    } finally {
      router.push('/');
      router.refresh();
      setIsSigningOut(false);
    }
  };

  return (
    <aside
      className={cn(
        'flex flex-col h-screen border-r border-border/60 bg-card/50 backdrop-blur-xl transition-all duration-300',
        collapsed ? 'w-16' : 'w-64'
      )}
    >
      {/* Logo */}
      <Link href="/dashboard" className="flex items-center gap-2 p-4 border-b border-border/40">
        <div className="h-8 w-8 rounded-lg bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center flex-shrink-0">
          <Zap className="h-5 w-5 text-white" />
        </div>
        {!collapsed && <span className="font-bold text-lg">Agentic</span>}
      </Link>

      {/* Navigation */}
      <nav className="flex-1 p-3 space-y-1">
        {navigation.map((item) => {
          const isActive = pathname === item.href || (item.href !== '/dashboard' && pathname.startsWith(item.href));
          return (
            <Link
              key={item.name}
              href={item.href}
              className={cn(
                'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all',
                isActive
                  ? 'bg-primary/10 text-primary border border-primary/20'
                  : 'text-muted-foreground hover:text-foreground hover:bg-muted/50'
              )}
            >
              <item.icon className="h-5 w-5 flex-shrink-0" />
              {!collapsed && (
                <>
                  <span className="flex-1">{item.name}</span>
                  {item.badge && (
                    <span className="flex items-center justify-center h-5 min-w-[20px] px-1.5 rounded-full bg-primary text-primary-foreground text-xs">
                      {item.badge}
                    </span>
                  )}
                </>
              )}
            </Link>
          );
        })}
      </nav>

      {/* Collapse toggle */}
      <div className="p-3 border-t border-border/40">
        <Button
          variant="ghost"
          size="sm"
          onClick={() => setCollapsed(!collapsed)}
          className="w-full justify-center"
        >
          {collapsed ? <ChevronRight className="h-4 w-4" /> : <ChevronLeft className="h-4 w-4" />}
        </Button>
      </div>

      {/* User section */}
      <div className="p-3 border-t border-border/40">
        <Link
          href="/dashboard/settings"
          className={cn(
            'flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-muted/50 cursor-pointer transition-colors',
            collapsed && 'justify-center'
          )}
        >
          <div className="h-8 w-8 rounded-full bg-gradient-to-br from-cyan-500 to-blue-500 flex items-center justify-center text-white text-sm font-medium flex-shrink-0">
            {initials}
          </div>
          {!collapsed && (
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium truncate">{profileName || 'User'}</p>
              <p className="text-xs text-muted-foreground truncate">{profileEmail || 'Signed out'}</p>
            </div>
          )}
        </Link>
        {!collapsed && (
          <Button
            variant="ghost"
            size="sm"
            className="w-full mt-2 text-muted-foreground"
            onClick={handleSignOut}
            disabled={isSigningOut}
          >
            <LogOut className="h-4 w-4 mr-2" />
            {isSigningOut ? 'Signing out…' : 'Sign out'}
          </Button>
        )}
      </div>
    </aside>
  );
}
