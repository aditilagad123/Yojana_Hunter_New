"use client";

import React, { useState, useEffect, useRef } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { 
  ChevronDown, 
  User as UserIcon, 
  Menu, 
  X, 
  Bookmark, 
  LayoutDashboard, 
  LogOut, 
  Sparkles,
  ShieldCheck
} from "lucide-react";
import { useAuth } from "@/context/AuthContext";

export const AppHeader: React.FC = () => {
  const pathname = usePathname();
  const router = useRouter();
  const { user, profile, isAuthenticated, logout } = useAuth();

  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const userMenuRef = useRef<HTMLDivElement | null>(null);

  // Close menus on outside click
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (userMenuRef.current && !userMenuRef.current.contains(event.target as Node)) {
        setUserMenuOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleLogout = async () => {
    setUserMenuOpen(false);
    setMobileMenuOpen(false);
    await logout();
    router.push("/login");
  };

  if (pathname?.startsWith("/admin")) {
    return null;
  }

  const displayName = profile?.name || user?.name || user?.email?.split("@")[0] || "Citizen";
  const initialLetter = displayName.charAt(0).toUpperCase();

  return (
    <header className="sticky top-0 z-40 w-full bg-white/95 backdrop-blur-md border-b border-brand-border">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        {/* Brand Logo */}
        <Link href="/" className="flex items-center gap-2.5 group">
          <div className="w-8 h-8 rounded-lg bg-green-50 border border-green-200 flex items-center justify-center p-1 shadow-sm">
            <svg viewBox="0 0 32 32" fill="none" className="w-6 h-6">
              <path d="M7 21C7 21 8.5 13 16 11C23.5 9 25 7 25 7C25 7 24.5 15 18 19C13 22 7 21 7 21Z" fill="#16A36A"/>
              <path d="M12 21C14 18 17 15 22 13" stroke="#DCFCE7" strokeWidth="1.8" strokeLinecap="round"/>
              <circle cx="21" cy="9" r="2" fill="#2DC6B1"/>
            </svg>
          </div>
          <div className="flex flex-col">
            <span className="font-extrabold text-xl tracking-tight text-brand-navy">
              Yojana<span className="text-brand-blue"> Hunter</span>
            </span>
          </div>
        </Link>

        {/* Center Nav Links */}
        <nav className="hidden md:flex items-center gap-8">
          <Link
            href="/"
            className={`text-sm font-medium transition ${
              pathname === "/" ? "text-brand-blue font-semibold" : "text-slate-600 hover:text-brand-navy"
            }`}
          >
            Home
          </Link>
          {isAuthenticated && (
            <>
              <Link
                href="/onboarding"
                className={`text-sm font-bold transition px-3 py-1.5 rounded-xl flex items-center gap-1.5 shadow-xs ${
                  pathname === "/onboarding" || pathname === "/interview"
                    ? "bg-brand-blue text-white"
                    : "bg-blue-50 text-brand-blue hover:bg-blue-100 border border-blue-200"
                }`}
              >
                <Sparkles className="w-3.5 h-3.5 text-teal-400" />
                <span>Start Now</span>
              </Link>
              <Link
                href="/schemes"
                className={`text-sm font-medium transition ${
                  pathname === "/schemes" ? "text-brand-blue font-semibold" : "text-slate-600 hover:text-brand-navy"
                }`}
              >
                Schemes
              </Link>
              <Link
                href="/dashboard"
                className={`text-sm font-medium transition ${
                  pathname === "/dashboard" ? "text-brand-blue font-semibold" : "text-slate-600 hover:text-brand-navy"
                }`}
              >
                Dashboard
              </Link>
              <Link
                href="/saved-schemes"
                className={`text-sm font-medium transition ${
                  pathname === "/saved-schemes" ? "text-brand-blue font-semibold" : "text-slate-600 hover:text-brand-navy"
                }`}
              >
                My Schemes
              </Link>
              <Link
                href="/profile"
                className={`text-sm font-medium transition ${
                  pathname === "/profile" ? "text-brand-blue font-semibold" : "text-slate-600 hover:text-brand-navy"
                }`}
              >
                My Profile
              </Link>
            </>
          )}
        </nav>

        {/* Right Controls */}
        <div className="flex items-center gap-3">


          {/* Authenticated User Menu or Guest Sign In/Register */}
          {isAuthenticated ? (
            <div className="relative" ref={userMenuRef}>
              <button
                onClick={() => setUserMenuOpen(!userMenuOpen)}
                className="flex items-center gap-2 p-1 pl-1.5 pr-2.5 rounded-full bg-slate-50 border border-brand-border hover:bg-slate-100 transition focus:outline-none"
                aria-label="User navigation menu"
              >
                <div className="w-7 h-7 rounded-full bg-gradient-to-tr from-brand-blue to-teal-400 flex items-center justify-center text-white font-bold text-xs shadow-sm">
                  {initialLetter}
                </div>
                <span className="hidden sm:inline text-xs font-semibold text-brand-navy max-w-[100px] truncate">
                  {displayName}
                </span>
                <ChevronDown className="w-3 h-3 text-slate-400" />
              </button>

              {userMenuOpen && (
                <div className="absolute right-0 mt-2 w-56 bg-white rounded-2xl shadow-floating border border-brand-border py-2 z-50 animate-fadeIn">
                  {/* User info header */}
                  <div className="px-4 py-2.5 border-b border-brand-border">
                    <p className="text-xs font-bold text-brand-navy truncate">
                      {displayName}
                    </p>
                    <p className="text-2xs text-slate-500 truncate">
                      {user?.email}
                    </p>
                    {profile?.userLevel && (
                      <span className="inline-block mt-1 px-2 py-0.5 rounded-full text-3xs font-extrabold bg-blue-50 text-brand-blue border border-blue-200">
                        Level {profile.userLevel.level} • {profile.userLevel.levelName}
                      </span>
                    )}
                  </div>

                  {/* Menu Items */}
                  <div className="py-1">
                    <Link
                      href="/dashboard"
                      onClick={() => setUserMenuOpen(false)}
                      className="flex items-center gap-2.5 px-4 py-2 text-xs font-medium text-slate-700 hover:bg-blue-50 hover:text-brand-blue transition"
                    >
                      <LayoutDashboard className="w-3.5 h-3.5 text-slate-400" />
                      <span>Dashboard</span>
                    </Link>

                    <Link
                      href="/profile"
                      onClick={() => setUserMenuOpen(false)}
                      className="flex items-center gap-2.5 px-4 py-2 text-xs font-medium text-slate-700 hover:bg-blue-50 hover:text-brand-blue transition"
                    >
                      <UserIcon className="w-3.5 h-3.5 text-slate-400" />
                      <span>My Profile</span>
                    </Link>

                    <Link
                      href="/saved-schemes"
                      onClick={() => setUserMenuOpen(false)}
                      className="flex items-center gap-2.5 px-4 py-2 text-xs font-medium text-slate-700 hover:bg-blue-50 hover:text-brand-blue transition"
                    >
                      <Bookmark className="w-3.5 h-3.5 text-slate-400" />
                      <span>My Scheme</span>
                    </Link>
                  </div>

                  {/* Logout */}
                  <div className="pt-1 border-t border-brand-border">
                    <button
                      onClick={handleLogout}
                      className="w-full flex items-center gap-2.5 px-4 py-2 text-xs font-semibold text-rose-600 hover:bg-rose-50 transition"
                    >
                      <LogOut className="w-3.5 h-3.5" />
                      <span>Sign Out</span>
                    </button>
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="flex items-center gap-2">
              <Link
                href="/admin/login"
                className="hidden sm:inline-flex items-center gap-1 text-xs font-semibold text-slate-500 hover:text-amber-700 px-2.5 py-1.5 rounded-lg border border-transparent hover:border-slate-200 transition"
                title="Administrator Portal"
              >
                <ShieldCheck className="w-3.5 h-3.5 text-amber-500" />
                <span>Admin</span>
              </Link>
              <Link
                href="/login"
                className="text-xs sm:text-sm font-bold text-slate-700 hover:text-brand-blue px-3 py-1.5 rounded-lg transition"
              >
                Sign In
              </Link>
              <Link
                href="/register"
                className="inline-flex items-center justify-center px-3.5 py-1.5 text-xs sm:text-sm font-bold text-white bg-brand-blue hover:bg-brand-blue-dark rounded-lg shadow-xs transition"
              >
                Register
              </Link>
            </div>
          )}

          {/* Mobile menu trigger */}
          <button
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            className="md:hidden p-2 text-slate-600 rounded-lg hover:bg-slate-100"
          >
            {mobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
          </button>
        </div>
      </div>

      {/* Mobile Nav Drawer */}
      {mobileMenuOpen && (
        <div className="md:hidden border-t border-brand-border bg-white px-4 pt-2 pb-4 space-y-1 shadow-lg animate-fadeIn">
          <Link
            href="/"
            onClick={() => setMobileMenuOpen(false)}
            className="block px-3 py-2 rounded-lg text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            Home
          </Link>

          {isAuthenticated && (
            <>
              <Link
                href="/onboarding"
                onClick={() => setMobileMenuOpen(false)}
                className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-bold text-brand-blue bg-blue-50 border border-blue-200"
              >
                <Sparkles className="w-4 h-4 text-teal-500" />
                <span>Start Now (Enter Details)</span>
              </Link>
              <Link
                href="/schemes"
                onClick={() => setMobileMenuOpen(false)}
                className="block px-3 py-2 rounded-lg text-sm font-medium text-slate-700 hover:bg-slate-50"
              >
                Schemes
              </Link>
              <Link
                href="/dashboard"
                onClick={() => setMobileMenuOpen(false)}
                className="block px-3 py-2 rounded-lg text-sm font-medium text-slate-700 hover:bg-slate-50"
              >
                Dashboard
              </Link>
              <Link
                href="/profile"
                onClick={() => setMobileMenuOpen(false)}
                className="block px-3 py-2 rounded-lg text-sm font-medium text-slate-700 hover:bg-slate-50"
              >
                My Profile
              </Link>
              <Link
                href="/saved-schemes"
                onClick={() => setMobileMenuOpen(false)}
                className="block px-3 py-2 rounded-lg text-sm font-medium text-slate-700 hover:bg-slate-50"
              >
                My Schemes
              </Link>
              <Link
                href="/action-plan"
                onClick={() => setMobileMenuOpen(false)}
                className="block px-3 py-2 rounded-lg text-sm font-medium text-slate-700 hover:bg-slate-50"
              >
                Action Plan
              </Link>
            </>
          )}

          <div className="pt-2 border-t border-brand-border">
            {isAuthenticated ? (
              <button
                onClick={handleLogout}
                className="w-full text-left px-3 py-2 rounded-lg text-sm font-semibold text-rose-600 hover:bg-rose-50"
              >
                Sign Out ({displayName})
              </button>
            ) : (
              <div className="space-y-2 pt-1">
                <div className="flex gap-2">
                  <Link
                    href="/login"
                    onClick={() => setMobileMenuOpen(false)}
                    className="flex-1 text-center py-2 px-3 rounded-lg text-sm font-bold text-slate-700 bg-slate-100 hover:bg-slate-200"
                  >
                    Sign In
                  </Link>
                  <Link
                    href="/register"
                    onClick={() => setMobileMenuOpen(false)}
                    className="flex-1 text-center py-2 px-3 rounded-lg text-sm font-bold text-white bg-brand-blue hover:bg-brand-blue-dark"
                  >
                    Register
                  </Link>
                </div>
                <Link
                  href="/admin/login"
                  onClick={() => setMobileMenuOpen(false)}
                  className="flex items-center justify-center gap-1.5 py-1.5 px-3 rounded-lg text-xs font-semibold text-slate-600 bg-slate-50 border border-slate-200"
                >
                  <ShieldCheck className="w-3.5 h-3.5 text-amber-500" />
                  <span>Admin Portal</span>
                </Link>
              </div>
            )}
          </div>
        </div>
      )}
    </header>
  );
};
